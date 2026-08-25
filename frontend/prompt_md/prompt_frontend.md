Create a complete production-ready SaaS web application UI/UX in Figma for a product called:

============================================================
PRESENCE
============================================================

Tagline:

"Your digital presence, under control."

Product description:

Presence is a modern SaaS platform designed specifically for small businesses to monitor and improve their digital presence from one simple dashboard.

Presence helps small businesses monitor:

- Website availability
- Website performance
- SSL certificate
- Domain and DNS configuration
- Email security configuration
- Security-related HTTP headers
- Uptime
- Online reviews
- Digital health score
- Alerts and incidents
- Reports

The target customers are non-technical small business owners.

Target businesses:

- Restaurants
- Cafés
- Barbershops
- Hair salons
- Beauty salons
- Hotels
- Auto repair shops
- Freelancers
- Small agencies
- Real estate agents
- Local businesses
- Professional services
- Small retailers

============================================================
IMPORTANT PRODUCT POSITIONING
============================================================

Presence is NOT a developer-oriented cybersecurity dashboard.

Presence is a simple "digital health" and monitoring product for business owners.

The user should understand the state of their digital presence within 30 seconds.

The product must communicate:

"We monitor your digital presence so you don't have to."

The user should immediately understand:

- What is healthy?
- What needs attention?
- What should I do?
- When was it checked?

Avoid unnecessary technical jargon.

Technical details should only appear when the user explicitly opens:

"Technical details"

For example:

Instead of:

"HTTP 503"

Display:

"Your website is temporarily unavailable."

Then provide:

"Technical details"

Instead of:

"DMARC p=none"

Display:

"Email protection needs improvement."

Then provide:

"Technical details"

============================================================
CRITICAL FIGMA ORGANIZATION REQUIREMENT
============================================================

DO NOT create the entire project as one giant Figma page.

This is a production SaaS design system and must be organized into multiple clearly named Figma pages.

Create the following Figma pages:

01 - Cover
02 - Brand
03 - Design System
04 - Variables
05 - Components
06 - Icons
07 - Landing
08 - Authentication
09 - Onboarding
10 - Dashboard Desktop
11 - Monitoring Desktop
12 - Website Details Desktop
13 - Alerts Desktop
14 - Reports Desktop
15 - Reviews Desktop
16 - Settings Desktop
17 - Pricing
18 - PWA Mobile
19 - PWA States
20 - Responsive
21 - Prototype

Each page must contain only the relevant designs.

Use consistent component references across pages.

Do not duplicate components unnecessarily.

Use Figma components, variants, variables and Auto Layout extensively.

============================================================
PRODUCT ARCHITECTURE
============================================================

Design Presence as one product with two primary experiences:

1. Web application
2. Installed Progressive Web App (PWA)

Both experiences must share:

- Same brand
- Same design system
- Same colors
- Same typography
- Same components
- Same icons
- Same UX principles
- Same information architecture where appropriate

Conceptually:

                    PRESENCE
                        |
              +---------+---------+
              |                   |
             WEB                 PWA
              |                   |
              +---------+---------+
                        |
                     API
                        |
                    Backend

The Figma design must therefore avoid creating two completely different products.

The PWA is the mobile-first application experience of the same Presence product.

============================================================
01 - COVER
============================================================

Create a professional Figma cover page.

Include:

Presence logo

Presence

"Your digital presence, under control."

Subtitle:

"Digital presence monitoring for small businesses."

Include a small product description:

"Website monitoring, SSL, DNS, email security, uptime, reviews and alerts — in one simple dashboard."

Show a subtle preview of:

Desktop dashboard
Mobile PWA dashboard

Do not overload the cover.

============================================================
02 - BRAND
============================================================

Create the complete Presence brand system.

Brand name:

Presence

Main tagline:

"Your digital presence, under control."

Alternative tagline:

"One simple dashboard for your digital presence."

Secondary message:

"We monitor your digital presence so you don't have to."

Create:

- Full logo
- Icon logo
- App icon
- Favicon
- PWA icon

Logo concept:

Combine one or more of:

- Checkmark
- Shield
- Globe
- Website window
- Presence/status indicator

The logo must work on:

- White background
- Light background
- Dark background

Create brand usage examples.

============================================================
03 - DESIGN SYSTEM
============================================================

Create a complete SaaS design system.

Typography:

Use Inter or another modern, highly readable sans-serif.

