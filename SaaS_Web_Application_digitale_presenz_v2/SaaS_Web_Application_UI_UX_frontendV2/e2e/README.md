# E2E tests (Playwright)

The end-to-end suite covers these journeys against the real stack:

| Test | Flow |
| --- | --- |
| `registration-verification.spec.ts` | sign-up → real verification e-mail in Mailpit → link → verified account → login |
| `public-scan.spec.ts` | visitor scans a domain → real API report → `/report/:id` redirect → share link → lead capture e-mail |
| `i18n-french.spec.ts` | French public pages plus authenticated dashboard, website and settings checks (private checks use the seeded QA account) |
| `legal-seo-dist.spec.ts` | serves the built `dist/` with the nginx rules and checks the pre-rendered legal pages, sitemap and robots (no Docker needed) |
| `bilingual-shell-dist.spec.ts` | same harness: every URL advertised by `hreflang` serves that language as raw HTML, plus hydration, noindex and switcher behaviour |

The two `*-dist.spec.ts` suites verify the *artifact* rather than the dev
server: nginx serves `dist/<route>/index.html` directly and answers 404 for a
public route that was never pre-rendered, which the SPA fallback of the dev
server hides. They therefore need a completed `pnpm build` and fail with that
instruction instead of skipping. `helpers/static-dist.ts` replays the
`try_files` rules of `nginx.conf`, including the bilingual one (`?lang=en`
selects `dist/_i18n/…`, and that folder is `internal`).

The legal pages covered by the first suite are `/impressum`, `/cookies`,
`/privacy`, `/terms` and `/widerruf`. `scripts/verify-nginx.sh` goes one step
further and runs the real `nginx.conf` in a throwaway nginx container against
the same `dist/` (Docker required, skipped with an explicit message otherwise);
run it when a change touches `nginx.conf`, the pre-rendered shells or the
variant folder.

## Prerequisites

The tests exercise the real API, database, Celery worker and Mailpit — there
are no API mocks.

```bash
# from the repository root
docker compose up -d          # Django, PostgreSQL, Redis, Celery, Mailpit, nginx
```

The browser talks to the Vite dev server (`http://localhost:5173`), whose
`/api` proxy reaches the stack, so the local self-signed TLS certificate never
reaches Playwright. The dev server is started automatically by the Playwright
`webServer` block unless one is already running.

## Run

```bash
cd SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2
pnpm install
pnpm exec playwright install chromium   # first run only
pnpm test:e2e
```

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `E2E_BASE_URL` | `http://localhost:5173` | origin under test |
| `MAILPIT_URL` | `http://localhost:8025` | Mailpit HTTP API |
| `E2E_SKIP_DOCKER_SETUP` | unset | do not touch Docker (remote stack, no cleanup) |
| `E2E_EMAIL` | unset | existing account for the French private-screen checks |
| `E2E_PASSWORD` | unset | password for `E2E_EMAIL`; never committed |
| `E2E_WEBSITE_ID` | first listed website | site ID used by the French detail check; CI seeds this exact ID |

### Seeding the authenticated checks

The authenticated French checks need an existing account and website. The CI
job creates the Free plan first (so the user-creation signal can attach a
subscription), then the QA account and website, after the Docker stack is
healthy and before Playwright runs:

```bash
# from the repository root
docker compose exec -T \
  -e E2E_EMAIL="$E2E_EMAIL" \
  -e E2E_PASSWORD="$E2E_PASSWORD" \
  -e E2E_WEBSITE_ID="$E2E_WEBSITE_ID" \
  web python scripts/seed_e2e.py
```

`E2E_EMAIL` and `E2E_PASSWORD` are required. `E2E_WEBSITE_ID` is optional
locally; when set, the script creates or reuses a website with that exact
primary key and verifies that it belongs to the seeded account. The script is
idempotent, ensures an existing QA account has a Free subscription when none
exists, and never prints the password. Do not commit these values.

### Diagnostic

En cas d'échec du job E2E, suivre le [runbook E2E](./RUNBOOK.md). Il décrit
les étapes à inspecter, la classification des erreurs et la reproduction
locale sans exposer les secrets.

Failed runs keep a trace and a screenshot in `test-results/` (gitignored).

### French private-screen checks

`i18n-french.spec.ts` always checks the French public pages and login. Its
dashboard, website-detail and settings checks use an existing account and are
skipped when `E2E_EMAIL`/`E2E_PASSWORD` are absent. Run them with:

```bash
E2E_EMAIL='...' E2E_PASSWORD='...' E2E_WEBSITE_ID='<id>' \
  pnpm exec playwright test e2e/i18n-french.spec.ts --reporter=list
```

Do not put the password in a tracked file. CI passes the values from the
`E2E_EMAIL`, `E2E_PASSWORD` and `E2E_WEBSITE_ID` repository secrets.

### CI

The workflow supports manual `workflow_dispatch` runs. The E2E job seeds the
Free plan, account and website with
`SaaS_Web_Application_digitale_presenz_v2/backend/scripts/seed_e2e.py`, then
runs `i18n-french.spec.ts`. It is blocking: an E2E failure makes the workflow
fail (no `continue-on-error`).

## Test data hygiene

- Both tests generate unique `e2e-…@example.com` addresses.
- `global-setup.ts` clears only the public-scan Redis throttle keys, so repeat
  runs stay deterministic (the public endpoint allows 5 requests/hour/IP).
- `global-teardown.ts` deletes only accounts and public leads whose address
  starts with `e2e-`. Guest scans are anonymous and are purged by the nightly
  cleanup task. The QA account and its website are intentionally outside that
  prefix so the CI seed can reuse them on a repeat run.
