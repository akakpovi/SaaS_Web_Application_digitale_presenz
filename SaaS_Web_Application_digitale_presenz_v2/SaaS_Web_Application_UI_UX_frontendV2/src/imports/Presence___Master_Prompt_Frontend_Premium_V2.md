# PRESENCE — PREMIUM FRONTEND REDESIGN & PRODUCT DESIGN MASTER PROMPT V2

## 0. MASTER INSTRUCTION

You are a world-class:

- Product Designer
- UX/UI Designer
- Design Systems Architect
- SaaS Product Architect
- Senior Frontend Engineer
- Conversion Designer
- Accessibility Specialist
- SEO Product Designer

You are working on **Presence**, a premium B2B SaaS platform for monitoring, analyzing and improving the digital presence, security, performance and reliability of websites.

Your mission is to transform the existing Presence frontend into a **production-grade, premium European SaaS product** with a coherent visual identity, scalable design system, exceptional UX, excellent responsive behavior and a clean handoff to React/TypeScript.

This document is the **MASTER DESIGN SOURCE OF TRUTH** for the frontend redesign.

---

# 1. CRITICAL OPERATING MODE

## IMPORTANT

At this stage, the primary objective is:

> DESIGN THE PRODUCT SYSTEM FIRST.

Do not immediately write implementation code.

Do not modify backend architecture.

Do not invent backend functionality that does not exist.

Do not blindly replace the existing frontend.

Do not create isolated visual mockups.

Instead:

1. Understand the existing Presence product.
2. Preserve useful existing functionality.
3. Establish the visual system.
4. Establish the UX architecture.
5. Design the complete responsive product.
6. Design all important states.
7. Map the design system to reusable frontend components.
8. Prepare the product for implementation using Figma MCP and React.

The final Figma file must be sufficiently structured that another engineer can inspect it and implement the interface without guessing.

---

# 2. PRODUCT VISION

Presence is a complete digital-presence monitoring platform.

A customer enters a website URL and Presence analyzes:

1. Website availability
2. SSL / TLS
3. DNS
4. Email security
5. Security headers
6. Website performance
7. Uptime monitoring

The platform generates a deterministic:

# Website Health Score: 0–100

Health score weights:

- Website availability: 20
- SSL / TLS: 20
- DNS: 15
- Email security: 15
- Security headers: 15
- Performance: 15

Uptime is tracked separately.

Statuses:

- Healthy
- Warning
- Critical
- Neutral

Presence must transform technical information into understandable business-oriented recommendations.

The user should always understand:

- What is wrong?
- Why does it matter?
- How serious is it?
- What is the business impact?
- How can it be fixed?
- What should I do next?

---

# 3. PRODUCT POSITIONING

Presence should feel like:

> Digital health infrastructure for the modern web.

It is not merely:

- a website scanner
- a security scanner
- an uptime monitor
- an SEO tool

It combines these concepts into one understandable digital-presence platform.

The interface should communicate:

- Trust
- Security
- Intelligence
- Technical excellence
- Simplicity
- Reliability
- Premium quality
- Professional B2B software
- European privacy-first positioning

---

# 4. CORE BUSINESS FUNNEL

Design the entire product around this funnel:

VISITOR

↓

SEO / GOOGLE / AI SEARCH / SOCIAL / ADS

↓

PRESENCE LANDING PAGE

↓

FREE WEBSITE SCANNER

↓

SCAN IN PROGRESS

↓

HEALTH SCORE

↓

FREE REPORT

↓

CREATE ACCOUNT

↓

ADD WEBSITE

↓

FIRST SCAN

↓

MONITORING

↓

ALERTS

↓

REPORTS

↓

PRICING

↓

SUBSCRIPTION

↓

CUSTOMER

↓

SHARE PUBLIC REPORT

↓

NEW VISITOR

The frontend must make this journey natural.

The main public CTA should generally be:

"Check my website"

or

"Scan my website for free"

Secondary CTA:

"View pricing"

---

# 5. DESIGN PHILOSOPHY

Presence must look like a serious premium SaaS product.

Visual characteristics:

- Minimal
- Elegant
- Technical
- Clean
- Precise
- High information density where appropriate
- Generous whitespace
- Excellent typography
- Subtle gradients
- Soft elevation
- Refined borders
- Controlled visual depth
- Smooth micro-interactions
- Strong hierarchy
- Excellent responsive behavior

Avoid:

- Generic SaaS templates
- Generic AI-generated dashboards
- Excessive glassmorphism
- Excessive gradients
- Excessive rounded cards
- Childish illustrations
- Excessive decoration
- Cyberpunk aesthetics
- Hacker clichés
- Visual noise

The product must look expensive because of:

- spacing
- typography
- hierarchy
- consistency
- interaction quality
- information architecture
- subtle details

Not because of excessive decoration.

---

# 6. BRAND DIRECTION

Create a distinctive Presence visual identity.

Concept:

> "Digital health infrastructure for the modern web."

The visual identity should combine:

- modern SaaS
- infrastructure
- website intelligence
- security
- reliability
- European professionalism

The product should NOT look like a generic cybersecurity dashboard.

---

# 7. COLOR SYSTEM

Define a complete semantic color system.

Required tokens:

### Brand

- brand.primary
- brand.primaryHover
- brand.primaryActive
- brand.secondary

### Semantic

- success
- successSubtle
- warning
- warningSubtle
- critical
- criticalSubtle
- info
- infoSubtle
- neutral
- neutralSubtle

### Surfaces

- background
- surface
- surfaceElevated
- surfaceMuted
- surfaceInteractive

### Borders

- border
- borderSubtle
- borderStrong
- borderFocus

### Typography

- textPrimary
- textSecondary
- textMuted
- textDisabled
- textInverse

Do not use raw colors inconsistently across components.

All colors must be represented through reusable design variables.

---

# 8. STATUS LANGUAGE

Never communicate status through color alone.

Every status must have:

- icon
- label
- semantic color
- visual hierarchy

Examples:

HEALTHY

✓ Healthy

WARNING

! Warning

CRITICAL

× Critical

NEUTRAL

— Not checked

Use the same language everywhere:

- dashboard
- scans
- checks
- alerts
- monitoring
- reports
- website list
- public reports

---

# 9. TYPOGRAPHY SYSTEM

Use a premium modern sans-serif system.

Prioritize readability.

Define:

- Display
- H1
- H2
- H3
- H4
- Body Large
- Body
- Body Small
- Caption
- Label
- Button
- Metric
- Code
- Technical value