Create:

- Display
- H1
- H2
- H3
- Body Large
- Body
- Body Small
- Caption
- Label
- Button

Color system:

Primary:
Deep blue / Indigo

Success:
Green

Warning:
Amber

Critical:
Red

Neutral:
White
Light gray
Medium gray
Dark gray

Suggested semantic colors:

Primary:
#4F46E5

Success:
#16A34A

Warning:
#F59E0B

Critical:
#DC2626

Refine these colors if necessary to create a polished European SaaS aesthetic.

Do not use colors excessively.

Colors should communicate:

- Hierarchy
- Status
- Importance
- Actions

Create spacing system:

4px / 8px based spacing system.

Create:

- Border radius
- Shadows
- Borders
- Grid
- Containers
- Breakpoints

Use generous spacing.

Use subtle shadows.

Avoid excessive rounded cards.

============================================================
04 - VARIABLES
============================================================

Create Figma variables for:

Colors
Typography
Spacing
Radius
Shadows
Borders
Breakpoints
Status

Use semantic variable naming.

Examples:

color/primary
color/success
color/warning
color/critical
color/background
color/surface
color/text-primary
color/text-secondary

Create variables that can easily be mapped later to:

React
TypeScript
Tailwind CSS

============================================================
05 - COMPONENTS
============================================================

Create a reusable component library.

Components:

Buttons
Inputs
Selects
Checkboxes
Radio buttons
Cards
KPI cards
Score cards
Status badges
Alerts
Tables
Website cards
Charts
Navigation
Sidebar
Bottom navigation
Header
Modal
Toast
Tooltip
Tabs
Accordion
Avatar
Dropdown
Language selector
Pricing cards
Feature cards
Notification cards
PWA install banner
PWA notification permission modal
Offline banner
Sync indicator

Each component must have variants:

Default
Hover
Active
Disabled
Loading
Success
Warning
Error

Use component properties and variants.

Do not create separate unrelated components for visually identical elements.

============================================================
06 - ICONS
============================================================

Create or use a consistent icon style.

Icons should be:

- Simple
- Modern
- Consistent
- Professional
- Accessible

Use icons for:

Website
SSL
DNS
Email
Performance
Uptime
Reviews
Reports
Alerts
Settings
Notifications
Users
Business
Mobile
PWA
Install
Offline
Sync

Do not mix multiple icon styles.

============================================================
07 - LANDING
============================================================

Create a complete responsive SaaS marketing website.

Sections:

1. Navigation
2. Hero
3. Trust
4. How it works
5. Digital Health Score
6. Features
7. Monitoring
8. Dashboard preview
9. PWA section
10. Pricing
11. FAQ
12. Final CTA
13. Footer

Desktop width:

1440px

Also create responsive versions later in the Responsive page.

------------------------------------------------------------
LANDING NAVIGATION
------------------------------------------------------------

Logo:

Presence

Navigation:

Features
How it works
Pricing
FAQ

Right:

Language selector
Log in
Get started

Primary CTA:

"Get started"

------------------------------------------------------------
HERO
------------------------------------------------------------

Headline:

"Your digital presence, always under control."

Subheadline:

"Monitor your website, SSL, domain, email security and online reputation from one simple dashboard."

Domain scanner:

[ yourwebsite.com ]

[ Check for free ]

Primary CTA:

"Check my website"

Secondary CTA:

"See how it works"

Text:

"No credit card required."

Show a polished dashboard preview.

Preview content:

Digital Health Score

82 / 100

Website
Healthy

SSL
Healthy

DNS
Healthy

Email security
Needs attention

Reviews
4.7 ★

Uptime
99.98%

------------------------------------------------------------
TRUST SECTION
------------------------------------------------------------

Create a subtle trust section.

Target categories:

Restaurants
Retail
Services
Freelancers
Agencies
Local businesses

Do NOT invent fake company logos.

Do NOT create fake testimonials presented as real.

If testimonials are needed, clearly label them as placeholder content.

------------------------------------------------------------
HOW IT WORKS
------------------------------------------------------------

Three steps:

1. Add your website

"Enter your domain."

2. Get your health score

"See what is healthy and what needs attention."

3. Get notified

"Presence monitors your website automatically."

Use three connected cards.

------------------------------------------------------------
DIGITAL HEALTH SCORE
------------------------------------------------------------

Headline:

"One score. Everything you need to know."

