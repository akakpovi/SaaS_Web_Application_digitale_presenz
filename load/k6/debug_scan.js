import http from "k6/http"
import { check, sleep } from "k6"

const BASE_URL = (__ENV.BASE_URL || "https://localhost").replace(/\/$/, "")
const EMAIL = __ENV.TEST_EMAIL || ""
const PASSWORD = __ENV.TEST_PASSWORD || ""

export const options = {
  insecureSkipTLSVerify: true,
  vus: 2,
  iterations: 2,
}

export function setup() {
  const login = http.post(
    `${BASE_URL}/api/v1/auth/login/`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  )
  const token = login.json("access")
  const websites = http.get(`${BASE_URL}/api/v1/websites/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const rows = websites.json()
  const ids = (Array.isArray(rows) ? rows : rows.results).map((row) => row.id)
  return { token, ids }
}

export default function (data) {
  const websiteId = data.ids[__VU % Math.min(3, data.ids.length)]
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  }
  const created = http.post(
    `${BASE_URL}/api/v1/websites/${websiteId}/scan/`,
    JSON.stringify({ scan_type: "health" }),
    { headers },
  )
  console.log(`create website=${websiteId} status=${created.status} body=${created.body}`)
  const scanId =
    created.status === 202
      ? created.json("scan_id")
      : created.json("active_scan_id")
  console.log(`scanId=${scanId} type=${typeof scanId}`)
  for (let i = 0; i < 4; i += 1) {
    sleep(1)
    const poll = http.get(`${BASE_URL}/api/v1/scans/${scanId}/`, { headers })
    console.log(
      `poll ${i} status=${poll.status} scan_status=${poll.json("status")} type=${typeof poll.json("status")}`,
    )
    if (["completed", "failed", "cancelled"].includes(poll.json("status"))) break
  }
}
