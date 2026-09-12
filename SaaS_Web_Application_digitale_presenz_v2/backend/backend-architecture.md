Build the production backend for the existing Presence SaaS frontend.

Read the existing frontend code first and understand its routes, components, API expectations, authentication flow, data structures and the existing 8 website health checks.

==================================================
STACK
==================================================

Django
Django REST Framework
PostgreSQL
Redis
Celery
Celery Beat
Docker
Nginx

Use Python with type hints.

==================================================
CORE MODULES
==================================================

accounts
websites
scans
monitoring
alerts
reports
reviews
notifications
subscriptions

scanners:

website
ssl
dns
email_security
security_headers
performance
uptime
reviews

==================================================
DATABASE
==================================================

Implement:

User
Website
Scan
CheckResult
MonitoringConfig
Alert
Report
Review
Notification
Subscription

Users must only access their own data.

==================================================
PUBLIC WEBSITE CHECKER
==================================================

Implement:

POST /api/v1/public/check

Input:

domain

The endpoint must perform a real website health scan.

Checks:

HTTP/HTTPS
SSL
DNS
SPF/DKIM/DMARC
Security Headers
Performance
Uptime

Return:

health_score
status
individual checks
human-readable messages
technical details where appropriate

The public checker must work without registration.

After the result the frontend can invite the visitor to create an account.

==================================================
SECURITY
==================================================

This is a security-sensitive scanner.

Implement strong SSRF protection.

Block:

localhost
127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
169.254.0.0/16
IPv6 private/loopback/link-local ranges
internal hostnames
unsafe URL schemes

Validate DNS resolution.

Re-check resolved addresses.

Restrict redirects.

Only allow HTTP and HTTPS.

Prevent access to cloud metadata/internal services.

Add request timeouts.

Never allow arbitrary ports.

Add rate limiting to public scans.

Do not expose server-side exceptions to users.

==================================================
ASYNC SCANNING
==================================================

Use Celery for scans.

API:

POST /api/v1/public/check
POST /api/v1/websites/{id}/scan

Long-running checks must not block HTTP requests.

Create Celery tasks for each scanner.

Use retries with sensible limits.

Tasks must be idempotent.

==================================================
MONITORING
==================================================

Implement scheduled monitoring using Celery Beat.

A website can have:

enabled
interval
last_scan
next_scan

Support intervals such as:

5 minutes
15 minutes
30 minutes
1 hour
6 hours
24 hours

When a monitored website changes from healthy to unhealthy:

create Alert

Examples:

SSL expiring
Website offline
DNS problem
Email security problem
Performance degradation
Security header problem

==================================================
API
==================================================

Create:

/api/v1/auth/
/api/v1/public/
/api/v1/websites/
/api/v1/scans/
/api/v1/monitoring/
/api/v1/alerts/
/api/v1/reports/
/api/v1/reviews/
/api/v1/notifications/
/api/v1/subscriptions/

Use DRF serializers and ViewSets/APIViews appropriately.

Generate OpenAPI documentation.

==================================================
AUTHENTICATION
==================================================

Support the existing frontend authentication requirements.

Implement:

registration
login
logout
password reset
JWT authentication

Preserve compatibility with the existing Google OAuth flow.

Do not replace working frontend authentication unnecessarily.

==================================================
PERMISSIONS
==================================================

Authenticated users can only access their own:

websites
scans
monitoring configurations
alerts
reports
reviews
notifications
subscriptions

Admin endpoints must require staff/admin permissions.

==================================================
HEALTH SCORE
==================================================

Create a central scoring engine.

Example:

Website
SSL
DNS
Email Security
Security Headers
Performance
Uptime

Each check produces:

score
status
message
details

The global score must be deterministic and testable.

Keep scoring rules configurable.

==================================================
CACHE
==================================================

Use Redis for:

Celery broker
cache
rate limiting where appropriate
temporary scan state

Avoid unnecessary database queries.

==================================================
REPORTS
==================================================

Generate monthly reports from historical scan data.

Support:

current health score
score history
check breakdown
improvements
problems
recommendations

Prepare the API for downloadable reports.

==================================================
REVIEWS
==================================================

Create the backend structure for:

review sources
ratings
reviews
response drafts
approved responses

Do not implement fake external review integrations.

Use provider adapters so Google/other platforms can be added later.

==================================================
NOTIFICATIONS
==================================================

Support:

email
in-app

Prepare architecture for:

push notifications

Do not hard-code a single notification provider.

==================================================
SUBSCRIPTIONS
==================================================

Create subscription/domain models that support:

Free
Pro
Business

Do not integrate a payment provider unless one already exists in the project.

Keep billing provider-independent.

==================================================
DOCKER
==================================================

Create production-ready Docker configuration for:

django
celery-worker
celery-beat
postgres
redis
nginx

Use environment variables.

Never commit secrets.

Create:

.env.example

==================================================
TESTING
==================================================

Write tests for:

authentication
permissions
website ownership
public scan
SSRF protection
rate limiting
each scanner
health scoring
Celery tasks
monitoring
alerts
API validation

Include integration tests for the public Website Checker.

==================================================
QUALITY
==================================================

Use:

type hints
clean architecture
small services
separation of concerns
structured logging
proper exception handling
database indexes where appropriate

Do not put scanner logic directly inside API views.

==================================================
FRONTEND COMPATIBILITY
==================================================

Inspect the existing React frontend before defining API responses.

Reuse its existing data structures where possible.

Do not redesign the frontend.

Update frontend API integration only where required.

==================================================
IMPLEMENTATION STRATEGY
==================================================

Do NOT build everything blindly in one step.

Phase 1:
Audit existing frontend/backend.

Phase 2:
Create Django project and infrastructure.

Phase 3:
Authentication + users.

Phase 4:
Website + scanning models.

Phase 5:
Real public Website Checker.

Phase 6:
All scanners.

Phase 7:
Monitoring + Celery.

Phase 8:
Alerts + reports.

Phase 9:
Reviews + notifications + subscriptions.

Phase 10:
Docker + production hardening.

Phase 11:
Tests + integration.

After each phase:

run tests
run type checks
run migrations
verify API
fix errors before continuing.

Never fabricate an API or backend integration that does not exist.

At the end provide:

- architecture implemented
- files created/modified
- API endpoints
- database models
- Celery tasks
- security measures
- tests
- Docker services
- remaining work
- deployment instructions