Display:

82 / 100

Status:

Good

Breakdown:

Website
20 / 20

SSL
20 / 20

DNS
15 / 15

Email security
10 / 15

Security headers
9 / 15

Performance
8 / 15

Explanation:

"Your digital presence is healthy overall, with a few recommended improvements."

IMPORTANT:

Never present the Digital Health Score as a cybersecurity certification.

------------------------------------------------------------
FEATURES
------------------------------------------------------------

Create feature cards for:

Website Monitoring

"Know immediately when your website becomes unavailable."

SSL Monitoring

"Get notified before your certificate expires."

DNS Monitoring

"Detect important changes to your domain configuration."

Email Security

"Check SPF, DKIM and DMARC configuration."

Performance Monitoring

"Track website response time and uptime."

Security Headers

"Identify missing or weak security-related headers."

Uptime Monitoring

"Track your website availability over time."

Online Reviews

"Monitor customer ratings and reviews."

Automatic Reports

"Receive clear reports without technical jargon."

Alerts

"Get notified when something needs your attention."

------------------------------------------------------------
PWA MARKETING SECTION
------------------------------------------------------------

Headline:

"Presence, wherever you are."

Description:

"Install Presence on your phone or computer and stay informed about your digital presence wherever you work."

Show:

- Smartphone mockup
- PWA dashboard
- Push notification
- Website status
- Alert
- Digital Health Score

CTA:

"Install Presence"

Secondary:

"Learn about the PWA"

Do not claim unsupported features.

------------------------------------------------------------
PRICING PREVIEW
------------------------------------------------------------

Show:

FREE
€0/month

PRO
€5.99/month

BUSINESS
€14.99/month

Use the full pricing design in the Pricing page.

------------------------------------------------------------
FAQ
------------------------------------------------------------

Questions:

"What does Presence monitor?"

"Do I need technical knowledge?"

"Does Presence change my website?"

"How often is my website checked?"

"What happens if my website goes offline?"

"Can I monitor multiple websites?"

"Can I install Presence as an app?"

"Can I cancel anytime?"

"Is my data secure?"

Use accordion components.

============================================================
08 - AUTHENTICATION
============================================================

Create:

Login
Register
Forgot password
Reset password
Email verification

Optional:

Continue with Google

All authentication screens must include:

Language selector

Presence logo

Simple clean layout

============================================================
09 - ONBOARDING
============================================================

Create a 4-step onboarding.

Step 1:

"Tell us about your business"

Fields:

Business name
Industry
Country

Step 2:

"Add your website"

[ example.com ]

Step 3:

"We're checking your website..."

Animated states:

Checking website...
Checking SSL...
Checking DNS...
Checking email security...
Checking security headers...
Checking performance...
Calculating your score...

Step 4:

"Your first report is ready."

Score:

82 / 100

CTA:

"Open dashboard"

Create mobile-friendly onboarding.

============================================================
10 - DASHBOARD DESKTOP
============================================================

Desktop:

1440px

Structure:

Left sidebar
Top header
Main content

Sidebar:

Presence logo

Overview
Websites
Monitoring
Reviews
Reports
Alerts

Settings

Bottom:

Help
Account

Top header:

Page title
Search
Notifications
Language selector
User avatar

Main:

"Good morning"

"Here's the health of your digital presence."

KPI cards:

Digital Health Score
82 / 100

Websites
3

Uptime
99.98%

Open issues
2

Website list:

Website
Status
Health
Uptime
SSL
Last check

Example:

example.de
Online
92 / 100
99.99%
Valid
2 min ago

example.com
Online
82 / 100
99.98%
Valid
5 min ago

example-shop.de
Needs attention
64 / 100
98.91%
Expires soon
3 min ago

============================================================
11 - MONITORING DESKTOP
============================================================

Show:

Monitoring active

Check frequency:

Every hour

Monitored:

3 websites

Uptime:

99.98%

Create chart.

Periods:

24H
7D
30D
90D

Timeline:

08:00
Online

09:00
Online

10:00
Online

11:00
Offline

11:04
Online

============================================================
12 - WEBSITE DETAILS DESKTOP
============================================================

Header:

example.de

🟢 Online

Last checked:

2 minutes ago

Actions:

Run check
Settings

Score:

82 / 100

Status:

Good

Sections:

Website availability
SSL certificate
DNS
Email security
Security headers
Performance
Reviews

