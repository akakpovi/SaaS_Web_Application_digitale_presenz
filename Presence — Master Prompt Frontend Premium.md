# PRESENCE — PREMIUM FRONTEND REDESIGN & PRODUCT DESIGN MASTER PROMPT

## 0. ROLE

You are a world-class product designer, UX/UI designer, SaaS architect and senior frontend engineer.

Redesign and upgrade the existing frontend of **Presence**, a premium B2B SaaS platform for monitoring, analyzing and improving the digital presence, security, performance and reliability of websites.

Do NOT create a generic dashboard template.

The final product must feel like a serious, premium, trustworthy European SaaS product comparable in quality and polish to products such as Linear, Stripe, Vercel, Raycast, Notion, Datadog and modern cybersecurity SaaS platforms — while maintaining its own visual identity.

The design must communicate:

- Trust
- Security
- Intelligence
- Technical excellence
- Simplicity
- Reliability
- Premium quality
- Professional B2B software
- European privacy-first positioning

The interface must be visually impressive without becoming noisy or overly decorative.

---

# 1. PRODUCT VISION

Presence is a complete digital-presence monitoring platform.

A customer enters a website URL and Presence analyzes:

1. Website availability
2. SSL / TLS
3. DNS
4. Email security
5. Security headers
6. Website performance
7. Uptime monitoring

The platform generates a deterministic **Website Health Score from 0–100**.

Health score weights:

- Website availability: 20
- SSL: 20
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

Presence should transform technical website problems into understandable business-oriented recommendations.

The user should always understand:

- What is wrong?
- Why does it matter?
- How serious is it?
- How can I fix it?
- What should I do next?

---

# 2. CORE BUSINESS FUNNEL

Design the entire product around this acquisition and conversion funnel:

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

The frontend must make this funnel obvious.

The main CTA throughout the public website should generally be:

"Check my website"

or

"Scan my website for free"

Secondary CTA:

"View pricing"

---

# 3. DESIGN PRINCIPLES

Use a premium modern SaaS design system.

Visual characteristics:

- Minimal
- Elegant
- Technical
- Clean
- High information density where appropriate
- Generous whitespace
- Excellent typography
- Subtle gradients
- Soft shadows
- Refined borders
- Smooth micro-interactions
- Strong visual hierarchy
- Excellent responsive behavior
- No excessive glassmorphism
- No childish illustrations
- No excessive rounded cards everywhere
- No generic AI-generated dashboard appearance

The product must look expensive.

Use restrained rounded corners, subtle elevation and consistent spacing.

Create a complete design system before designing individual pages.

---

# 4. BRAND DIRECTION

Create a distinctive Presence visual identity.

Possible visual concept:

"Digital health infrastructure for the modern web."

Use a sophisticated color system.

Primary brand color should communicate technology and trust.

Define semantic colors:

- Primary
- Secondary
- Success
- Warning
- Critical
- Info
- Neutral
- Background
- Surface
- Elevated surface
- Border
- Text primary
- Text secondary
- Muted text

Do not rely on color alone for status.

Every status must also use:

- icon
- label
- visual hierarchy

Example:

HEALTHY
✓ Healthy

WARNING
! Warning

CRITICAL
× Critical

NEUTRAL
— Not checked

---

# 5. TYPOGRAPHY

Use a premium modern sans-serif typography system.

Prioritize readability.

Typography hierarchy:

- Display
- H1
- H2
- H3
- H4
- Body large
- Body
- Body small
- Caption
- Label
- Metric
- Code / technical values

Numbers such as:

82
99.98%
€29
2.4s

must have strong visual hierarchy.

---

# 6. RESPONSIVE DESIGN

Design every screen for:

- Desktop
- Laptop
- Tablet
- Mobile

Do not simply shrink desktop layouts.

Mobile must be intentionally designed.

Dashboard mobile priority:

1. Health score
2. Critical problems
3. Websites
4. Monitoring
5. Alerts
6. Recent scans
7. Reports

