# Phase E — AI Advisor API, Celery and Context Resilience

**Date:** 2026-10-24  
**Scope:** `advisory`, `organizations`, `websites`, `scans`, `config`  
**Status:** implemented and validated locally

---

## 1. Executive summary

| Requirement | Status |
|---|---|
| Dedicated Celery task with feature flag and retries | Done |
| Scan task queues advisor asynchronously | Done |
| Organization-scoped recommendation API | Done |
| Owner/Admin/Analyst/Viewer role enforcement | Done |
| Deterministic fallback on failed run, without AI call or AI persistence | Done |
| Accept/dismiss trace with user and timestamp | Done |
| Strict prompt caps and evidence ranking | Done |
| IntegrityError-safe concurrent run creation | Done |
| Full backend suite | **591/591 passed** |
| Django checks / migration drift | **No issues / no changes** |

The main structural finding was that the repository had **no Organization or
Membership model** despite the plan selling team access. Owner scoping alone
could not satisfy the Viewer/Analyst requirement. A minimal `organizations`
app was therefore introduced, `Website` gained a nullable `organization` FK,
and existing users/websites are backfilled into personal organizations. The
advisory API is now scoped by organization membership while preserving the
legacy `Website.owner` as a compatibility path.

---

## 2. Celery task

File: `backend/advisory/tasks.py`

Task:

```text
advisory.tasks.generate_scan_recommendations_task(scan_id)
```

Behaviour:

1. Re-checks `AI_ADVISOR_ENABLED` inside the worker. A message queued before a
   kill switch cannot generate billable AI traffic.
2. Rejects missing scans, guest scans and scans that are not `COMPLETED`.
3. Calls `generate_recommendations_for_scan(..., retry_failed=retries > 0)`.
4. Contains every service exception and returns a sanitised result. Provider
   bodies, prompts and evidence never enter the Celery result or logs.
5. On an exhausted quota, schedules a Celery retry with a delayed countdown
   between 30 seconds and `AI_ADVISOR_RETRY_MAX_SECONDS` (default 900 s), for
   at most three retries.
6. Uses a 600 s hard / 570 s soft limit so the two-model failover chain and the
   client's bounded HTTP retries cannot be killed prematurely by a 300 s task
   limit.

### Pipeline hook

File: `backend/scans/tasks.py`

After a `COMPLETED` scan is finalised:

```text
alerts.detect_alerts.delay(scan_id)
advisory.tasks.generate_scan_recommendations_task.delay(scan_id)
```

The advisor dispatch is behind `_dispatch_advisor()` and catches every broker
or import failure. Alert/advisor side effects can never turn a good scan into a
failed scan. `AI_ADVISOR_ENABLED=false` prevents even the dispatch call.

### Concurrency

No Redis lock was added. The run claim uses the database as the source of truth:

- unique constraint `(scan, input_hash)`;
- `IntegrityError` recovery followed by `select_for_update()`;
- failed/pending runs are reclaimed only with explicit `retry_failed=True`;
- a `RUNNING` run is reclaimed only after a 10-minute stale window;
- a second worker never makes a second provider call for the same input.

This avoids a new dependency and keeps the lock effective across workers and
hosts.

---

## 3. Organization and role model

New app: `backend/organizations/`

### Models

`Organization`:

- UUID primary key;
- `name`;
- `billing_owner` (nullable, `SET_NULL`);
- `is_personal`;
- partial unique constraint: one personal organization per billing owner.

`Membership`:

- `organization`, `user`;
- unique `(organization, user)`;
- roles: `owner`, `admin`, `analyst`, `viewer`.

### Website ownership

`Website.organization` is a nullable FK. On save, an authenticated website with
an owner and no organization receives the owner's personal organization and an
owner membership automatically. Guest websites stay organization-less.

Migrations:

- `organizations/0001_initial.py`
- `organizations/0002_backfill_personal_organizations.py`
- `websites/0005_website_organization.py`

The backfill creates one personal organization and owner membership per
existing user, then attaches every owned website. The reverse migration is a
no-op; the data migration must be applied to a backed-up database.

### Permission source

File: `backend/advisory/permissions.py`

The organization is **never** read from the request. It is derived from
`scan.website.organization`. The owner fallback remains for compatibility.
A non-member receives 404, which avoids leaking the existence of another
tenant's scan.

Role matrix:

| Role | Read recommendations | Accept / dismiss |
|---|---|---|
| Owner | Yes | Yes |
| Admin | Yes | Yes |
| Analyst | Yes | Yes |
| Viewer | Yes | **No (403)** |

---

## 4. REST API

File: `backend/advisory/views.py`  
Routes: `backend/advisory/urls.py`

### `GET /api/v1/advisory/recommendations/?scan_id=<id>`

- Requires authentication.
- `scan_id` is required and validated as an integer.
- A foreign or unknown scan returns 404.
- Returns the latest run for the scan.

Succeeded run:

```json
{
  "scan_id": 42,
  "run": {
    "id": "…",
    "status": "succeeded",
    "model_used": "groq/qwen/qwen3.8-27b",
    "attempts": 1,
    "error_code": "",
    "completed_at": "2026-10-24T…"
  },
  "source": "ai",
  "persisted": true,
  "recommendations": [
    {
      "id": "…",
      "title": "…",
      "summary": "…",
      "action": "…",
      "effort": "low",
      "priority": "high",
      "confidence": 0.92,
      "check_code": "ssl.overall",
      "category": "ssl",
      "finding_id": null,
      "check_result_id": 12,
      "status": "proposed",
      "accepted_at": null,
      "dismissed_at": null,
      "source": "ai",
      "persisted": true
    }
  ]
}
```

Failed run:

```json
{
  "scan_id": 42,
  "run": {"status": "failed", "error_code": "rate_limit_exceeded", "...": "..."},
  "source": "deterministic",
  "persisted": false,
  "recommendations": [
    {"id": null, "source": "deterministic", "status": "proposed", "...": "..."}
  ]
}
```

The fallback is generated by `RecommendationEngine` only. No provider call is
made and no `AIRecommendation` row is written. A failed run therefore cannot
look like persisted AI output. Deterministic items are read-only because they
have no database identity.

No run yet:

```json
{"scan_id": 42, "run": null, "source": "none", "persisted": false, "recommendations": []}
```

A pending/running run returns an empty list with `source: "none"`; it never
fabricates AI recommendations.

### `POST /api/v1/advisory/recommendations/<uuid>/accept/`

### `POST /api/v1/advisory/recommendations/<uuid>/dismiss/`

- Requires authentication and a membership/role that can write.
- Viewer receives 403 and the recommendation is unchanged.
- Outsider receives 404.
- Writes `status`, `accepted_by`/`accepted_at` or
  `dismissed_by`/`dismissed_at`.
- Idempotent for the same decision; the first timestamp is preserved.
- Switching decision clears the opposite decision fields.

`AIRecommendation` migration `0002` adds the status and audit fields plus a
database check constraint.

---

## 5. Prompt and context resilience

File: `backend/advisory/services/advisor.py`

`PROMPT_VERSION = "scan-advisor-v2"`.

Hard limits:

| Limit | Value |
|---|---|
| Critical findings included | 15 |
| Total findings included | 30 |
| CheckResults included | 10 |
| Per-text field | 3,000 chars |
| Per-JSON evidence field | 3,000 chars |
| Whole snapshot | `AKA_AI_MAX_PROMPT_CHARS` (default 60,000) |

Ranking:

- findings by severity (`critical` first), then status (`fail` first), then id;
- CheckResults by status (`critical` first), then ascending score, then
  category.

If the JSON budget is still exceeded after ranking, the lowest-ranked entries
are dropped until the budget is respected. `evidence_limits` in the snapshot
records totals, included counts and truncation counts. Evidence remains
explicitly labelled `UNTRUSTED TECHNICAL EVIDENCE` and the model is instructed
never to follow its content.

Input-hash changes are deterministic because the snapshot contains the selected
evidence and the limits metadata. A changed prompt version or model order
produces a new run rather than reusing an incompatible one.

---

## 6. Validation

Commands run from the repository root through the canonical test wrapper:

```bash
bash scripts/run_backend_tests.sh advisory
bash scripts/run_backend_tests.sh websites scans
bash scripts/run_backend_tests.sh organizations
bash scripts/run_backend_tests.sh --parallel 4
```

Results:

```text
Full backend suite : Ran 591 tests in 475.750s — OK
Advisory suite      : Ran 76 tests — OK
Websites + scans    : Ran 197 tests in 225.195s — OK
Organizations       : Ran 3 tests in 5.646s — OK
Django check        : System check identified no issues (0 silenced)
makemigrations      : No changes detected
```