Each section contains:

Status
Score
Last checked
Simple explanation
Recommended action

Example:

SSL Certificate

🟢 Healthy

Valid until:

14 September 2026

"Your SSL certificate is valid."

Example:

Email protection

🟠 Needs attention

"Your email protection configuration could be improved."

Collapsed section:

"Technical details"

Technical information should remain hidden by default.

============================================================
13 - ALERTS DESKTOP
============================================================

Create an alerts inbox.

Filters:

All
Critical
Warning
Resolved

Examples:

🔴 Website unavailable

example-shop.de

Detected:
12 minutes ago

[View details]

🟠 SSL certificate expires soon

example.de

Expires in:
12 days

[View details]

🟡 DNS configuration changed

example.com

[View details]

Actions:

Resolve
Ignore
View details

============================================================
14 - REPORTS DESKTOP
============================================================

Create reports page.

Monthly report:

August 2026

Score:

82 / 100

Change:

+6 points

Issues:

2

CTA:

Download PDF

History:

August 2026
82 / 100

July 2026
76 / 100

June 2026
74 / 100

============================================================
15 - REVIEWS DESKTOP
============================================================

Create reputation dashboard.

Rating:

4.7 ★

Total reviews:

248

New this month:

18

Recent reviews:

★★★★★

"Excellent service..."

★★★★★

"Very friendly staff..."

★★☆☆☆

"Waited too long..."

Negative reviews should show:

"Needs response"

CTA:

"Generate response"

============================================================
AI REVIEW RESPONSE
============================================================

Create modal:

"AI Response Assistant"

Show:

Customer review

AI-generated suggested response

Buttons:

Regenerate
Edit
Copy

IMPORTANT:

The AI response must never be automatically published.

The user must approve the response.

Clearly label:

"AI-generated suggestion"

============================================================
16 - SETTINGS DESKTOP
============================================================

Settings:

Account
Business
Websites
Notifications
PWA
Security
Subscription
Language

Business:

Business name
Industry
Country
Timezone

Language:

English
Français
Deutsch

Timezone:

Europe/Berlin

Notifications:

Website down
SSL expiration
DNS changes
Email security
Weekly report
Reviews

Channels:

Email
Push
Discord
Slack

PWA settings:

Install Presence

Status:

Installed

Push notifications:

Enabled

Offline data:

Enabled

Last synchronized:

10:42

============================================================
17 - PRICING
============================================================

Create a polished pricing page.

FREE

€0/month

1 website
Manual checks
Basic report

CTA:

Start free

PRO

€5.99/month

10 websites
Automatic monitoring
Email alerts
Push notifications
PDF reports
History
Advanced checks

CTA:

Start Pro

BUSINESS

€14.99/month

50 websites
Hourly monitoring
Advanced analytics
Review monitoring
Multiple users
Push notifications
Priority support

CTA:

Start Business

Include:

"Cancel anytime."

"14-day free trial."

Do not use fake urgency.

Do not use fake discounts.

============================================================
18 - PWA MOBILE
============================================================

This page is extremely important.

Design the complete installed PWA experience.

Mobile width:

390px

Also consider:

320px

Create:

Splash screen
Login
Onboarding
Dashboard
Websites
Website details
Monitoring
Alerts
Reports
Reviews
Settings
Profile

The PWA must feel like a native mobile application.

Do NOT simply shrink the desktop dashboard.

------------------------------------------------------------
PWA HEADER
------------------------------------------------------------

Compact header:

Presence logo
Page title
Notification icon
Profile

Support mobile safe areas.

Design around:

- Notch
- Dynamic Island
- Status bar
- Bottom safe area

------------------------------------------------------------
PWA BOTTOM NAVIGATION
------------------------------------------------------------

Bottom navigation:

Home
Websites
Alerts
Reports
More

Use:

Icon
Label

Primary actions must be reachable with one hand.

------------------------------------------------------------
PWA MOBILE DASHBOARD
------------------------------------------------------------

Show:

Good morning

Digital Health Score:

82 / 100

Status:

Good

KPI cards:

Open issues
2

Websites
3

Uptime
99.98%

Then:

Your websites

Use mobile cards instead of desktop tables.

Example:

example.de

🟢 Online

92 / 100

99.99% uptime

SSL:
Valid

Last check:
2 min ago

------------------------------------------------------------
PWA WEBSITE DETAILS
------------------------------------------------------------