Navigation should transform elegantly into a mobile navigation system.

---

# 7. DARK MODE

Support:

- Light
- Dark
- System

Dark mode should be a first-class design, not an inverted light theme.

Technical dashboards should look especially strong in dark mode.

---

# 8. PUBLIC WEBSITE STRUCTURE

Create a premium public website containing:

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

# 9. LANDING PAGE

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
[ https://example.com                         ]
[ Scan ]

Small reassurance:

"No credit card required."

---

# 10. HERO VISUAL

Instead of a generic stock illustration, show a premium interactive Website Health visualization.

Example:

Website Health

92 / 100

Healthy

Availability       ✓
SSL                ✓
DNS                ✓
Email Security     ✓
Security Headers   !
Performance        ✓

Include subtle animated data visualization.

---

# 11. TRUST SECTION

Immediately below hero:

"Everything you need to keep your website healthy."

Show six core checks:

Website
SSL
DNS
Email Security
Security Headers
Performance

Use elegant icons and concise explanations.

---

# 12. FREE WEBSITE SCANNER

Create a complete public scanner experience.

## Step 1 — URL INPUT

Large input:

"Enter your website URL"

CTA:

"Scan website"

Validate URL.

Show loading state.

---

# 13. SCAN PROGRESS

Create an impressive scanning interface.

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
- estimated state
- animated technical indicators
- reassuring messaging

Do not make it look like a hacker terminal.

Make it look like premium infrastructure software.

---

# 14. SCAN RESULT PAGE

Create a highly polished result page.

Header:

example.com

Website Health Score

92 / 100

Healthy

Show score prominently.

Use a circular or radial score visualization.

Below:

Availability        20/20
SSL                  20/20
DNS                  15/15
Email Security      13/15
Security Headers    15/15
Performance         9/15

---

# 15. PROBLEMS SECTION

Show:

"3 things need your attention"

Each issue should include:

- Severity
- Problem
- Explanation
- Business impact
- Recommended solution

Example:

CRITICAL

Missing Content-Security-Policy

"Your website is missing an important security header that can help reduce certain classes of attacks."

Buttons:

"Learn how to fix"

"View detailed report"

---

# 16. CONVERSION WALL

After giving meaningful free information, encourage registration.

Example:

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

Never hide the basic score behind registration.

Give enough value before asking for signup.

---

# 17. SEO LANDING PAGES

Create visually consistent SEO-focused pages for:

Website Checker
Website Health Checker
SEO Checker
Security Checker
SSL Checker
DNS Checker
Email Security Checker
Website Performance Checker

Each page must contain:

- SEO-focused H1
- Explanation
- Free tool
- Benefits
- How it works
- Common problems
- FAQ
- CTA
- Related articles
- Internal links
- Related tools

Do not create thin doorway pages.

Each page must provide unique, genuinely useful content.

---

# 18. SOLUTION PAGES

Create dedicated pages for:

Small Businesses
Freelancers
Agencies
Restaurants
E-commerce
Local Businesses

Each should explain:

- Their problem
- Why website health matters
- How Presence helps
- Relevant checks
- Monitoring
- Alerts
- Reports
- CTA

---

# 19. PRICING PAGE

Create a premium SaaS pricing page.

Plans:

FREE
STARTER
BUSINESS
AGENCY

Do not hard-code final prices if they are not yet finalized.

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

Monthly / yearly toggle.

Highlight annual savings.

Include FAQ.

Strong CTA.

---

# 20. BLOG

Create a premium integrated blog.

Blog categories:

Security
Performance
SEO
DNS
Email Security
SSL
Website Management
Digital Presence

Article pages should include:

- Title
- Subtitle
- Author
- Publication date
- Reading time
- Category
- Hero visual
- Table of contents
- Article body
- Related tools
- CTA
- Related articles
- Newsletter/signup CTA

Every article should naturally lead users toward relevant Presence tools.

Example:

Article:
"How to fix SPF problems"

CTA:

"Check your email security"

---

# 21. CMS ARCHITECTURE

Use WordPress as a separate headless CMS.

Architecture:

WordPress
↓
REST API
↓
Public Presence frontend
↓
/blog

WordPress is only the content management system.

Do not expose duplicate indexable versions of articles.

Only the Presence public frontend version should be indexed.

---

# 22. SEO SYSTEM

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

Support:

German
English
French

URL strategy:

/de/...
/en/...
/fr/...

Prioritize German, then English, then French.

---

# 23. TECHNICAL SEO

Design and architecture must support:

- semantic HTML
- crawlable content
- server-side rendering or static generation for public pages
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

# 24. CORE WEB VITALS

The Presence frontend itself must be extremely fast.

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

Presence sells website performance, so the Presence website must itself demonstrate excellent performance.

---

# 25. PRIVATE APPLICATION

Create a premium SaaS application shell.

Desktop:

LEFT SIDEBAR
- Dashboard
- Websites
- Scans
- Monitoring
- Alerts
- Reports

BOTTOM:
- Settings
- Billing
- Account

Top bar:

- Search
- Notifications
- Help
- User menu

---

# 26. DASHBOARD

Dashboard should immediately communicate website health.

Header:

"Good morning"

"Here's how your digital presence is doing."

Primary CTA:

"Run new scan"

Main KPI:

82 / 100
Website Health

Show trend:

+6 from last week

---

# 27. DASHBOARD KPI CARDS

Display:

Websites
Healthy websites
Critical issues
Uptime
Recent scans

Example:

5 Websites
4 Healthy
3 Critical issues
99.98% Uptime
12 Recent scans

Use subtle sparklines.

---

# 28. WEBSITE LIST

Display:

Website
Health
Availability
SSL
Performance
Last scan

Example:

example.com
92 Healthy
SSL ✓
Performance ✓
Scanned 5 min ago

Actions:

View
Scan
Settings

---

# 29. WEBSITE DETAIL PAGE

Header:

example.com

92 / 100

Healthy

Actions:

Scan now
Monitoring
Share report

Tabs:

Overview
Checks
History
Monitoring
Alerts
Reports

---

# 30. CHECKS PAGE

Display six checks:

Availability
SSL
DNS
Email Security
Security Headers
Performance

Each check:

Status
Score
Last checked
Problem count
Details

Clicking opens a detailed explanation.

---

# 31. CHECK DETAIL

Each technical check must use the same UX pattern:

STATUS

What we found

Why it matters

Technical details

Business impact

How to fix

Recommended action

Example:

SSL

✓ Healthy

Certificate valid for 78 days.

Technical details:
Issuer
Expiry
TLS version
Certificate chain

CTA:

"Learn how to fix SSL issues"

---

# 32. MONITORING

Create monitoring dashboard:

Current uptime
30-day uptime
90-day uptime
Response time
Incidents

Chart:

Uptime history

Response time chart.

Status timeline.

Allow configuration:

Monitoring frequency
Notification preferences
Pause monitoring

---

# 33. ALERTS

Create alerts center.

Categories:

Critical
Warning
Resolved
Informational

Examples:

SSL certificate expires soon
Website unavailable
Performance degraded
DNS changed
Security header missing

Filters:

All
Critical
Warning
Resolved

---

# 34. NOTIFICATIONS

Notification center should support:

- scan completed
- health score changed
- website down
- SSL expiration
- security issue
- performance degradation
- report ready

Support:

Email
Browser
In-app

---

# 35. SCAN HISTORY

Create scan history page.

Columns:

Date
Website
Score
Change
Status
Duration

Allow:

Compare scans

Example:

82 → 91

Show what changed.

---

# 36. REPORTS

Reports dashboard:

Monthly reports
Scan reports
Monitoring reports

Actions:

View
Download PDF
Share

---

# 37. PUBLIC REPORTS

Create shareable reports:

/report/:publicId

Display:

Website
Health score
Check results
Issues
Last scan
Uptime

Footer:

"Powered by Presence"

CTA:

"Check your website for free"

This creates a viral acquisition loop.

---

# 38. REPORT SHARING

Allow:

Copy link
Share
Download PDF

For agencies eventually:

White-label reports.

---

# 39. ONBOARDING

After registration:

Welcome to Presence

Step 1:
Add your website

Step 2:
Run your first scan

Step 3:
Enable monitoring

Step 4:
Configure alerts

Show progress:

1 / 4

Keep onboarding short.

---

# 40. AUTHENTICATION

Create premium:

Login
Register
Forgot password
Reset password
Email verification

Support:

Email/password
Google OAuth

Make authentication extremely simple.

---

# 41. SETTINGS

Sections:

Profile
Security
Notifications
Language
Appearance
Billing
Subscription
Integrations
Privacy

Appearance:

Light
Dark
System

Language:

Deutsch
English
Français

---

# 42. BILLING

Create billing dashboard:

Current plan
Monthly cost
Next billing date
Payment status

Actions:

Upgrade
Change plan
Cancel subscription
View invoices

Integrate conceptually with Stripe.

Stripe is the source of truth for payment state.

---

# 43. ANALYTICS — UMAMI

Do not build a custom analytics engine.

Use self-hosted **Umami**.

Track public website and application behavior.

Events:

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

language
page
plan
traffic_source
campaign
website_type
scan_score

---

# 44. PRIMARY PRODUCT FUNNEL

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

Every major CTA should be trackable.

---

# 45. MARKETING ANALYTICS

Track:

Visitors
Sessions
Traffic sources
Organic traffic
Direct traffic
Referral traffic
Campaigns
Landing pages
Scanner usage
Signup conversion
Pricing conversion
Subscription conversion

Support UTM parameters:

utm_source
utm_medium
utm_campaign
utm_content

---

# 46. BUSINESS METRICS

The frontend should display business data when available:

Visitors
Scans
Signups
Active users
Customers
Conversion rate
MRR
ARR

But:

Django + PostgreSQL = application/business source of truth

Stripe = billing/revenue source of truth

Umami = behavior/marketing analytics

Never use analytics as the authoritative billing database.

---

# 47. ADMIN / GROWTH CENTER

Create an internal premium admin dashboard:

Overview
Visitors
Acquisition
SEO
Blog
Conversion
Revenue
Advertising
Privacy
System

Overview:

Visitors
Scans
Signups
Customers
MRR
Conversion

Charts:

Traffic
Signups
Revenue
Scans

---

# 48. ADVERTISING

Prepare the UI for future:

Google Ads
Meta Ads
LinkedIn Ads
Reddit Ads

But do not make advertising the initial acquisition strategy.

Initial priority:

SEO
Organic traffic
Free scanner
Content
Referral reports

---

# 49. GDPR / PRIVACY

Presence targets European users.

Design privacy-first.

Avoid unnecessary:

- tracking
- fingerprinting
- personal data collection
- session recording without appropriate legal basis
- invasive advertising

Provide:

Privacy Policy
Terms
Cookie information where applicable
Consent management where required

Use privacy-friendly analytics.

---

# 50. ACCESSIBILITY

Target WCAG 2.2 AA where practical.

Support:

- keyboard navigation
- visible focus states
- semantic HTML
- sufficient contrast
- screen readers
- accessible forms
- error messages
- reduced motion

Never communicate information through color alone.

---

# 51. MICRO-INTERACTIONS

Use subtle animations:

- score animation
- progress animation
- chart transitions
- hover states
- button feedback
- skeleton loading
- toast notifications
- success states
- scan progress

Animations should feel fast and premium.

Avoid excessive animations.

---

# 52. LOADING STATES

Every asynchronous operation needs a polished state.

Examples:

Scanner:
"Analyzing your website..."

Dashboard:
Skeleton cards

Reports:
Skeleton document

Charts:
Skeleton chart

Never show blank white screens.

---

# 53. ERROR STATES

Design:

404
500
API error
Network error
Scan failed
Invalid URL
Website unreachable
Authentication failure
Payment failure

Each must explain:

What happened
What can the user do?

---

# 54. EMPTY STATES

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

---

# 55. COMPONENT LIBRARY

Create reusable components:

Button
Input
Select
Textarea
Card
Badge
Alert
Toast
Modal
Drawer
Tabs
Table
Dropdown
Tooltip
Progress
Score
Chart
Sparkline
Timeline
Skeleton
EmptyState
ErrorState
Navbar
Sidebar
Footer
Breadcrumb
Command menu

Create consistent states:

default
hover
active
focus
disabled
loading
error
success

---

# 56. DESIGN TOKENS

Define:

Colors
Spacing
Radius
Typography
Shadows
Borders
Transitions
Breakpoints
Z-index
Container widths

Everything must be reusable.

---

# 57. ICONOGRAPHY

Use one coherent icon system.

Icons should be:

- minimal
- technical
- recognizable
- consistent

Do not mix multiple icon styles.

---

# 58. DATA VISUALIZATION

Charts should be simple and meaningful.

Use:

- line charts
- area charts
- sparklines
- radial score
- progress bars
- timelines
- status distributions

Avoid decorative charts without business value.

---

# 59. SECURITY VISUAL LANGUAGE

Presence is partially a cybersecurity product.

Security-related pages should feel trustworthy and technical.

But avoid:

- hacker clichés
- neon green terminal aesthetics
- skulls
- excessive dark cyberpunk visuals

Instead use:

- clean technical diagrams
- structured data
- professional security indicators
- certificates
- domain information
- security scores

---

# 60. PWA

The private application must be PWA-ready.

Include:

- app manifest
- installability
- responsive navigation
- service worker
- offline fallback
- application icons
- install prompt
- mobile-friendly interactions

The application should feel like a native SaaS application.

---

# 61. SEARCH

Create global application search.

Allow users to search:

Websites
Scans
Reports
Alerts
Settings

Use command-menu style UX.

Keyboard shortcut:

⌘ / Ctrl + K

---

# 62. FRONTEND ARCHITECTURE

Current application:

React
TypeScript
Tailwind CSS
Vite

Keep this architecture for the authenticated application unless there is a strong technical reason to change it.

Public SEO-heavy website/blog should use an SSR/SSG-capable architecture such as Astro or another appropriate framework.

The final architecture should be:

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

# 63. SEO + AI SEARCH STRATEGY

Do not implement fake "AI SEO hacks".

Optimize for:

- useful content
- clear structure
- semantic HTML
- authoritative information
- original explanations
- internal linking
- fast pages
- crawlability
- structured data
- strong UX

Content should answer real questions users ask.

Example article topics:

"Why is my website slow?"
"How to fix an SSL certificate problem"
"What is SPF?"
"What is DMARC?"
"How to fix DNS problems"
"How to improve Core Web Vitals"
"Which security headers should a website have?"
"Why is my website unavailable?"

Every article should connect naturally to a Presence tool.

---

# 64. SEO CONTENT LOOP

Design the platform around:

Problem
↓
Educational article
↓
Free tool
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

This is the primary growth mechanism.

---

# 65. CONVERSION OPTIMIZATION

Every public page should have:

One clear primary CTA.

Avoid multiple competing CTAs.

Use contextual CTAs.

Example:

SEO article
→ "Check your website's SEO"

Security article
→ "Run a security scan"

SSL article
→ "Check your SSL certificate"

Performance article
→ "Test your website performance"

---

# 66. TRUST SIGNALS

Include appropriate:

- Privacy-first messaging
- Security information
- Transparent pricing
- No-credit-card-required message for free scanner
- Technical explanations
- Real scan results
- Public reports
- Monitoring history
- Professional documentation
- Contact/support

Do not fabricate customer logos, reviews or statistics.

---

# 67. PREMIUM DETAIL

Pay special attention to:

- spacing
- typography
- hover states
- transitions
- loading states
- empty states
- responsive behavior
- data hierarchy
- charts
- forms
- error handling
- accessibility

The difference between a normal SaaS and a premium SaaS is often in these details.

---

# 68. DO NOT DO

Do NOT:

- create a generic Bootstrap dashboard
- overuse gradients
- overuse glassmorphism
- use random illustrations
- use fake statistics
- use fake testimonials
- create meaningless charts
- hide all scan results behind registration
- overload the landing page
- create SEO doorway pages
- build a custom analytics system unnecessarily
- mix inconsistent visual styles
- make the dashboard unnecessarily complicated

---

# 69. FINAL USER EXPERIENCE

The complete experience should feel like:

"I enter my website."

↓

"Presence immediately tells me how healthy it is."

↓

"I understand the problems."

↓

"I understand what to fix."

↓

"I create an account."

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

# 70. FINAL DESIGN OUTPUT

Generate a complete high-fidelity design system and interface covering:

PUBLIC WEBSITE

1. Homepage
2. Features
3. Pricing
4. Free scanner
5. Scan progress
6. Scan result
7. Website checker
8. SEO checker
9. Security checker
10. SSL checker
11. DNS checker
12. Email security checker
13. Performance checker
14. Solution pages
15. Blog
16. Blog article
17. About
18. Contact
19. Privacy
20. Terms

AUTHENTICATION

21. Login
22. Register
23. Forgot password
24. Reset password
25. Email verification
26. Google OAuth

ONBOARDING

27. Welcome
28. Add website
29. First scan
30. Enable monitoring
31. Configure alerts

APPLICATION

32. Dashboard
33. Websites
34. Website detail
35. Checks
36. Check detail
37. Scan history
38. Scan comparison
39. Monitoring
40. Alerts
41. Notifications
42. Reports
43. Public report
44. Billing
45. Settings
46. Profile
47. Security
48. Notifications settings
49. Appearance
50. Language

ADMIN / GROWTH

51. Growth overview
52. Visitors
53. Acquisition
54. SEO
55. Blog analytics
56. Conversion
57. Revenue
58. Advertising
59. Privacy
60. System

Also create:

- responsive variants
- light mode
- dark mode
- component library
- design tokens
- loading states
- empty states
- error states
- success states
- hover states
- mobile navigation
- desktop navigation
- accessibility states

---

# 71. IMPORTANT IMPLEMENTATION RULE

The existing Presence frontend already contains functionality and pages.

Do NOT blindly replace everything.

First analyze the existing implementation and preserve useful existing functionality.

Then:

1. Identify reusable components.
2. Identify existing routes.
3. Identify existing API integration.
4. Identify hard-coded data.
5. Identify missing states.
6. Identify UX problems.
7. Refactor where appropriate.
8. Implement the new design system.
9. Upgrade pages progressively.
10. Ensure existing functionality continues working.

Never sacrifice working backend integration merely to achieve visual changes.

---

# 72. FINAL QUALITY BAR

The final result must look like a product that could realistically be launched as a premium European B2B SaaS in 2026.

It should feel:

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

The most important screen is not the dashboard.

The most important user journey is:

GOOGLE / AI SEARCH
→ LANDING PAGE
→ FREE SCANNER
→ RESULT
→ SIGNUP
→ FIRST WEBSITE
→ MONITORING
→ VALUE
→ UPGRADE

Design that journey exceptionally well.

The final interface should make the user immediately understand:

"Presence tells me whether my website is healthy, secure, fast and reliable — and continuously watches it for me."

Do not stop at a visual mockup.

Create a coherent, production-oriented product design system and complete frontend experience.