Technical values must have excellent readability.

Examples:

82

92 / 100

99.98%

2.4s

€29

example.com

TLS 1.3

DMARC

Typography must communicate hierarchy immediately.

---

# 10. DESIGN TOKENS

Create a complete token system.

Required token categories:

### Colors
Semantic colors and surfaces.

### Typography
Font family, sizes, weights, line heights and letter spacing.

### Spacing
Use a consistent spacing scale.

### Radius
Define:

- xs
- sm
- md
- lg
- xl
- full

Avoid excessive radius.

### Shadows
Define subtle:

- sm
- md
- lg
- focus

### Borders

### Motion

Define:

- fast
- normal
- slow

And easing curves.

### Breakpoints

Define responsive behavior for:

- mobile
- tablet
- laptop
- desktop
- wide desktop

### Z-index

Define:

- base
- dropdown
- sticky
- modal
- toast
- command menu

### Container widths

Define consistent maximum content widths.

Everything should be reusable.

---

# 11. FIGMA FILE ARCHITECTURE

Structure the Figma project professionally.

Recommended structure:

## PAGE 01 — Foundations

- Brand
- Colors
- Typography
- Spacing
- Radius
- Shadows
- Icons
- Motion
- Grid
- Breakpoints
- Accessibility

## PAGE 02 — Components

- Buttons
- Inputs
- Forms
- Cards
- Badges
- Status indicators
- Score components
- Tables
- Charts
- Navigation
- Modals
- Drawers
- Tooltips
- Toasts
- Skeletons
- Empty states
- Error states

## PAGE 03 — Patterns

- Authentication
- Forms
- Scan progress
- Health score
- Check result
- Alerts
- Monitoring
- Reports
- Data tables
- Filters
- Search
- Command menu

## PAGE 04 — Public Desktop

All public desktop pages.

## PAGE 05 — Public Mobile

All public mobile pages.

## PAGE 06 — Application Desktop

All authenticated application pages.

## PAGE 07 — Application Mobile

All authenticated mobile pages.

## PAGE 08 — Admin / Growth

All internal administration and analytics screens.

## PAGE 09 — Prototype / User Flows

Major clickable flows.

---

# 12. FIGMA COMPONENT RULES

Every reusable component should use:

- Auto Layout
- Variables
- Variants
- Component properties
- Consistent naming

Example:

Button

Variants:

- Primary
- Secondary
- Ghost
- Destructive
- Link

Properties:

- size
- icon
- loading
- disabled
- state

Do not create visually duplicated components.

Create one reusable source component whenever possible.

---

# 13. FIGMA NAMING CONVENTION

Use predictable names.

Examples:

Component/Button

Component/Input

Component/StatusBadge

Component/HealthScore

Component/AlertCard

Component/CheckCard

Component/Chart

Component/Navigation

Pattern/ScanProgress

Pattern/WebsiteOverview

Page/Dashboard/Desktop

Page/Dashboard/Mobile

State/Dashboard/Loading

State/Dashboard/Empty

State/Dashboard/Error

This structure must make the design easy to inspect using Figma MCP.

---

# 14. RESPONSIVE DESIGN

Design every important screen intentionally for:

- Desktop
- Laptop
- Tablet
- Mobile

Do NOT simply shrink desktop layouts.

Desktop and mobile should be considered different UX contexts.

---

# 15. MOBILE UX

Mobile must be first-class.

Use where appropriate:

- bottom navigation
- sticky action bars
- bottom sheets
- drawers
- full-screen dialogs
- touch-friendly controls
- simplified tables
- stacked cards
- horizontal scrolling only when justified
- mobile filters
- mobile-friendly charts

Touch targets should be comfortable.

Avoid dense desktop-style tables on mobile.

---

# 16. MOBILE APPLICATION NAVIGATION

Authenticated mobile navigation should prioritize:

1. Dashboard
2. Websites
3. Scans
4. Monitoring
5. Alerts

Secondary:

- Reports
- Billing
- Settings
- Account

Use a clean mobile navigation system.

Consider a bottom navigation with a secondary "More" surface for lower-frequency destinations.

---

# 17. DARK MODE

Support:

- Light
- Dark
- System

Dark mode must be intentionally designed.

Do not invert the light design.

Define dedicated:

- surfaces
- borders
- text hierarchy
- shadows
- chart colors
- status colors

Technical dashboards should feel especially strong in dark mode.

---

# 18. PUBLIC WEBSITE STRUCTURE

Create:

/

 /features

 /pricing

 /scanner

 /website-checker

 /website-health-checker

 /seo-checker

 /security-checker

 /ssl-checker

 /dns-checker

 /email-security-checker

 /website-performance-checker

 /solutions

 /solutions/small-business

 /solutions/freelancers

 /solutions/agencies

 /solutions/restaurants

 /solutions/ecommerce

 /solutions/local-business

 /blog

 /resources

 /about

 /contact

 /privacy

 /terms

Private application:

/app

/app/dashboard

/app/websites

/app/websites/:id

/app/scans

/app/monitoring

/app/alerts

/app/reports

/app/settings

/app/billing

---

# 19. GLOBAL PUBLIC NAVIGATION

Desktop navigation:

- Logo
- Features
- Solutions
- Resources
- Pricing

Actions:

- Log in
- Check my website

Mobile:

- Logo
- Menu
- Primary CTA

Navigation must remain simple.

Do not overload the header.

---

# 20. LANDING PAGE

Create a premium conversion-focused landing page.

## HERO

Headline concept:

"Know exactly how healthy your website is."

Subheadline:

"Presence continuously checks your website's availability, security, DNS, email protection and performance — and tells you what needs attention."

Primary CTA:

"Check my website for free"

Secondary CTA:

"View pricing"

Immediately show an interactive URL scanner:

Website URL