Mobile website details page:

example.de

🟢 Online

82 / 100

Sections:

Availability
SSL
DNS
Email
Security headers
Performance
Reviews

Use expandable cards.

Technical details are collapsed by default.

------------------------------------------------------------
PWA ALERTS
------------------------------------------------------------

Mobile alert cards:

🚨 Website offline

example.de

3 minutes ago

Button:

View details

🟠 SSL expires soon

example.de

12 days remaining

Button:

View details

------------------------------------------------------------
PWA REPORTS
------------------------------------------------------------

Show:

August 2026

82 / 100

+6 points

2 issues

Button:

View report

Button:

Download PDF

------------------------------------------------------------
PWA REVIEWS
------------------------------------------------------------

Show:

4.7 ★

248 reviews

Recent reviews

Negative reviews:

"Needs response"

CTA:

Generate response

============================================================
19 - PWA STATES
============================================================

Create dedicated designs for:

1. Installation available
2. Installation dismissed
3. Already installed
4. Offline
5. Reconnecting
6. Syncing
7. Push notification permission
8. Push enabled
9. Push disabled
10. Update available
11. PWA loading
12. PWA error

------------------------------------------------------------
INSTALLATION AVAILABLE
------------------------------------------------------------

Banner:

"Install Presence"

"Get faster access to your digital health dashboard and receive important alerts."

Buttons:

Install app
Not now

------------------------------------------------------------
IOS INSTALLATION
------------------------------------------------------------

Create an iOS-specific instruction screen.

Title:

"Add Presence to your Home Screen"

Show visual instructions:

1. Tap Share
2. Select "Add to Home Screen"
3. Tap Add

Do not pretend that iOS uses the exact same installation mechanism as Android.

------------------------------------------------------------
ANDROID / CHROME
------------------------------------------------------------

Title:

"Install Presence"

Show:

Install app

Create an appropriate browser installation visual.

------------------------------------------------------------
DESKTOP INSTALLATION
------------------------------------------------------------

Title:

"Install Presence on your computer"

Show:

Install Presence

Do not use platform-specific UI that may not be universally accurate.

------------------------------------------------------------
OFFLINE
------------------------------------------------------------

Show:

"You're offline"

"Some information may be outdated."

Last synchronized:

10:42

Show cached dashboard information.

============================================================
20 - RESPONSIVE
============================================================

Create responsive designs for:

1440px desktop
1280px laptop
1024px tablet
768px tablet
390px mobile
320px mobile

IMPORTANT:

Do not simply scale desktop.

Define responsive behavior.

Desktop:

Sidebar

Tablet:

Collapsible sidebar

Mobile:

Bottom navigation

Tables:

Desktop:
Table

Mobile:
Cards

Large charts:

Desktop:
Full chart

Mobile:
Simplified chart

Buttons:

Desktop:
Inline

Mobile:
Full-width when appropriate

============================================================
21 - PROTOTYPE
============================================================

Create a fully clickable Figma prototype.

MAIN CUSTOMER FLOW:

Landing
→ Enter domain
→ Free scan
→ Scan progress
→ Results
→ Create account
→ Onboarding
→ Add website
→ Dashboard
→ Website details
→ Monitoring
→ Alert
→ Report

PWA FLOW:

Landing
→ Install Presence
→ Installation prompt
→ PWA splash
→ PWA dashboard
→ Push notification
→ Open alert
→ Website details

LANGUAGE FLOW:

EN
↔ FR
↔ DE

PRICING FLOW:

Free
→ Pro
→ Business

REVIEW FLOW:

Review
→ AI Response Assistant
→ Edit
→ Copy

ALERT FLOW:

Notification
→ Alert
→ Website details
→ Resolve

============================================================
PWA NOTIFICATIONS
============================================================

Create notification designs for:

Website offline:

"🚨 Your website is unavailable"

SSL:

"⚠️ SSL certificate expires in 7 days"

Recovery:

"🟢 Your website is back online"

Weekly report:

"📊 Your weekly digital health report is ready"

DNS:

"⚠️ Important DNS change detected"

Review:

"⭐ New review received"

============================================================
PWA INSTALLATION EXPERIENCE
============================================================

The installation experience must be helpful but not annoying.

Do not repeatedly display installation prompts.

Create states:

First visit
Installation available
User dismissed
Installation completed
Already installed

