import { execFileSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173"
const mailpitURL = process.env.MAILPIT_URL ?? "http://localhost:8025"
const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
)

async function waitFor(url: string, label: string, attempts = 30): Promise<void> {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // The dev server may still be starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error(
    `${label} is not reachable at ${url}. Start the local stack with ` +
      "`docker compose up -d` and retry.",
  )
}

/**
 * The public scan endpoint allows 5 requests/hour/IP. E2E runs create a scan
 * and send one report e-mail, so repeated runs would eventually hit the
 * throttle. Clear only the public-scan counter (Redis keys), never user data.
 */
function resetPublicScanThrottle(): void {
  if (process.env.E2E_SKIP_DOCKER_SETUP === "1") return
  try {
    const output = execFileSync(
      "docker",
      [
        "compose",
        "exec",
        "-T",
        "redis",
        "redis-cli",
        "--scan",
        "--pattern",
        "*throttle_public_scan*",
      ],
      { cwd: repoRoot, encoding: "utf8" },
    )
    const keys = output
      .split("\n")
      .map((key) => key.trim())
      .filter(Boolean)
    if (keys.length > 0) {
      execFileSync(
        "docker",
        ["compose", "exec", "-T", "redis", "redis-cli", "DEL", ...keys],
        { cwd: repoRoot, encoding: "utf8" },
      )
    }
  } catch (error) {
    console.warn(
      "[e2e] Could not reset the public scan throttle through Docker. " +
        "The test may fail with a 429 if the limit was already reached.",
      error,
    )
  }
}

export default async function globalSetup(): Promise<void> {
  await waitFor(`${baseURL}/api/v1/health/`, "The API (through the Vite proxy)")
  // The API can answer while Vite is still compiling the entry module (for
  // example right after a dependency re-optimisation): wait for the module
  // itself so the first test never lands on a blank page.
  await waitFor(`${baseURL}/src/main.tsx`, "The Vite dev server")
  await waitFor(`${mailpitURL}/api/v1/messages?limit=1`, "Mailpit")
  resetPublicScanThrottle()
}