The full suite previously exceeded the local serial window. Parallel execution
also exposed that all workers shared the development Redis cache, so the public
scan throttle bucket leaked between workers. `config/settings/test.py` now uses
an isolated `LocMemCache` and explicitly disables `AI_ADVISOR_ENABLED` unless a
test overrides it. Production cache and Redis configuration are unchanged.

The final task-timeout adjustment was followed by a targeted rerun:

```text
advisory.tests.test_tasks : Ran 10 tests in 32.808s — OK
```

Tests added:

- `advisory/tests/test_api.py`
  - owner/viewer/outsider access;
  - missing/invalid scan id;
  - failed-run fallback and non-persistence;
  - Viewer 403 on accept/dismiss;
  - Analyst accept/dismiss and audit fields;
  - idempotent acceptance;
  - unknown recommendation 404;
  - no-run response.
- `advisory/tests/test_tasks.py`
  - disabled flag skips provider;
  - task calls service;
  - service exception is contained;
  - non-completed scan is skipped;
  - quota exhaustion requests a deferred retry;
  - broker outage during dispatch leaves the scan successful;
  - `.delay()` is called only when enabled.
- `advisory/tests/test_resilience.py`
  - 20 critical findings are capped at 15;
  - 12 CheckResults are capped at 10;
  - prompt size is bounded;
  - oversized text is truncated;
  - failed run is reclaimed only with `retry_failed=True`;
  - stale/live concurrency paths and `IntegrityError` recovery.
- `organizations/tests/test_models.py`
  - website creation assigns a personal organization;
  - personal organization creation is idempotent;
  - guest websites have no organization.

---

## 7. Deployment notes

1. Apply migrations before deploying the new task/API:
   ```bash
   python manage.py migrate
   ```
2. Keep `AI_ADVISOR_ENABLED=false` until the canary is approved. The API still
   serves deterministic fallback for existing failed runs when the flag is off,
   but no new task calls the provider.
3. No new package is required. Concurrency control uses PostgreSQL row locks and
   the existing unique constraint.
4. The Celery task uses the default queue. If advisor latency must be isolated,
   add a dedicated `ai` queue and worker in a later deployment step.
5. The organization backfill creates one personal organization per existing
   user. Verify counts and orphan websites before applying to production.

---

## 8. Known limitations

- **Organization layer is advisory-only for now.** `WebsiteViewSet` and
  `ScanViewSet` remain scoped to `website.owner`. A Viewer can read advisory
  recommendations for their organization but cannot yet use the rest of the
  website UI unless those querysets are migrated to membership scoping.
- **No team-management API or admin registration** was added in this step.
  Memberships must currently be created through Django admin/shell.
- **Deterministic fallback decisions are not persisted.** Accept/dismiss require
  a persisted AI recommendation id. This is intentional to avoid presenting
  non-AI output as AI output.
- **Subscription billing remains user-scoped.** `Subscription` is still
  `OneToOne(User)`; the organization borrows the billing owner's plan only by
  convention, not by an enforced database relation.
- **Circuit breaker is in-memory per worker.** Existing limitation from Phase C;
  a Redis-backed breaker is still needed for fleet-wide behavior.
- **Retry countdown is capped** at `AI_ADVISOR_RETRY_MAX_SECONDS` (900 s). A
  provider `Retry-After` longer than that is retried earlier, with at most three
  attempts.
- **Backfill is not reversible.** The data migration's reverse operation is a
  no-op. A production rollback must be planned from a database backup.

---

## 9. Files changed

Backend:

- `backend/organizations/` (new app, services, migrations, tests)
- `backend/websites/models.py`
- `backend/websites/migrations/0005_website_organization.py`
- `backend/advisory/models.py`
- `backend/advisory/migrations/0002_airecommendation_accepted_at_and_more.py`
- `backend/advisory/permissions.py`
- `backend/advisory/serializers.py`
- `backend/advisory/views.py`
- `backend/advisory/urls.py`
- `backend/advisory/tasks.py`
- `backend/advisory/services/advisor.py`
- `backend/advisory/tests/test_api.py`
- `backend/advisory/tests/test_tasks.py`
- `backend/advisory/tests/test_resilience.py`
- `backend/scans/tasks.py`
- `backend/config/settings/base.py`
- `backend/config/settings/test.py`
- `backend/config/urls.py`
- `backend/.env.example`

No commit was created.
