/**
 * Presence — test de charge k6.
 *
 * Trois scénarios simultanés :
 *   1. public_browse  : pages publiques + API de santé/offres ;
 *   2. auth_browse    : navigation authentifiée (websites, scans, monitoring,
 *                       alertes, avis, rapports, abonnement) ;
 *   3. scan_flow      : orchestration réelle Celery — création d'un scan via
 *                       l'API, puis polling jusqu'à l'état terminal.
 *
 * Usage (depuis la racine du dépôt, pile démarrée) :
 *
 *   docker run --rm -i --network host \
 *     -v "$PWD/load/k6:/scripts:ro" \
 *     -e BASE_URL=https://localhost \
 *     -e TEST_EMAIL=... -e TEST_PASSWORD=... \
 *     -e INSECURE_SKIP_TLS_VERIFY=true \
 *     grafana/k6:0.54.0 run /scripts/presence_load_test.js
 *
 * Le compte de test doit avoir un plan payant (quota de scans suffisant) et
 * au moins un website. Aucun scan n'est lancé si SCAN_ENABLED=false.
 */
import http from "k6/http"
import { check, group, sleep } from "k6"
import { Rate, Trend } from "k6/metrics"

const BASE_URL = (__ENV.BASE_URL || "https://localhost").replace(/\/$/, "")
const EMAIL = __ENV.TEST_EMAIL || ""
const PASSWORD = __ENV.TEST_PASSWORD || ""
const SCAN_ENABLED = (__ENV.SCAN_ENABLED || "true") === "true"
const SCAN_ROUNDS = Number(__ENV.SCAN_ROUNDS || 2)
const SCAN_TIMEOUT_SECONDS = Number(__ENV.SCAN_TIMEOUT_SECONDS || 120)

// Seconds, not a k6 time metric: values are already expressed in seconds.
const scanCompletion = new Trend("scan_completion_seconds")
const scanFailures = new Rate("scan_failures")