[ https://example.com ]

[ Scan ]

Reassurance:

"No credit card required."

---

# 21. HERO VISUAL

Do not use generic stock imagery.

Show a premium Website Health visualization.

Example:

Website Health

92 / 100

Healthy

Availability ✓

SSL ✓

DNS ✓

Email Security ✓

Security Headers !

Performance ✓

Use subtle data animation.

The visual should communicate that Presence is actively analyzing a real website.

---

# 22. LANDING PAGE CONTENT STRUCTURE

Recommended hierarchy:

1. Hero
2. Interactive scanner
3. Trust/value statement
4. Six core checks
5. How Presence works
6. Example health report
7. Monitoring
8. Alerts
9. Reports
10. Solutions
11. Security/privacy
12. Pricing preview
13. FAQ
14. Final scanner CTA
15. Footer

Do not overload the page.

Every section must have a purpose.

---

# 23. TRUST SECTION

Headline:

"Everything you need to keep your website healthy."

Show:

- Website
- SSL
- DNS
- Email Security
- Security Headers
- Performance

Use concise explanations.

---

# 24. FREE WEBSITE SCANNER

Create a complete public scanner.

## STEP 1 — URL INPUT

Large input:

"Enter your website URL"

CTA:

"Scan website"

Validate URL.

Show:

- invalid URL state
- empty state
- loading state
- network error
- unavailable website state

---

# 25. SCAN PROGRESS

Create a premium scanning experience.

Example:

Analyzing example.com

✓ Checking availability

✓ Inspecting SSL certificate

✓ Resolving DNS

● Checking email security

○ Checking security headers

○ Measuring performance

Show:

- progress
- current operation
- completed operations
- pending operations
- reassuring explanation
- technical indicators

Do not show a fake hacker terminal.

Make it feel like premium infrastructure software.

---

# 26. SCAN LIFECYCLE UX

The frontend must visually support the real scan lifecycle:

QUEUED

↓

RUNNING

↓

SCANNING

↓

COMPLETED

or

FAILED

or

CANCELLED

The UI must clearly distinguish:

- waiting
- active scanning
- completed
- failed
- cancelled

Do not invent fake percentage precision.

If backend progress is unavailable, use stage-based progress rather than fake exact percentages.

---

# 27. SCAN RESULT

Create a highly polished result page.

Header:

example.com

Website Health Score

92 / 100

Healthy

Show prominent radial score.

Then show:

Availability 20/20

SSL 20/20

DNS 15/15

Email Security 13/15

Security Headers 15/15

Performance 9/15

Each dimension must communicate:

- score
- status
- short explanation
- problem count
- action

---

# 28. HEALTH SCORE COMPONENT

Create a reusable HealthScore component.

Variants:

- Large
- Medium
- Compact
- Inline
- Public Report
- Dashboard

States:

- Healthy
- Warning
- Critical
- Neutral
- Loading

The score must always communicate:

score

status

context

Example:

92 / 100

Healthy

Last scanned 5 minutes ago

---

# 29. PROBLEMS SECTION

Show:

"3 things need your attention"

Each issue:

- severity
- problem
- explanation
- business impact
- recommended solution
- CTA

Example:

CRITICAL

Missing Content-Security-Policy

"Your website is missing an important security header that can help reduce certain classes of attacks."

Actions:

"Learn how to fix"

"View detailed report"

---

# 30. CONVERSION WALL

After meaningful free information, encourage registration.

Headline:

"Get the complete website report"

Unlock:

✓ Full technical analysis

✓ Detailed recommendations

✓ Scan history

✓ Monitoring

✓ Alerts

✓ Reports

CTA:

"Create my free account"

Never hide the basic health score behind registration.

Give meaningful value before asking for signup.

---

# 31. SEO LANDING PAGES

Create:

- Website Checker
- Website Health Checker
- SEO Checker
- Security Checker
- SSL Checker
- DNS Checker
- Email Security Checker
- Website Performance Checker

Each page must include:

- SEO-focused H1
- explanation
- free tool
- benefits
- how it works
- common problems
- FAQ
- CTA
- related articles
- internal links
- related tools

Do not create thin doorway pages.

Every page must contain genuinely useful unique content.

---

# 32. SOLUTION PAGES

Create:

- Small Businesses
- Freelancers
- Agencies
- Restaurants
- E-commerce
- Local Businesses

Each page should explain:

- their problem
- why website health matters
- how Presence helps
- relevant checks
- monitoring
- alerts
- reports
- CTA

---

# 33. PRICING

Plans:

FREE

STARTER

BUSINESS

AGENCY

Do not hard-code final prices if they are not finalized.

Example:

FREE

- 1 website
- Basic scan
- Basic report

STARTER

- Multiple websites
- Monitoring
- Alerts
- Detailed reports

BUSINESS

- More websites
- Advanced monitoring
- Advanced reports
- Team features

AGENCY

- Many websites
- Client reports
- White-label capability
- Team management

Include:

- monthly/yearly toggle
- annual savings
- feature comparison
- FAQ
- strong CTA

Pricing must be transparent.

---

# 34. BLOG

Create a premium integrated blog.

Categories:

- Security
- Performance
- SEO
- DNS
- Email Security
- SSL
- Website Management
- Digital Presence

Article pages include:

- title
- subtitle
- author
- publication date
- reading time
- category
- hero visual
- table of contents
- article body
- related tools
- CTA
- related articles
- newsletter/signup CTA

Every article should naturally lead toward a relevant Presence tool.

Example:

Article:

"How to fix SPF problems"

CTA:

"Check your email security"

---

# 35. HEADLESS CMS

Use WordPress as a separate headless CMS.

Architecture:

WordPress

↓

REST API

↓

Presence public frontend

↓

/blog

WordPress is the content management system only.

Do not expose duplicate indexable article versions.

Only the Presence public frontend article should be indexed.

---

# 36. SEO SYSTEM

Every public page must support:

- title
- meta description
- canonical
- Open Graph
- Twitter/X cards
- hreflang
- structured data
- breadcrumbs
- sitemap
- robots.txt

Languages:

- German
- English
- French

URL strategy:

/de/...

/en/...

/fr/...

Prioritize:

1. German
2. English
3. French

---

# 37. TECHNICAL SEO

Design must support:

- semantic HTML
- crawlable content
- SSR or SSG for SEO-critical public pages
- fast loading
- clean URLs
- internal linking
- image optimization
- accessible navigation
- sitemap
- canonical URLs
- hreflang

Do not rely exclusively on client-side JavaScript for SEO-critical content.

---

# 38. AI SEARCH / GEO STRATEGY

Do not implement fake "AI SEO hacks."

Optimize for:

- useful content
- clear information structure
- semantic HTML
- authoritative information
- original explanations
- internal linking
- fast pages
- crawlability
- structured data
- excellent UX

Content should directly answer questions users ask.

Examples:

"Why is my website slow?"

"How to fix an SSL certificate problem"

"What is SPF?"

"What is DMARC?"

"How to fix DNS problems"

"How to improve Core Web Vitals"

"Which security headers should a website have?"

"Why is my website unavailable?"

---

# 39. SEO CONTENT LOOP

Design around:

Problem

↓

Educational Article

↓

Free Tool

↓

Scan

↓

Report

↓

Signup

↓

Monitoring

↓

Subscription

This is a primary growth mechanism.

---

# 40. PRIVATE APPLICATION SHELL

Create a premium SaaS application shell.

Desktop sidebar:

- Dashboard
- Websites
- Scans
- Monitoring
- Alerts
- Reports

Secondary navigation:

- Settings
- Billing
- Account

Top bar:

- Search
- Notifications
- Help
- User menu

The shell must support:

- collapsed sidebar
- expanded sidebar
- responsive behavior
- active navigation
- keyboard navigation
- mobile navigation

---

# 41. APPLICATION DASHBOARD

Dashboard should immediately communicate website health.

Header:

"Good morning"

"Here's how your digital presence is doing."

Primary CTA:

"Run new scan"

Main KPI:

82 / 100

Website Health

Trend:

+6 from last week

Dashboard hierarchy:

1. Overall health
2. Critical problems
3. Website portfolio
4. Monitoring
5. Alerts
6. Recent scans
7. Reports

---

# 42. DASHBOARD KPI CARDS

Display:

- Websites
- Healthy websites
- Critical issues
- Uptime
- Recent scans

Example:

5 Websites

4 Healthy

3 Critical issues

99.98% Uptime

12 Recent scans

Use subtle sparklines.

Do not overload KPI cards with unnecessary decoration.

---

# 43. WEBSITE LIST

Display:

- Website
- Health
- Availability
- SSL
- Performance
- Last scan

Example:

example.com

92 Healthy

SSL ✓

Performance ✓

Scanned 5 min ago

Actions:

- View
- Scan
- Settings

Desktop may use a table.

Mobile should use a card/list representation.

---

# 44. WEBSITE DETAIL

Header:

example.com

92 / 100

Healthy

Actions:

- Scan now
- Monitoring
- Share report

Tabs:

- Overview
- Checks
- History
- Monitoring
- Alerts
- Reports

The header should remain useful on scroll.

---

# 45. WEBSITE OVERVIEW

Show:

- health score
- score trend
- check summary
- critical issues
- recent scan
- monitoring status
- uptime
- response time
- recommendations

Provide a clear "What should I do next?" section.

---

# 46. CHECKS

Display six core checks:

1. Availability
2. SSL
3. DNS
4. Email Security
5. Security Headers
6. Performance

Each check:

- status
- score
- last checked
- problem count
- details

Clicking opens detailed explanation.

---

# 47. CHECK DETAIL

Every technical check must use the same UX pattern:

STATUS

↓

What we found

↓

Why it matters

↓

Technical details

↓

Business impact

↓

How to fix

↓

Recommended action

Example:

SSL

✓ Healthy

Certificate valid for 78 days.

Technical details:

- Issuer
- Expiry
- TLS version
- Certificate chain

CTA:

"Learn how to fix SSL issues"

---

# 48. SCAN HISTORY

Create scan history page.

Columns:

- Date
- Website
- Score
- Change
- Status
- Duration

Allow:

- filter
- sort
- search
- compare scans
- open scan details

Example:

82 → 91

Show what changed.

---

# 49. SCAN COMPARISON

Create a dedicated comparison UX.

Compare:

- overall score
- each health dimension
- newly detected issues
- resolved issues
- changed technical values
- uptime
- performance

Use:

Improved

Regressed

Unchanged

New

Resolved

Avoid unnecessary visual complexity.

---

# 50. MONITORING

Create monitoring dashboard.

Show:

- current uptime
- 30-day uptime
- 90-day uptime
- response time
- incidents

Charts:

- uptime history
- response time
- status timeline

Configuration:

- monitoring frequency
- notification preferences
- pause monitoring

Make monitoring status immediately visible.

---

# 51. ALERTS

Create alerts center.

Categories:

- Critical
- Warning
- Resolved
- Informational

Examples:

- SSL certificate expires soon
- Website unavailable
- Performance degraded
- DNS changed
- Security header missing

Filters:

- All
- Critical
- Warning
- Resolved

Allow:

- acknowledge
- resolve
- open details
- configure alert

---

# 52. NOTIFICATIONS

Notification center supports:

- scan completed
- health score changed
- website down
- SSL expiration
- security issue
- performance degradation
- report ready

Channels:

- Email
- Browser
- In-app

Design unread/read states clearly.

---

# 53. REPORTS

Reports dashboard:

- Monthly reports
- Scan reports
- Monitoring reports

Actions:

- View
- Download PDF
- Share

Report design should feel professional enough to send directly to a client.

---

# 54. PUBLIC REPORT

Route concept:

/report/:publicId

Display:

- Website
- Health score
- Check results
- Issues
- Last scan
- Uptime

Footer:

"Powered by Presence"

CTA:

"Check your website for free"

This creates a referral/acquisition loop.

---

# 55. REPORT SHARING

Allow:

- Copy link
- Share
- Download PDF

Future agency capability:

- White-label reports

Design the architecture so white-labeling can be added later.

---

# 56. ONBOARDING

After registration:

"Welcome to Presence"

Step 1:

Add your website

Step 2:

Run your first scan

Step 3:

Enable monitoring

Step 4:

Configure alerts

Show:

1 / 4

Keep onboarding short.

The user should reach the first meaningful result as quickly as possible.

---

# 57. AUTHENTICATION

Create premium:

- Login
- Register
- Forgot password
- Reset password
- Email verification

Authentication methods:

- Email/password
- Google OAuth

Authentication should feel:

- fast
- trustworthy
- simple
- low-friction

Include:

- loading
- validation
- API error
- success
- password visibility
- verification state

---

# 58. SETTINGS

Sections:

- Profile
- Security
- Notifications
- Language
- Appearance
- Billing
- Subscription
- Integrations
- Privacy

Appearance:

- Light
- Dark
- System

Language:

- Deutsch
- English
- Français

---

# 59. BILLING

Billing dashboard:

- Current plan
- Monthly cost
- Next billing date
- Payment status

Actions:

- Upgrade
- Change plan
- Cancel subscription
- View invoices

Conceptually integrate with Stripe.

Stripe is the source of truth for payment state.

Do not create fake billing data in the final implementation.

---

# 60. ADMIN / GROWTH CENTER

Create a separate internal premium administration experience.

Sections:

- Growth overview
- Visitors
- Acquisition
- SEO
- Blog
- Conversion
- Revenue
- Advertising
- Privacy
- System

The Admin UI should be visually consistent with Presence but clearly distinguishable as internal tooling.

---

# 61. ADMIN OVERVIEW

Show:

- Visitors
- Scans
- Signups
- Customers
- MRR
- Conversion

Charts:

- traffic
- signups
- revenue
- scans

Include date range controls.

Examples:

Today

7 days

30 days

90 days

Custom

---

# 62. ANALYTICS ARCHITECTURE

Do NOT build a custom behavioral analytics engine.

Use self-hosted **Umami** for behavioral and marketing analytics.

Responsibilities:

### Umami

- page views
- sessions
- traffic sources
- behavioral events
- campaign attribution
- funnel behavior

### Django + PostgreSQL

- users
- websites
- scans
- application state
- product data
- business data

### Stripe

- subscriptions
- payment state
- revenue
- invoices

Never use Umami as the authoritative billing database.

---

# 63. UMAMI EVENTS

Track:

page_view

scan_started

scan_completed

report_viewed

cta_clicked

signup_started

signup_completed

pricing_viewed

checkout_started

subscription_created

subscription_cancelled

blog_article_viewed

share_report_clicked

Useful properties:

- language
- page
- plan
- traffic_source
- campaign
- website_type
- scan_score

Every major CTA should be trackable.

---

# 64. PRIMARY PRODUCT FUNNEL ANALYTICS

Design analytics around:

Visitor

↓

Landing

↓

Scanner started

↓

Scanner completed

↓

Report viewed

↓

Signup

↓

Website added

↓

Monitoring enabled

↓

Pricing viewed

↓

Checkout

↓

Customer

The Admin UI should make drop-off visible.

---

# 65. MARKETING ANALYTICS

Track:

- visitors
- sessions
- traffic sources
- organic traffic
- direct traffic
- referral traffic
- campaigns
- landing pages
- scanner usage
- signup conversion
- pricing conversion
- subscription conversion

Support:

utm_source

utm_medium

utm_campaign

utm_content

---

# 66. BUSINESS METRICS

When available, display:

- Visitors
- Scans
- Signups
- Active users
- Customers
- Conversion rate
- MRR
- ARR

Data sources:

Django + PostgreSQL = application/business source of truth

Stripe = billing/revenue source of truth

Umami = behavior/marketing analytics

Never mix these responsibilities.

---

# 67. ADVERTISING

Prepare UI for future:

- Google Ads
- Meta Ads
- LinkedIn Ads
- Reddit Ads

But advertising is not the initial acquisition priority.

Initial growth priorities:

1. SEO
2. Organic traffic
3. Free scanner
4. Content
5. Referral reports

---

# 68. DATA VISUALIZATION

Charts must communicate decisions.

Use:

- line charts
- area charts
- sparklines
- radial health score
- progress bars
- timelines
- status distributions

Avoid decorative charts.

Every chart should answer:

"What does this tell the user?"

Provide:

- clear labels
- useful tooltips
- empty state
- loading state
- error state
- accessible alternatives

---

# 69. GLOBAL SEARCH

Create global application search.

Search:

- Websites
- Scans
- Reports
- Alerts
- Settings

Use command-menu UX.

Keyboard:

⌘ / Ctrl + K

Support:

- recent searches
- keyboard navigation
- categories
- shortcuts
- empty results
- loading results

---

# 70. COMPONENT LIBRARY

Create reusable:

- Button
- Input
- Select
- Textarea
- Checkbox
- Radio
- Switch
- Card
- Badge
- Alert
- Toast
- Modal
- Drawer
- Bottom Sheet
- Tabs
- Table
- Dropdown
- Tooltip
- Popover
- Progress
- Score
- Chart
- Sparkline
- Timeline
- Skeleton
- EmptyState
- ErrorState
- Navbar
- Sidebar
- BottomNavigation
- Footer
- Breadcrumb
- CommandMenu
- DatePicker
- FilterBar
- SearchInput
- StatusIndicator

States:

- default
- hover
- active
- focus
- disabled
- loading
- error
- success
- selected

---

# 71. DOMAIN COMPONENTS

Create dedicated reusable Presence components:

HealthScore

CheckCard

CheckStatus

CheckSummary

FindingCard

RecommendationCard

ScanProgress

ScanStatus

WebsiteCard

WebsiteTable

MonitoringChart

UptimeChart

ResponseTimeChart

IncidentTimeline

AlertCard

ReportPreview

ReportHeader

ReportShare

MetricCard

TrendIndicator

SeverityBadge

TechnicalDetails

BusinessImpact

ActionCard

These components should be reusable across:

- public scanner
- application
- reports
- public reports
- admin

---

# 72. LOADING STATES

Every asynchronous operation must have a polished state.

Examples:

Scanner:

"Analyzing your website..."

Dashboard:

Skeleton cards

Reports:

Skeleton document

Charts:

Skeleton chart

Website:

Skeleton content

Never show a blank white screen.

Avoid excessive spinner-only loading states.

Prefer contextual skeletons and progress indicators.

---

# 73. EMPTY STATES

Examples:

No websites:

"Your digital presence starts here."

[ Add your first website ]

No scans:

"Run your first scan."

No alerts:

"You're all clear."

No reports:

"Your first report will appear here."

Every empty state should explain:

- what is empty
- why
- what to do next

---

# 74. ERROR STATES

Design:

- 404
- 500
- API error
- network error
- scan failed
- scan cancelled
- invalid URL
- website unreachable
- authentication failure
- payment failure
- permission error
- rate limit

Each error must explain:

1. What happened?
2. Why?
3. What can the user do?
4. Retry if appropriate.

Do not expose unnecessary technical stack traces.

Technical details may be expandable.

---

# 75. SUCCESS STATES

Design meaningful success states:

- scan completed
- website added
- monitoring enabled
- alert configured
- report generated
- report shared
- settings saved
- subscription updated

Use subtle confirmation.

Do not overuse celebratory animations.

---

# 76. MICRO-INTERACTIONS

Use subtle animations for:

- score animation
- scan progress
- chart transitions
- hover states
- button feedback
- skeleton loading
- toast notifications
- success states
- navigation
- modal transitions

Animations should feel:

- fast
- intentional
- premium

Avoid excessive motion.

---

# 77. MOTION ACCESSIBILITY

Support reduced motion.

If the user prefers reduced motion:

- remove unnecessary transitions
- avoid animated score counters
- simplify scan animation
- avoid parallax
- keep essential feedback visible

---

# 78. PWA

The private application must be PWA-ready.

Include:

- app manifest
- installability
- responsive navigation
- service worker
- offline fallback
- application icons
- install prompt
- mobile interactions

The application should feel like a native SaaS application.

---

# 79. OFFLINE UX

Design explicit offline states.

Example:

"You are offline."

Show:

- last available data
- connection status
- retry action

Never pretend stale data is live.

Clearly communicate:

"Last updated 8 minutes ago."

---

# 80. SECURITY VISUAL LANGUAGE

Presence is partially a cybersecurity product.

Security-related pages should feel:

- trustworthy
- technical
- precise
- professional

Avoid:

- hacker clichés
- neon green terminals
- skulls
- cyberpunk
- excessive dark aesthetics

Instead use:

- clean technical diagrams
- structured data
- professional indicators
- certificates
- domain information
- security scores
- clear explanations

---

# 81. TRUST SIGNALS

Use appropriate:

- Privacy-first messaging
- Security information
- Transparent pricing
- No-credit-card-required messaging
- Technical explanations
- Real scan results
- Public reports
- Monitoring history
- Professional documentation
- Contact/support

Never fabricate:

- customer logos
- reviews
- testimonials
- statistics
- security certifications
- market claims

---

# 82. GDPR / PRIVACY

Presence targets European users.

Design privacy-first.

Avoid unnecessary:

- tracking
- fingerprinting
- personal data collection
- invasive advertising
- session recording without appropriate legal basis

Provide:

- Privacy Policy
- Terms
- Cookie information where applicable
- Consent management where required

Use privacy-friendly analytics.

---

# 83. ACCESSIBILITY

Target WCAG 2.2 AA where practical.

Support:

- keyboard navigation
- visible focus
- semantic HTML
- sufficient contrast
- screen readers
- accessible forms
- useful error messages
- reduced motion
- logical heading hierarchy
- accessible charts
- accessible status indicators

Never communicate information through color alone.

---

# 84. INTERNATIONALIZATION

Support:

- German
- English
- French

Do not hard-code text into layouts.

Design for text expansion.

German may require longer labels.

French may require longer descriptions.

Buttons and navigation must survive translation.

Date, number and currency formats must be locale-aware.

---

# 85. FRONTEND ARCHITECTURE

Current authenticated application:

React

TypeScript

Tailwind CSS

Vite

Keep this architecture unless there is a strong technical reason to change it.

Public SEO-heavy website/blog should use an SSR/SSG-capable architecture such as Astro or another appropriate architecture.

Target architecture:

PUBLIC WEB

→ SEO / marketing / tools / blog

PRIVATE APP

→ React + TypeScript + Tailwind + PWA

BACKEND

→ Django REST Framework

DATABASE

→ PostgreSQL

QUEUE

→ Redis + Celery

CMS

→ Headless WordPress

ANALYTICS

→ Umami

BILLING

→ Stripe

---

# 86. API-FIRST DESIGN

The frontend must ultimately reflect the real backend.

Do not create production UI around invented API responses.

Do not create fake persistent data.

Use realistic mock data only during design/prototyping.

Clearly distinguish:

- mock data
- real API data
- loading
- error
- empty

The final implementation must use the actual backend contract.

TypeScript types should align with backend responses.

---

# 87. BACKEND SOURCE OF TRUTH

The design must respect the real domain model.

Core concepts include:

- User
- Website
- Scan
- ScannerRun
- CheckResult
- Finding
- Monitoring
- Alert
- Report

Do not invent contradictory domain concepts.

The UI should reflect real lifecycle states.

---

# 88. SCANNER UX ARCHITECTURE

The scanner experience should conceptually follow:

React

↓

Django API

↓

Scan Orchestrator

↓

Celery / Redis

↓

Scanner Engine

↓

Individual scanners

↓

Parsers / normalized findings

↓

ScannerRun / Finding / CheckResult

↓

Score Engine

↓

Recommendations

The interface should never imply that the browser itself performs the scan.

---

# 89. SCAN TYPES

Support the conceptual scan types:

HEALTH

SECURITY

FULL

HEALTH should be the default user-facing scan experience unless the backend specifies otherwise.

The UI should clearly communicate scan scope.

---

# 90. FINDINGS UX

Findings must be understandable.

Each finding can expose:

- severity
- title
- explanation
- affected URL/domain
- technical evidence
- business impact
- recommendation
- remediation guidance

Severity language:

- Informational
- Low
- Medium
- High
- Critical

Do not confuse:

Finding severity

with

Overall website health status.

---

# 91. HEALTH SCORE UX

Health score dimensions:

Website Availability — 20

SSL/TLS — 20

DNS — 15

Email Security — 15

Security Headers — 15

Performance — 15

Uptime is separate.

Always visually distinguish:

Health Score

from

Uptime.

---

# 92. RECOMMENDATIONS UX

Recommendations should answer:

"What should I fix first?"

Prioritize recommendations by:

1. Severity
2. Business impact
3. Ease of remediation
4. Dependency/order where relevant

Use language suitable for small-business owners.

Do not assume the user is a cybersecurity expert.

Allow technical details to be expanded.

---

# 93. TECHNICAL + BUSINESS DUAL LAYER

Every important technical issue should have two levels:

### Simple explanation

What happened and why the user should care.

### Technical details

The underlying technical information.

Example:

"Your SSL certificate is valid."

Then expandable:

Issuer

Expiration

TLS version

Certificate chain

This makes Presence useful for both:

- business owners
- developers
- agencies
- technical professionals

---

# 94. DESKTOP INFORMATION DENSITY

Desktop can use higher information density.

Use:

- tables
- side-by-side metrics
- multi-column layouts
- dense technical panels

But preserve hierarchy.

Do not make everything equally prominent.

---

# 95. MOBILE INFORMATION DENSITY

Mobile should prioritize:

1. health score
2. critical problems
3. websites
4. monitoring
5. alerts
6. recent scans
7. reports

Secondary technical details should be collapsible.

---

# 96. TABLE RESPONSIVENESS

Never simply overflow every desktop table.

For mobile, transform data into:

- cards
- compact list rows
- expandable details
- horizontal tables only when necessary

The user should never have to fight the interface.

---

# 97. FORMS

Forms must have:

- labels
- help text
- validation
- errors
- success
- disabled state
- loading state
- required indicators
- accessible focus

Avoid placeholder-only labels.

---

# 98. NOTIFICATION UX

Use:

- toast
- notification center
- contextual alerts

Toasts should not contain essential information that disappears immediately.

Critical information should persist in the relevant page.

---

# 99. COMMAND MENU

Command menu should support:

- global search
- navigation
- websites
- scans
- reports
- settings
- actions

Examples:

"Scan example.com"

"Open website"

"View latest report"

"Open settings"

Keyboard navigation must be excellent.

---

# 100. REPORT DESIGN SYSTEM

Reports should feel like professional documents.

Visual hierarchy:

- Presence branding
- website
- health score
- summary
- issues
- checks
- recommendations
- technical details
- monitoring
- timestamp

Reports must be usable:

- on screen
- as PDF
- when shared with clients

---

# 101. PUBLIC REPORT VIRAL LOOP

Public reports should naturally encourage:

"Check your website for free"

The report should demonstrate Presence value without feeling like aggressive advertising.

Keep branding visible but professional.

---

# 102. CONVERSION OPTIMIZATION

Every public page should have one clear primary CTA.

Avoid multiple competing CTAs.

Contextual CTA examples:

SEO article:

"Check your website's SEO"

Security article:

"Run a security scan"

SSL article:

"Check your SSL certificate"

Performance article:

"Test your website performance"

---

# 103. TRUST + CONVERSION BALANCE

Never sacrifice trust for conversion.

Do not:

- hide basic results
- use fake urgency
- use fake testimonials
- use misleading pricing
- use manipulative dark patterns

Instead:

- show real value
- explain clearly
- reduce friction
- communicate privacy
- provide transparent pricing

---

# 104. CORE WEB VITALS

Presence sells website performance.

Therefore Presence itself must be extremely fast.

Targets:

LCP < 2.5s

INP < 200ms

CLS < 0.1

Optimize:

- images
- fonts
- JavaScript
- bundles
- lazy loading
- code splitting
- caching
- responsive images
- CDN
- critical CSS

Avoid unnecessary JavaScript.

---

# 105. PERFORMANCE-FIRST DESIGN

Design must account for implementation performance.

Avoid:

- huge decorative images
- unnecessary video
- excessive animation
- enormous icon libraries
- unnecessary chart libraries
- huge client-side dependencies

Prefer:

- lightweight SVG
- optimized assets
- progressive loading
- component-level loading
- lazy-loaded secondary content

---

# 106. EXISTING FRONTEND MIGRATION RULE

The existing Presence frontend already contains functionality and pages.

Do NOT blindly replace everything.

First:

1. Analyze existing implementation.
2. Identify reusable components.
3. Identify existing routes.
4. Identify API integration.
5. Identify hard-coded data.
6. Identify missing states.
7. Identify UX problems.
8. Identify duplicated components.
9. Identify opportunities for refactoring.

Then:

10. Implement the design system.
11. Upgrade pages progressively.
12. Preserve working functionality.
13. Connect real API data.
14. Validate responsive behavior.
15. Validate accessibility.
16. Validate performance.

Never sacrifice working backend integration merely to achieve visual changes.

---

# 107. FIGMA → REACT MAPPING

The design must be implementation-ready.

Mapping:

Figma Components

→ React components

Figma Variables

→ design tokens / Tailwind tokens

Figma Variants

→ React props / variants

Figma Auto Layout

→ Flexbox / Grid

Figma responsive frames

→ responsive breakpoints

Figma states

→ component states

Figma typography tokens

→ typography system

Do not create monolithic React components.

---

# 108. COMPONENT ARCHITECTURE

Prefer:

components/

  ui/

  navigation/

  charts/

  forms/

  health/

  scans/

  monitoring/

  reports/

  alerts/

  websites/

pages/

features/

layouts/

hooks/

services/

types/

lib/

Keep business logic separate from visual components.

---

# 109. DESIGN HANDOFF REQUIREMENTS

Before implementation, every important screen should have:

- exact frame dimensions
- spacing
- typography
- component hierarchy
- component variants
- interaction states
- responsive behavior
- empty state
- loading state
- error state
- success state
- accessibility considerations

Do not leave critical interaction behavior implicit.

---

# 110. FIGMA MCP HANDOFF

Figma MCP will later be used to inspect the actual design.

Therefore:

The Figma design must be structured so MCP can identify:

- frames
- components
- component instances
- variants
- dimensions
- spacing
- typography
- colors
- variables
- auto layout
- hierarchy
- responsive variants

Do not create flattened screenshots instead of real components.

Do not hide the entire design inside one giant frame.

---

# 111. FIGMA MCP IMPLEMENTATION WORKFLOW

After the design phase:

1. Select the target Figma frame.
2. Copy the Figma link.
3. Use Figma MCP.
4. Inspect design context.
5. Inspect screenshot.
6. Inspect metadata.
7. Identify reusable components.
8. Compare with existing React components.
9. Map Figma tokens to frontend tokens.
10. Implement incrementally.
11. Compare rendered UI against Figma.
12. Fix visual discrepancies.
13. Validate responsive layouts.

The model should inspect the actual Figma design rather than inventing dimensions.

---

# 112. READ ACTUAL DESIGN — DO NOT GUESS

When Figma MCP is available:

Do not guess:

- dimensions
- spacing
- colors
- typography
- border radius
- shadows
- component hierarchy
- layout

Read them from Figma.

Use the Figma design as the visual source of truth.

---

# 113. PROTOTYPE FLOWS

Create interactive prototype flows for the most important journeys.

### Flow A — Acquisition

Landing

→ Scanner

→ Scan Progress

→ Result

→ Signup

### Flow B — Activation

Signup

→ Add Website

→ First Scan

→ Result

→ Monitoring

### Flow C — Monitoring

Dashboard

→ Website

→ Monitoring

→ Alert

→ Resolution

### Flow D — Conversion

Dashboard

→ Pricing

→ Upgrade

→ Billing

### Flow E — Referral

Website

→ Report

→ Share

→ Public Report

→ New Visitor

---

# 114. CRITICAL UX JOURNEY

The most important user journey is:

GOOGLE / AI SEARCH

↓

LANDING PAGE

↓

FREE SCANNER

↓

RESULT

↓

SIGNUP

↓

FIRST WEBSITE

↓

MONITORING

↓

VALUE

↓

UPGRADE

Design this journey exceptionally well.

---

# 115. FINAL USER EXPERIENCE

The complete experience should feel like:

"I enter my website."

↓

"Presence immediately tells me how healthy it is."

↓

"I understand the problems."

↓

"I understand the business impact."

↓

"I understand what to fix."

↓

"I create an account."

↓

"I add my website."

↓

"Presence monitors my website automatically."

↓

"I receive alerts."

↓

"I receive reports."

↓

"I can share reports with clients."

↓

"I eventually upgrade because Presence continuously provides value."

---

# 116. DO NOT DO

Do NOT:

- create a generic Bootstrap dashboard
- create a generic AI dashboard
- overuse gradients
- overuse glassmorphism
- use random illustrations
- use fake statistics
- use fake testimonials
- create meaningless charts
- hide all scan results behind registration
- overload the landing page
- create SEO doorway pages
- build custom analytics unnecessarily
- mix visual styles
- make the dashboard unnecessarily complicated
- use color alone for status
- create inaccessible interactions
- create desktop-only layouts
- fake backend states
- fake scan progress
- invent API fields
- invent unsupported features
- flatten Figma designs
- create giant monolithic components

---

# 117. PREMIUM DETAIL CHECKLIST

Pay special attention to:

- spacing
- typography
- hierarchy
- hover states
- focus states
- transitions
- loading states
- empty states
- error states
- responsive behavior
- data hierarchy
- charts
- forms
- validation
- accessibility
- mobile navigation
- technical detail presentation
- business impact explanations

The difference between a normal SaaS and a premium SaaS is often in these details.

---

# 118. DESIGN QUALITY BAR

The final product must feel:

PREMIUM

FAST

TRUSTWORTHY

TECHNICAL

SIMPLE

PROFESSIONAL

PRIVACY-FIRST

CONVERSION-FOCUSED

SEO-FIRST

MOBILE-FIRST

ACCESSIBLE

INTERNATIONALIZED

PRODUCTION-READY

---

# 119. FINAL DESIGN OUTPUT

Create a complete high-fidelity design system and interface covering:

## PUBLIC WEBSITE

1. Homepage
2. Features
3. Pricing
4. Free scanner
5. Scan progress
6. Scan result
7. Website checker
8. Website health checker
9. SEO checker
10. Security checker
11. SSL checker
12. DNS checker
13. Email security checker
14. Website performance checker
15. Solution pages
16. Blog
17. Blog article
18. Resources
19. About
20. Contact
21. Privacy
22. Terms

## AUTHENTICATION

23. Login
24. Register
25. Forgot password
26. Reset password
27. Email verification
28. Google OAuth

## ONBOARDING

29. Welcome
30. Add website
31. First scan
32. Enable monitoring
33. Configure alerts

## APPLICATION

34. Dashboard
35. Websites
36. Website detail
37. Checks
38. Check detail
39. Scan history
40. Scan comparison
41. Monitoring
42. Alerts
43. Notifications
44. Reports
45. Public report
46. Billing
47. Settings
48. Profile
49. Security
50. Notification settings
51. Appearance
52. Language

## ADMIN / GROWTH

53. Growth overview
54. Visitors
55. Acquisition
56. SEO
57. Blog analytics
58. Conversion
59. Revenue
60. Advertising
61. Privacy
62. System

---

# 120. REQUIRED DESIGN STATES

For every major screen create:

- Default
- Loading
- Empty
- Error
- Success
- Disabled
- Hover
- Focus
- Active
- Selected
- Mobile
- Desktop
- Light mode
- Dark mode

Where relevant also create:

- Offline
- Permission denied
- No access
- Rate limited
- Partial data
- Stale data

---

# 121. RESPONSIVE DELIVERABLES

Do not only create desktop screens.

Required:

### Public

Desktop + Mobile

### Authentication

Desktop + Mobile

### Onboarding

Desktop + Mobile

### Application

Desktop + Mobile

### Admin

Desktop + Mobile where appropriate

Tablet behavior may be represented through responsive rules rather than dedicated frames when appropriate.

---

# 122. DESIGN SYSTEM QUALITY CHECK

Before considering the design complete, verify:

### Brand

- Presence has a distinctive visual identity.

### Typography

- hierarchy is consistent
- metrics are readable
- technical values are clear

### Color

- semantic
- accessible
- consistent
- dark-mode compatible

### Components

- reusable
- variants defined
- states defined

### Layout

- consistent spacing
- responsive
- intentional hierarchy

### UX

- clear actions
- clear feedback
- no dead ends

### Accessibility

- keyboard
- focus
- contrast
- semantics
- reduced motion

### Mobile

- touch-friendly
- readable
- no unnecessary horizontal overflow

### Performance

- lightweight
- no unnecessary visual assets

### Internationalization

- German
- English
- French
- text expansion considered

---

# 123. FINAL PRODUCT QUALITY CHECK

Before declaring the design finished, ask:

1. Does Presence immediately communicate its value?
2. Can a visitor scan a website without friction?
3. Is the free result genuinely useful?
4. Is the conversion path natural?
5. Does the dashboard communicate health immediately?
6. Can a non-technical business owner understand problems?
7. Can a technical user access deeper details?
8. Is monitoring clearly differentiated from scanning?
9. Are alerts actionable?
10. Are reports professional enough to share with clients?
11. Does mobile feel intentionally designed?
12. Does dark mode feel native?
13. Are all major states designed?
14. Is accessibility considered?
15. Is SEO supported structurally?
16. Is the product fast by design?
17. Is privacy visible and credible?
18. Can Figma MCP inspect the design cleanly?
19. Can React components be mapped directly from Figma?
20. Does the entire experience feel like a premium European SaaS product?

---

# 124. FINAL INSTRUCTION

Do not stop at a visual mockup.

Create a coherent, production-oriented product design system and complete frontend experience.

The final Presence product should make the user immediately understand:

> "Presence tells me whether my website is healthy, secure, fast and reliable — and continuously watches it for me."

The design must combine:

PRODUCT CLARITY

+

PREMIUM VISUAL DESIGN

+

TECHNICAL CREDIBILITY

+

BUSINESS VALUE

+

CONVERSION

+

SEO

+

PERFORMANCE

+

PRIVACY

+

ACCESSIBILITY

+

MOBILE UX

+

SCALABLE COMPONENT ARCHITECTURE

+

IMPLEMENTATION READINESS

The result must not merely look beautiful.

It must be:

**DESIGN-SYSTEM READY**

**RESPONSIVE**

**ACCESSIBLE**

**SEO-FIRST**

**PERFORMANCE-FIRST**

**API-FIRST**

**Figma-MCP READY**

**REACT IMPLEMENTATION READY**

**PRODUCTION-ORIENTED**

and capable of becoming a genuinely competitive premium B2B SaaS product.