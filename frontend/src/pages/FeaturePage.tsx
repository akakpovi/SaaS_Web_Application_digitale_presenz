import React, { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle, ChevronDown, ArrowRight } from "lucide-react";
import { Button } from "../components/ui";
import SEO, { faqSchema, breadcrumbSchema, softwareAppSchema } from "../components/SEO";
import Breadcrumb from "../components/Breadcrumb";

interface FeaturePageConfig {
  slug: string;
  title: string;
  metaTitle: string;
  metaDescription: string;
  h1: string;
  intro: string;
  problem: string;
  solution: string;
  benefits: string[];
  howItWorks: { step: string; desc: string }[];
  faqItems: { q: string; a: string }[];
  relatedFeatures: { label: string; path: string }[];
  checkpoints: string[];
  ctaLabel?: string;
}

const configs: Record<string, FeaturePageConfig> = {
  "website-monitoring": {
    slug: "website-monitoring",
    title: "Website Monitoring",
    metaTitle: "Website Monitoring & Uptime Alerts | Presence",
    metaDescription: "Know the moment your website goes offline. Automatic website monitoring for small businesses with instant email and push alerts.",
    h1: "Website Monitoring for Small Businesses",
    intro: "Every minute your website is offline, you're losing customers. Presence monitors your website around the clock and alerts you the moment something goes wrong — so you can act fast.",
    problem: "Most small business owners only discover their website is down when a customer tells them. By then, the damage is already done: lost visitors, lost trust, and lost revenue.",
    solution: "Presence checks your website every hour and immediately notifies you if your website becomes unavailable. You'll always know your website status before your customers do.",
    benefits: [
      "Instant alerts when your website goes offline",
      "Automatic recovery notifications when your website comes back online",
      "Uptime history and statistics",
      "Monitor multiple websites from one dashboard",
      "No technical knowledge required",
    ],
    howItWorks: [
      { step: "1. Add your website", desc: "Enter your domain. No installation required." },
      { step: "2. Automatic monitoring", desc: "Presence checks your website every hour. Pro plan checks more frequently." },
      { step: "3. Instant alerts", desc: "If your website goes offline, you receive an immediate email or push notification." },
    ],
    faqItems: [
      { q: "How often is my website checked?", a: "On the Pro plan, your website is checked every hour. On the Business plan, checks happen even more frequently. On the Free plan, you can run manual checks." },
      { q: "What does 'website offline' mean?", a: "Your website is considered offline when Presence cannot reach it — for example, if your server is down, your domain has expired, or there's a technical problem preventing visitors from accessing your site." },
      { q: "How will I be notified?", a: "Presence can notify you by email, browser push notification, or app push notification if you have the PWA installed. You choose which channels to use in your settings." },
      { q: "Does Presence change my website?", a: "No. Presence only checks whether your website is reachable from the outside. It never modifies, accesses, or interferes with your website files or code." },
    ],
    relatedFeatures: [
      { label: "Uptime monitoring", path: "/features/uptime-monitoring" },
      { label: "Performance monitoring", path: "/features/website-performance" },
      { label: "SSL certificate monitoring", path: "/features/ssl-monitoring" },
    ],
    checkpoints: ["Website availability", "Response time", "HTTP status", "Uptime statistics", "Instant alerts"],
    ctaLabel: "Start monitoring your website",
  },

  "ssl-monitoring": {
    slug: "ssl-monitoring",
    title: "SSL Certificate Monitoring",
    metaTitle: "SSL Certificate Monitoring & Expiry Alerts | Presence",
    metaDescription: "Get alerted before your SSL certificate expires. Automatic SSL monitoring keeps your business website trusted and secure.",
    h1: "SSL Certificate Monitoring",
    intro: "An expired SSL certificate locks visitors out of your website and destroys customer trust. Presence monitors your SSL certificate and alerts you well before it expires.",
    problem: "SSL certificates expire — usually once or twice a year. Forgetting to renew one means your website shows a scary security warning to visitors, causing them to leave immediately.",
    solution: "Presence tracks your SSL certificate expiry date and alerts you 30 days in advance, giving you plenty of time to renew before your visitors are affected.",
    benefits: [
      "Early warning before your SSL certificate expires",
      "Alerts sent 30 days before expiry",
      "Verification that your certificate is valid and trusted",
      "Detection of certificate configuration issues",
      "Automatic monitoring — no manual tracking needed",
    ],
    howItWorks: [
      { step: "1. Add your website", desc: "Enter your domain and Presence checks your SSL certificate immediately." },
      { step: "2. Continuous monitoring", desc: "Presence tracks your certificate expiry date and checks the certificate validity regularly." },
      { step: "3. Timely alerts", desc: "You receive an alert 30 days before expiry, giving you time to act." },
    ],
    faqItems: [
      { q: "What is an SSL certificate?", a: "An SSL certificate secures the connection between your website and your visitors. It's what makes the padlock appear in the browser address bar and enables the 'https://' prefix." },
      { q: "What happens if my SSL certificate expires?", a: "Browsers display a security warning page that blocks visitors from accessing your website. Most visitors immediately leave, and this severely damages trust in your business." },
      { q: "How early does Presence alert me?", a: "Presence alerts you 30 days before your certificate expires, giving you plenty of time to renew it before your visitors are affected." },
      { q: "Can Presence renew my SSL certificate?", a: "No. Presence monitors and alerts you — renewing the certificate is done through your hosting provider or domain registrar. We make sure you never forget." },
    ],
    relatedFeatures: [
      { label: "Website monitoring", path: "/features/website-monitoring" },
      { label: "DNS monitoring", path: "/features/dns-monitoring" },
      { label: "Free SSL checker", path: "/tools/ssl-checker" },
    ],
    checkpoints: ["Certificate validity", "Expiry date", "Issuer trust", "Certificate chain", "30-day advance alert"],
    ctaLabel: "Check your SSL certificate",
  },

  "dns-monitoring": {
    slug: "dns-monitoring",
    title: "DNS Monitoring",
    metaTitle: "DNS Monitoring & Domain Health Checks | Presence",
    metaDescription: "Detect unexpected DNS changes automatically. Presence monitors your domain DNS configuration and alerts you when something important changes.",
    h1: "DNS Monitoring & Domain Health Checks",
    intro: "Your domain's DNS configuration is the foundation of your online presence. Unexpected DNS changes can take your website offline or redirect your visitors elsewhere. Presence monitors your DNS and alerts you when important changes occur.",
    problem: "DNS changes can happen accidentally — through a misconfiguration, a compromised account, or an error at your domain registrar. Without monitoring, you might not notice for hours or days.",
    solution: "Presence checks your DNS records regularly and notifies you when something changes unexpectedly, so you can verify whether the change was intentional or investigate immediately.",
    benefits: [
      "Automatic detection of DNS record changes",
      "Alerts for unexpected or unauthorized changes",
      "Verification that your domain is correctly configured",
      "MX record monitoring for email delivery",
      "Historical record of DNS changes",
    ],
    howItWorks: [
      { step: "1. Add your domain", desc: "Presence captures a baseline of your current DNS configuration." },
      { step: "2. Regular checks", desc: "Your DNS records are verified regularly for unexpected changes." },
      { step: "3. Instant alerts", desc: "If a DNS record changes unexpectedly, you receive an immediate notification." },
    ],
    faqItems: [
      { q: "What is DNS?", a: "DNS (Domain Name System) translates your domain name (like example.com) into the IP address of your server. It also controls where your email is delivered and other important settings." },
      { q: "Why does DNS monitoring matter?", a: "DNS changes can cause your website to go offline, redirect visitors elsewhere, or break email delivery. Unauthorized DNS changes are also a sign of a security issue." },
      { q: "What DNS records does Presence monitor?", a: "Presence monitors A records (website IP), MX records (email routing), CNAME records, TXT records, and NS records." },
      { q: "Does Presence alert me when I make planned DNS changes?", a: "Presence will notify you of all DNS changes. If you've made a planned change, you can acknowledge the alert in your dashboard." },
    ],
    relatedFeatures: [
      { label: "Website monitoring", path: "/features/website-monitoring" },
      { label: "Email security", path: "/features/email-security" },
      { label: "Free DNS checker", path: "/tools/dns-checker" },
    ],
    checkpoints: ["A records", "MX records", "CNAME records", "TXT records", "NS records"],
    ctaLabel: "Check your DNS configuration",
  },

  "email-security": {
    slug: "email-security",
    title: "Email Security",
    metaTitle: "SPF, DKIM & DMARC Monitoring | Presence",
    metaDescription: "Check your SPF, DKIM and DMARC email security configuration. Protect your business email from spoofing and impersonation.",
    h1: "Email Security Monitoring — SPF, DKIM & DMARC",
    intro: "Criminals impersonate business emails to scam your customers. Properly configuring SPF, DKIM and DMARC protects your business email and helps your legitimate emails reach inboxes. Presence checks your email security configuration and tells you exactly what needs attention.",
    problem: "Most small business owners have never heard of SPF, DKIM or DMARC — yet a missing or misconfigured email security record means anyone can send emails that appear to come from your domain.",
    solution: "Presence checks your SPF, DKIM and DMARC configuration and explains the results in plain language. No technical knowledge required — we tell you exactly what's working and what needs improvement.",
    benefits: [
      "Check SPF, DKIM and DMARC configuration",
      "Plain-language explanations — no technical jargon",
      "Specific recommendations to improve email security",
      "Regular monitoring for configuration changes",
      "Protection against email spoofing and phishing",
    ],
    howItWorks: [
      { step: "1. Add your domain", desc: "Presence looks up your DNS records to find your email security configuration." },
      { step: "2. Instant check", desc: "We verify your SPF, DKIM and DMARC records and check for common problems." },
      { step: "3. Clear results", desc: "You receive a plain-language summary: what's working, what needs attention, and what to do next." },
    ],
    faqItems: [
      { q: "What are SPF, DKIM and DMARC?", a: "SPF, DKIM and DMARC are email authentication standards. SPF specifies which servers can send email on your behalf. DKIM adds a digital signature to your emails. DMARC tells email providers what to do with emails that fail verification. Together they significantly reduce email impersonation." },
      { q: "Do I need technical knowledge to fix email security issues?", a: "Not with Presence. We explain what needs to be done in simple terms. You (or your hosting provider) will need to add or update a DNS record, but we guide you through it." },
      { q: "Why is DMARC important?", a: "Without DMARC, scammers can send emails that appear to come from your domain to deceive your customers. DMARC tells email providers to reject or quarantine those fake emails." },
      { q: "Will fixing email security affect my existing email?", a: "Done correctly, adding SPF, DKIM and DMARC will not affect your legitimate email. Presence will notify you if your monitoring detects any issues." },
    ],
    relatedFeatures: [
      { label: "DNS monitoring", path: "/features/dns-monitoring" },
      { label: "Security headers", path: "/features/security-headers" },
      { label: "Free email security checker", path: "/tools/email-security-checker" },
    ],
    checkpoints: ["SPF record", "DKIM record", "DMARC policy", "DMARC enforcement", "Email reputation"],
    ctaLabel: "Check your email security",
  },

  "uptime-monitoring": {
    slug: "uptime-monitoring",
    title: "Uptime Monitoring",
    metaTitle: "Website Uptime Monitoring for Small Businesses | Presence",
    metaDescription: "Track your website uptime over time. Monitor availability, detect outages instantly and measure your website reliability.",
    h1: "Website Uptime Monitoring",
    intro: "Uptime is one of the most important metrics for your business website. Presence tracks your website availability over time and gives you clear uptime statistics, so you always know how reliable your website has been.",
    problem: "Without uptime monitoring, you have no record of how often your website has been offline, how long outages lasted, or whether your hosting provider is delivering on their promises.",
    solution: "Presence monitors your website continuously and records every outage. You can view your uptime history, identify patterns, and hold your hosting provider accountable with hard data.",
    benefits: [
      "Real-time uptime tracking",
      "Historical uptime statistics (24h, 7d, 30d, 90d)",
      "Outage duration tracking",
      "Uptime percentage over time",
      "Evidence for hosting provider disputes",
    ],
    howItWorks: [
      { step: "1. Add your website", desc: "Presence begins monitoring your uptime immediately." },
      { step: "2. Continuous tracking", desc: "Every check result is recorded, building your uptime history." },
      { step: "3. View statistics", desc: "Access clear charts and statistics showing your website availability over time." },
    ],
    faqItems: [
      { q: "What does 99.9% uptime mean?", a: "99.9% uptime means your website was offline for approximately 8.7 hours per year, or 43.8 minutes per month. Even small reductions in uptime add up quickly." },
      { q: "How is uptime calculated?", a: "Presence checks your website regularly and records whether it was reachable. Uptime is calculated as the percentage of checks where your website responded successfully." },
      { q: "What counts as downtime?", a: "Downtime is recorded when Presence cannot reach your website or when your website returns an error response. Brief slow responses may not be counted as downtime." },
      { q: "Can I download uptime reports?", a: "Yes. Presence Pro and Business plans include downloadable PDF reports with your uptime statistics." },
    ],
    relatedFeatures: [
      { label: "Website monitoring", path: "/features/website-monitoring" },
      { label: "Performance monitoring", path: "/features/website-performance" },
      { label: "Alerts", path: "/features/website-monitoring" },
    ],
    checkpoints: ["Real-time status", "Uptime percentage", "Outage history", "Response time", "Monthly reports"],
    ctaLabel: "Start tracking your uptime",
  },

  "website-performance": {
    slug: "website-performance",
    title: "Website Performance Monitoring",
    metaTitle: "Website Performance Monitoring | Presence",
    metaDescription: "Track your website response time and loading speed. Identify performance issues that affect your customers and search rankings.",
    h1: "Website Performance Monitoring",
    intro: "A slow website frustrates visitors and hurts your search rankings. Presence tracks your website response time and loading speed, and alerts you when performance drops below acceptable levels.",
    problem: "Website performance degrades gradually. Without monitoring, you might not notice your website getting slower until visitors are already leaving in frustration or your search rankings have dropped.",
    solution: "Presence measures your website response time on every check and maintains a history of performance data. You can see exactly when performance changed and identify potential causes.",
    benefits: [
      "Response time tracking on every check",
      "Performance history and trends",
      "Alerts when response time exceeds thresholds",
      "Performance as part of your Digital Health Score",
      "Clear, plain-language recommendations",
    ],
    howItWorks: [
      { step: "1. Add your website", desc: "Presence immediately measures your website's response time." },
      { step: "2. Regular performance checks", desc: "Response time is measured on every check and recorded over time." },
      { step: "3. Alerts and recommendations", desc: "You're alerted if performance degrades, with clear recommendations to improve." },
    ],
    faqItems: [
      { q: "What is website response time?", a: "Response time is how quickly your website server responds to a request. Fast response times (under 200ms) provide a good experience; slow response times (over 1000ms) can frustrate visitors." },
      { q: "Does website speed affect SEO?", a: "Yes. Google considers page speed as a ranking factor. A slow website can rank lower in search results, reducing your organic traffic." },
      { q: "What causes slow website performance?", a: "Common causes include unoptimized images, too many plugins, slow hosting, large JavaScript files, and database issues. Presence identifies the issue and recommends actions." },
      { q: "What is a good response time?", a: "Under 200ms is excellent. Under 500ms is good. Over 1 second starts to affect user experience and should be investigated." },
    ],
    relatedFeatures: [
      { label: "Uptime monitoring", path: "/features/uptime-monitoring" },
      { label: "Website monitoring", path: "/features/website-monitoring" },
      { label: "Free website checker", path: "/tools/website-checker" },
    ],
    checkpoints: ["Response time", "Time to First Byte", "Performance trends", "Threshold alerts", "Recommendations"],
    ctaLabel: "Check your website performance",
  },

  "security-headers": {
    slug: "security-headers",
    title: "Security Headers",
    metaTitle: "Website Security Headers Check | Presence",
    metaDescription: "Check your website's HTTP security headers. Identify missing or misconfigured security headers that could put your visitors at risk.",
    h1: "Website Security Headers Monitoring",
    intro: "Security headers are simple configuration settings that protect your visitors from common web attacks. Many small business websites are missing these basic protections. Presence checks your security headers and tells you exactly what to improve — in plain language.",
    problem: "Security headers are invisible to most website owners. Missing headers can expose your visitors to clickjacking, cross-site scripting (XSS), and other common web attacks.",
    solution: "Presence checks your website's security headers and explains each finding in plain language. We don't just report the technical details — we tell you what the risk is and what to do about it.",
    benefits: [
      "Check all important security headers",
      "Plain-language explanations of each finding",
      "Specific recommendations to fix issues",
      "Security headers as part of your Digital Health Score",
      "Regular monitoring for configuration changes",
    ],
    howItWorks: [
      { step: "1. Add your website", desc: "Presence reads your website's HTTP response headers." },
      { step: "2. Analysis", desc: "We check for the presence and correct configuration of important security headers." },
      { step: "3. Plain-language results", desc: "You receive a clear summary of what's configured, what's missing, and what to add." },
    ],
    faqItems: [
      { q: "What are security headers?", a: "Security headers are HTTP response headers that your server sends to browsers. They instruct browsers how to behave to protect your visitors — for example, preventing your website from being embedded in an iframe on another site." },
      { q: "Which security headers does Presence check?", a: "Presence checks for Content-Security-Policy (CSP), Strict-Transport-Security (HSTS), X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy." },
      { q: "Do I need to be technical to fix security header issues?", a: "Not with Presence. We explain what needs to be done in plain language. Your hosting provider or website developer can implement the changes with our recommendations." },
      { q: "Will adding security headers break my website?", a: "Some headers (like CSP) need careful configuration to avoid breaking functionality. Presence always recommends a safe starting configuration and explains any trade-offs." },
    ],
    relatedFeatures: [
      { label: "SSL monitoring", path: "/features/ssl-monitoring" },
      { label: "Email security", path: "/features/email-security" },
      { label: "Free website checker", path: "/tools/website-checker" },
    ],
    checkpoints: ["Content-Security-Policy", "HSTS", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy"],
    ctaLabel: "Check your security headers",
  },

  "review-monitoring": {
    slug: "review-monitoring",
    title: "Review Monitoring",
    metaTitle: "Online Review Monitoring for Small Businesses | Presence",
    metaDescription: "Monitor your online reviews and customer ratings. Stay on top of new reviews and respond quickly to negative feedback.",
    h1: "Online Review Monitoring for Small Businesses",
    intro: "Online reviews are one of the first things potential customers check before visiting your business. Presence monitors your customer ratings across platforms and alerts you when new reviews arrive — so you can respond quickly.",
    problem: "A single unanswered negative review can deter dozens of potential customers. Most business owners only check their reviews occasionally — by which time the damage to their reputation may already be done.",
    solution: "Presence monitors your online reviews and notifies you when new reviews arrive. For negative reviews, Presence can suggest a response using AI — which you review and approve before it's ever sent.",
    benefits: [
      "Monitor reviews across multiple platforms",
      "Instant notifications for new reviews",
      "Alerts when negative reviews need attention",
      "AI-assisted response suggestions (you always approve)",
      "Rating trends and statistics",
    ],
    howItWorks: [
      { step: "1. Connect your business", desc: "Tell Presence where your business appears online." },
      { step: "2. Automatic monitoring", desc: "Presence tracks new reviews as they arrive." },
      { step: "3. Respond quickly", desc: "You're notified immediately and can draft a response with AI assistance." },
    ],
    faqItems: [
      { q: "Which review platforms does Presence monitor?", a: "Presence monitors Google Reviews and Yelp. Additional platforms are on the roadmap." },
      { q: "Does Presence post responses automatically?", a: "Never. Presence can suggest AI-generated responses, but you always review, edit, and approve any response before it is published. We believe in human oversight." },
      { q: "How quickly am I notified about new reviews?", a: "Presence checks for new reviews regularly and notifies you promptly when a new review is detected." },
      { q: "Does responding to reviews help my business?", a: "Yes. Responding to reviews — especially negative ones — shows potential customers that you care about feedback. Businesses that respond to reviews consistently score higher in trust ratings." },
    ],
    relatedFeatures: [
      { label: "Digital Health Score", path: "/#score" },
      { label: "Reports", path: "/features/website-monitoring" },
      { label: "Alerts", path: "/features/website-monitoring" },
    ],
    checkpoints: ["Google Reviews", "Yelp", "New review alerts", "Negative review priority", "AI response suggestions"],
    ctaLabel: "Start monitoring your reviews",
  },
};

function FeatureContent({ config }: { config: FeaturePageConfig }) {
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={config.metaTitle}
        description={config.metaDescription}
        path={`/features/${config.slug}`}
        hreflang={{
          en: `/features/${config.slug}`,
        }}
        structuredData={[
          softwareAppSchema,
          faqSchema(config.faqItems),
          breadcrumbSchema([
            { name: "Home", url: "/" },
            { name: "Features", url: "/features" },
            { name: config.title, url: `/features/${config.slug}` },
          ]),
        ]}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-8">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link to="/#features" className="text-sm text-slate-600 hover:text-slate-900">Features</Link>
            <Link to="/pricing" className="text-sm text-slate-600 hover:text-slate-900">Pricing</Link>
            <Link to="/tools/website-checker" className="text-sm text-slate-600 hover:text-slate-900">Free checker</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-slate-600 hover:text-slate-900">Log in</Link>
            <Link to="/register">
              <button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors">
                {config.ctaLabel || "Get started"}
              </button>
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="pt-16 pb-20 px-4 bg-gradient-to-b from-indigo-50/50 to-white">
          <div className="max-w-4xl mx-auto">
            <Breadcrumb items={[
              { label: "Home", path: "/" },
              { label: "Features", path: "/#features" },
              { label: config.title, path: `/features/${config.slug}` },
            ]} />
            <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-5 leading-tight">
              {config.h1}
            </h1>
            <p className="text-xl text-slate-500 mb-8 leading-relaxed max-w-2xl">{config.intro}</p>
            <div className="flex flex-wrap gap-3">
              <Link to="/tools/website-checker">
                <button className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2">
                  Check your website for free <ArrowRight size={16} />
                </button>
              </Link>
              <Link to="/register">
                <button className="px-6 py-3 border border-slate-300 text-slate-700 font-semibold rounded-xl hover:bg-slate-50 transition-colors">
                  Start monitoring
                </button>
              </Link>
            </div>
          </div>
        </section>

        {/* What we check */}
        <section className="py-16 px-4 border-y border-slate-100 bg-slate-50">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">What Presence checks</h2>
            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
              {config.checkpoints.map((cp) => (
                <div key={cp} className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3">
                  <CheckCircle size={16} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-sm font-medium text-slate-700">{cp}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Problem / Solution */}
        <section className="py-20 px-4">
          <div className="max-w-4xl mx-auto grid md:grid-cols-2 gap-10">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-red-500 mb-3">The problem</p>
              <h2 className="text-2xl font-bold text-slate-900 mb-4">Why this matters for your business</h2>
              <p className="text-slate-600 leading-relaxed">{config.problem}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-emerald-600 mb-3">The solution</p>
              <h2 className="text-2xl font-bold text-slate-900 mb-4">How Presence helps</h2>
              <p className="text-slate-600 leading-relaxed">{config.solution}</p>
            </div>
          </div>
        </section>

        {/* Benefits */}
        <section className="py-16 px-4 bg-indigo-600">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-white mb-8">What you get with Presence</h2>
            <ul className="space-y-3">
              {config.benefits.map((b) => (
                <li key={b} className="flex items-center gap-3 text-indigo-100">
                  <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
                  {b}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section className="py-20 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 mb-10 text-center">How it works</h2>
            <div className="grid md:grid-cols-3 gap-8">
              {config.howItWorks.map(({ step, desc }) => (
                <div key={step} className="text-center">
                  <div className="w-12 h-12 bg-indigo-600 text-white rounded-2xl flex items-center justify-center font-bold text-lg mx-auto mb-4">
                    {step.split(".")[0]}
                  </div>
                  <p className="font-semibold text-slate-900 mb-2">{step.replace(/^\d\.\s/, "")}</p>
                  <p className="text-sm text-slate-500">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-20 px-4 bg-slate-50">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 mb-8 text-center">Frequently asked questions</h2>
            <div className="space-y-3">
              {config.faqItems.map((faq, i) => (
                <div key={i} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <button
                    className="w-full flex items-center justify-between px-5 py-4 text-left"
                    onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                    aria-expanded={activeFaq === i}
                  >
                    <span className="font-medium text-slate-900">{faq.q}</span>
                    <ChevronDown size={16} className={`text-slate-400 flex-shrink-0 transition-transform ${activeFaq === i ? "rotate-180" : ""}`} />
                  </button>
                  {activeFaq === i && (
                    <div className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
                      {faq.a}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Related features */}
        <section className="py-16 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Related features</h2>
            <div className="flex flex-wrap gap-3">
              {config.relatedFeatures.map(({ label, path }) => (
                <Link
                  key={path}
                  to={path}
                  className="px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-700 hover:bg-indigo-50 transition-all flex items-center gap-2"
                >
                  {label} <ArrowRight size={14} />
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-20 px-4 bg-slate-900 text-center">
          <div className="max-w-xl mx-auto">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to monitor your website?</h2>
            <p className="text-slate-400 mb-8">Start for free. No credit card required.</p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/tools/website-checker">
                <button className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors">
                  Check your website for free
                </button>
              </Link>
              <Link to="/pricing">
                <button className="px-6 py-3 border border-slate-700 text-slate-300 font-semibold rounded-xl hover:bg-slate-800 transition-colors">
                  View pricing
                </button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">© 2026 Presence. <Link to="/pricing" className="hover:text-slate-600">Pricing</Link> · <Link to="/faq" className="hover:text-slate-600">FAQ</Link> · <Link to="/about" className="hover:text-slate-600">About</Link></p>
      </footer>
    </div>
  );
}

export default function FeaturePage({ feature }: { feature: string }) {
  // SEO dynamique par feature
  const featureTitles: Record<string, { title: string; description: string; path: string }> = {
    "website-monitoring": {
      title: "Website Monitoring for Small Businesses | Presence",
      description: "Monitor your website 24/7. Get instant alerts when your site goes down. Track uptime, response time and HTTP status from one simple dashboard.",
      path: "/features/website-monitoring",
    },
    "ssl-monitoring": {
      title: "SSL Certificate Monitoring — Never Let Your SSL Expire | Presence",
      description: "Get alerted before your SSL certificate expires. Monitor certificate validity, expiry date and chain of trust automatically.",
      path: "/features/ssl-monitoring",
    },
    "dns-monitoring": {
      title: "DNS Monitoring — Track Your DNS Records | Presence",
      description: "Monitor your DNS records automatically. Get alerted when DNS changes are detected. Check A, AAAA, MX and NS records.",
      path: "/features/dns-monitoring",
    },
    "email-security": {
      title: "Email Security Monitoring — SPF, DKIM & DMARC | Presence",
      description: "Check your SPF, DKIM and DMARC configuration automatically. Protect your business email from spoofing and impersonation.",
      path: "/features/email-security",
    },
    "uptime-monitoring": {
      title: "Uptime Monitoring — Track Your Website Availability | Presence",
      description: "Monitor your website uptime 24/7. Get instant downtime alerts. See your uptime percentage and incident history.",
      path: "/features/uptime-monitoring",
    },
    "website-performance": {
      title: "Website Performance Monitoring | Presence",
      description: "Monitor your website load time and page size automatically. Get alerted when performance degrades.",
      path: "/features/website-performance",
    },
    "security-headers": {
      title: "Security Headers Monitoring — CSP, HSTS & More | Presence",
      description: "Check your HTTP security headers automatically. Monitor CSP, HSTS, X-Frame-Options and more from one dashboard.",
      path: "/features/security-headers",
    },
    "review-monitoring": {
      title: "Review Monitoring — Track Your Online Reputation | Presence",
      description: "Monitor your customer reviews across platforms. Get notified of new reviews and manage your online reputation.",
      path: "/features/review-monitoring",
    },
  };
  const seoMeta = featureTitles[feature] ?? {
    title: "Features | Presence",
    description: "Discover all Presence monitoring features for small businesses.",
    path: `/features/${feature}`,
  };

  const config = configs[feature];
  if (!config) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-lg font-semibold text-slate-900">Feature not found</p>
          <Link to="/" className="text-indigo-600 hover:underline text-sm">← Back to home</Link>
        </div>
      </div>
    );
  }
  return <FeatureContent config={config} />;
}
