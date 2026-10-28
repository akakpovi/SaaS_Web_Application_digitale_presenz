import { spawnSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
)

/**
 * Removes only the rows this suite creates: accounts prefixed `e2e-` and the
 * public-scan leads sent to `e2e-…` addresses. The rest of the database is
 * never touched.
 */
const CLEANUP = `
from accounts.models import User
from public_checker.models import PublicLead

users = User.objects.filter(email__startswith="e2e-")
print("e2e accounts removed:", users.count())
users.delete()

leads = PublicLead.objects.filter(email__startswith="e2e-")
print("e2e public leads removed:", leads.count())
leads.delete()
`

export default async function globalTeardown(): Promise<void> {
  if (process.env.E2E_SKIP_DOCKER_SETUP === "1") return
  const result = spawnSync(
    "docker",
    ["compose", "exec", "-T", "web", "python", "manage.py", "shell"],
    { cwd: repoRoot, input: CLEANUP, encoding: "utf8" },
  )
  if (result.status !== 0) {
    console.warn(
      "[e2e] Teardown could not reach the backend container; test accounts " +
        "starting with `e2e-` were left in place.",
      result.stderr || result.stdout,
    )
    return
  }
  if (result.stdout.trim()) {
    console.log(`[e2e] ${result.stdout.trim().split("\n").slice(-2).join(" | ")}`)
  }
}