============================================================
PWA OFFLINE EXPERIENCE
============================================================

Design:

Offline banner

"You're offline."

"Showing the latest synchronized information."

When connection returns:

"Back online."

"Your data is up to date."

Create:

Offline
Reconnecting
Syncing
Synchronized

============================================================
PWA PUSH NOTIFICATION PERMISSION
============================================================

Do not request notification permissions immediately.

First explain the benefit.

Screen:

"Stay informed"

"Presence can notify you when your website goes offline, your SSL certificate is about to expire, or an important issue is detected."

Buttons:

Enable notifications
Maybe later

============================================================
EMPTY STATES
============================================================

Create:

No websites
No alerts
No reports
No reviews
No notifications

Example:

"No websites yet"

"Add your first website to start monitoring your digital presence."

CTA:

Add website

============================================================
ERROR STATES
============================================================

Create:

Invalid domain
Website unavailable
DNS check failed
SSL check failed
Monitoring unavailable
Offline
Authentication error
Payment error

Use friendly language.

Example:

"We couldn't reach your website."

"Your website may be temporarily unavailable. We'll try again automatically."

Buttons:

Try again
View details

============================================================
SECURITY & PRIVACY UX
============================================================

Create privacy and security screens.

Use simple language.

Example:

"We only collect the information needed to monitor your digital presence."

Show:

Secure connection
Account security
Data protection
Notification controls

Do not make exaggerated claims such as:

"100% secure"

============================================================
ACCESSIBILITY
============================================================

Follow WCAG-friendly principles.

Ensure:

- Accessible contrast
- Visible focus states
- Keyboard navigation
- Large touch targets
- Readable typography
- Screen-reader-friendly hierarchy

Never communicate status using color alone.

Use:

🟢 Healthy
🟠 Warning
🔴 Critical

with text labels.

============================================================
MICRO-INTERACTIONS
============================================================

Create subtle interactions for:

Website scanning
Score calculation
Loading
Success
Alerts
Notifications
PWA installation
Offline state
Reconnection
Sync
Button hover
Card hover
Dropdowns
Page transitions

Avoid excessive animation.

============================================================
FINAL FIGMA FILE STRUCTURE
============================================================

The final Figma file MUST be organized exactly as follows:

01 - Cover
02 - Brand
03 - Design System
04 - Variables
05 - Components
06 - Icons

07 - Landing

08 - Authentication

09 - Onboarding

10 - Dashboard Desktop
11 - Monitoring Desktop
12 - Website Details Desktop
13 - Alerts Desktop
14 - Reports Desktop
15 - Reviews Desktop
16 - Settings Desktop

17 - Pricing

18 - PWA Mobile
19 - PWA States

20 - Responsive

21 - Prototype

Do NOT combine these into one page.

Keep each page organized and clean.

Use clear section titles.

Use Auto Layout.

Use components and variants.

Use variables.

Use consistent naming.

============================================================
IMPORTANT DEVELOPMENT-READY REQUIREMENT
============================================================

The Figma design will later be implemented using:

Frontend:

React
TypeScript
Tailwind CSS

PWA:

Web App Manifest
Service Worker
Push Notifications
Offline caching

Backend:

Django
Django REST Framework

Database:

PostgreSQL

Background jobs:

Celery
Redis

Infrastructure:

Docker
Nginx

Therefore:

Design components that can realistically be implemented in React.

Avoid designs that require impossible or unnecessarily complex frontend behavior.

Use reusable components.

Use consistent states.

Design loading, empty, success, warning and error states.

============================================================
FINAL PRODUCT EXPERIENCE
============================================================

Presence should feel like:

A simple digital assistant for small businesses.

The user should open the application and immediately see:

"Is my digital presence okay?"

Then:

"What needs my attention?"

Then:

"What should I do?"

The interface should never overwhelm the user.

The final product should feel:

Professional
Trustworthy
Simple
Modern
European
Accessible
Responsive
PWA-first
Production-ready

The final Figma file must look like a real commercial SaaS product and NOT like a generic AI-generated dashboard.

The design should be ready to hand over to a frontend developer for implementation.

The most important priorities are:

1. Clarity
2. Simplicity
3. Trust
4. Actionable information
5. PWA experience
6. Responsive design
7. Internationalization
8. Accessibility
9. Reusable components
10. Production-ready design system

Final message of the product:

"Presence takes care of your digital presence for you."