export const options = {
  insecureSkipTLSVerify: (__ENV.INSECURE_SKIP_TLS_VERIFY || "true") === "true",
  scenarios: {
    public_browse: {
      executor: "ramping-vus",
      exec: "publicBrowse",
      startVUs: 1,
      stages: [
        { duration: "20s", target: 20 },
        { duration: "60s", target: 40 },
        { duration: "20s", target: 0 },
      ],
      tags: { flow: "public" },
    },
    auth_browse: {
      executor: "ramping-vus",
      exec: "authBrowse",
      startTime: "10s",
      startVUs: 1,
      stages: [
        { duration: "15s", target: 10 },
        { duration: "60s", target: 25 },
        { duration: "15s", target: 0 },
      ],
      tags: { flow: "auth" },
    },
    scan_flow: {
      executor: "per-vu-iterations",
      exec: "scanFlow",
      startTime: "20s",
      vus: 2,
      iterations: SCAN_ENABLED ? SCAN_ROUNDS : 0,
      maxDuration: "5m",
      tags: { flow: "scan" },
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<800", "p(99)<1500"],
    checks: ["rate>0.98"],
    scan_failures: ["rate<0.01"],
    scan_completion_seconds: ["p(95)<60000"],
  },
}

const PUBLIC_PATHS = [
  "/",
  "/pricing",
  "/blog",
  "/blog/what-is-dmarc",
  "/api/v1/health/",
  "/api/v1/subscriptions/plans/",
]

const AUTH_PATHS = [
  "/api/v1/websites/",
  "/api/v1/scans/",
  "/api/v1/monitoring/overview/?period=30D",
  "/api/v1/alerts/?status=firing",
  "/api/v1/reviews/",
  "/api/v1/reviews/summary/",
  "/api/v1/reports/",
  "/api/v1/subscriptions/me/",
]

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}` } }
}

function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

export function setup() {
  if (!EMAIL || !PASSWORD) {
    throw new Error("TEST_EMAIL and TEST_PASSWORD are required")
  }

  const login = http.post(
    `${BASE_URL}/api/v1/auth/login/`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { name: "setup-login" },
    },
  )
  if (!check(login, { "login returns 200": (r) => r.status === 200 })) {
    throw new Error(`Login failed: HTTP ${login.status}`)
  }
  const token = login.json("access")
  const websites = http.get(`${BASE_URL}/api/v1/websites/`, authHeaders(token))
  if (!check(websites, { "websites returns 200": (r) => r.status === 200 })) {
    throw new Error(`Website list failed: HTTP ${websites.status}`)
  }
  const payload = websites.json()
  const rows = Array.isArray(payload) ? payload : payload.results || []
  const websiteIds = rows.map((row) => row.id)
  if (websiteIds.length === 0) {
    throw new Error("The load-test account has no website to scan")
  }
  return { token, websiteIds }
}

export function publicBrowse() {
  group("public", () => {
    const path = pick(PUBLIC_PATHS)
    const response = http.get(`${BASE_URL}${path}`, {
      tags: { name: `public ${path}` },
    })
    check(response, {
      [`${path} < 400`]: (r) => r.status < 400,
    })
    sleep(0.3 + Math.random() * 0.7)
  })
}

export function authBrowse(data) {
  if (!data || !data.token) return
  group("authenticated", () => {
    const path = pick(AUTH_PATHS)
    const response = http.get(`${BASE_URL}${path}`, {
      ...authHeaders(data.token),
      tags: { name: `auth ${path}` },
    })
    check(response, {
      [`${path} returns 200`]: (r) => r.status === 200,
    })
    sleep(0.3 + Math.random() * 0.7)
  })
}

export function scanFlow(data) {
  if (!data || !data.websiteIds?.length) return
  const websiteId =
    data.websiteIds[(__VU + __ITER) % Math.min(3, data.websiteIds.length)]
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  }

  const created = http.post(
    `${BASE_URL}/api/v1/websites/${websiteId}/scan/`,
    JSON.stringify({ scan_type: "health" }),
    { headers, tags: { name: "scan-create" } },
  )

  let scanId = null
  if (created.status === 202) {
    // /websites/{id}/scan/ returns the scan object (field ``id``); the
    // monitoring alias returns ``scan_id``. Accept both shapes.
    scanId = created.json("id") || created.json("scan_id")
    check(created, { "scan accepted": () => true })
  } else if (created.status === 409) {
    // Another scan is already running for this website: follow it instead of
    // failing the whole scenario.
    scanId = created.json("active_scan_id")
    check(created, { "scan already running": () => true })
  } else {
    check(created, {
      [`scan accepted (got ${created.status})`]: () => false,
    })
    scanFailures.add(1)
    return
  }

  if (!scanId) {
    scanFailures.add(1)
    return
  }

  const started = Date.now()
  let status = "unknown"
  let finished = false
  while ((Date.now() - started) / 1000 < SCAN_TIMEOUT_SECONDS) {
    sleep(1.5)
    const poll = http.get(`${BASE_URL}/api/v1/scans/${scanId}/`, {
      headers,
      tags: { name: "scan-poll" },
    })
    check(poll, { "scan detail returns 200": (r) => r.status === 200 })
    if (poll.status !== 200) break
    status = poll.json("status")
    if (["completed", "failed", "cancelled"].includes(status)) {
      finished = true
      break
    }
  }

  if (finished) {
    scanCompletion.add((Date.now() - started) / 1000)
  } else {
    console.warn(`scan ${scanId} did not finish within ${SCAN_TIMEOUT_SECONDS}s`)
  }
  if (status !== "completed") {
    console.warn(`scan ${scanId} ended with status=${status} (website ${websiteId})`)
  }
  scanFailures.add(status === "completed" ? 0 : 1)
  check(
    { status },
    { "scan reached a terminal state": (value) => value.status === "completed" },
  )
  sleep(1)
}

export default function () {
  // Default export is unused: every scenario references an explicit exec.
  publicBrowse()
}
