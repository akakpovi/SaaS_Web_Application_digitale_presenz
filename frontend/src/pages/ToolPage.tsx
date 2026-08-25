import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle, Loader, ChevronDown, Globe } from "lucide-react";
import SEO, { faqSchema, breadcrumbSchema, softwareAppSchema } from "../components/SEO";
import Breadcrumb from "../components/Breadcrumb";

interface ToolConfig {
  slug: string;
  metaTitle: string;
  metaDescription: string;
  h1: string;
  intro: string;
  inputPlaceholder: string;
  inputLabel: string;
  buttonLabel: string;
  checks: string[];
  resultChecks: { label: string; status: "healthy" | "warning" | "neutral" }[];
  relatedTool?: { label: string; path: string };
  featurePath: string;
  faqItems: { q: string; a: string }[];
  howItWorks: string[];
}

const toolConfigs: Record<string, ToolConfig> = {
  "website-checker": {
    slug: "website-checker",
    metaTitle: "Free Website Health Checker | Presence",
    metaDescription: "Check your website health for free. Test uptime, SSL, DNS, email security, performance and security headers in seconds.",
    h1: "Free Website Health Checker",
    intro: "Check your website's availability, SSL certificate, DNS configuration, email security and performance in seconds. No account required.",
    inputPlaceholder: "example.com",
    inputLabel: "Your website domain",
    buttonLabel: "Check my website",
    checks: ["Website availability", "SSL certificate", "DNS configuration", "Email security", "Security headers", "Performance", "Uptime"],
    resultChecks: [
      { label: "Website available", status: "healthy" },
      { label: "SSL certificate valid", status: "healthy" },
      { label: "DNS configured", status: "healthy" },
      { label: "Email security (DMARC)", status: "warning" },
      { label: "Security headers", status: "warning" },
      { label: "Performance", status: "healthy" },
    ],
    relatedTool: { label: "Check SSL certificate", path: "/tools/ssl-checker" },
    featurePath: "/features/website-monitoring",
    faqItems: [
      { q: "What does the website health checker test?", a: "It checks whether your website is reachable, verifies your SSL certificate, inspects your DNS configuration, checks email security records (SPF, DKIM, DMARC), security headers, and measures your website's response time." },
      { q: "Is the website checker really free?", a: "Yes. You can run a website health check for free without creating an account. The results give you a useful snapshot of your website health." },
      { q: "Does the checker access my website files?", a: "No. The checker only tests what's publicly visible from the outside — the same information a visitor or search engine bot would see." },
      { q: "What's the difference between the free check and monitoring?", a: "The free check is a single snapshot. Continuous monitoring checks your website regularly and alerts you when something changes — so you're always informed without having to remember to check manually." },
    ],
    howItWorks: ["Enter your domain", "We run automated checks across 6 health dimensions", "See your results instantly with plain-language explanations", "Get specific recommendations to improve your digital health"],
  },
  "ssl-checker": {
    slug: "ssl-checker",
    metaTitle: "Free SSL Certificate Checker | Presence",
    metaDescription: "Check your SSL certificate for free. Verify expiry date, issuer, and certificate chain in seconds.",
    h1: "Free SSL Certificate Checker",
    intro: "Verify your SSL certificate, check the expiry date, and identify certificate issues in seconds. No account required.",
    inputPlaceholder: "example.com",
    inputLabel: "Your domain",
    buttonLabel: "Check SSL certificate",
    checks: ["Certificate validity", "Expiry date", "Issuer and trust chain", "Certificate algorithm", "HTTPS redirect"],
    resultChecks: [
      { label: "Certificate valid", status: "healthy" },
      { label: "Trusted by all browsers", status: "healthy" },
      { label: "Expires in 42 days", status: "warning" },
      { label: "RSA 2048-bit key", status: "healthy" },
      { label: "HTTPS redirect active", status: "healthy" },
    ],
    relatedTool: { label: "Check website health", path: "/tools/website-checker" },
    featurePath: "/features/ssl-monitoring",
    faqItems: [
      { q: "What does the SSL checker test?", a: "It verifies whether your SSL certificate is valid, trusted by major browsers, when it expires, who issued it, and whether your website correctly redirects visitors from HTTP to HTTPS." },
      { q: "How do I know if my SSL certificate is about to expire?", a: "The SSL checker shows the exact expiry date. If it expires within 30 days, we recommend renewing immediately. With Presence monitoring, you receive an automatic alert 30 days before expiry." },
      { q: "My certificate is valid but my site shows a warning. Why?", a: "This can happen if your certificate chain is incomplete, if you have a self-signed certificate, or if parts of your page load over HTTP. The SSL checker helps identify the specific issue." },
      { q: "Is this SSL check the same as a penetration test?", a: "No. This is a basic SSL certificate verification — not a security audit. It checks your certificate validity, not the security of your server configuration." },
    ],
    howItWorks: ["Enter your domain", "We retrieve and verify your SSL certificate", "See your certificate details and expiry date", "Get alerted if anything needs attention"],
  },
  "dns-checker": {
    slug: "dns-checker",
    metaTitle: "Free DNS Checker | Presence",
    metaDescription: "Check your domain DNS records for free. Verify A, MX, CNAME, TXT and NS records instantly.",
    h1: "Free DNS Checker",
    intro: "Inspect your domain's DNS records instantly. Verify A records, MX records, CNAME, TXT and NS records — no technical knowledge required.",
    inputPlaceholder: "example.com",
    inputLabel: "Your domain",
    buttonLabel: "Check DNS records",
    checks: ["A records (website IP)", "MX records (email routing)", "CNAME records", "TXT records (SPF, DMARC)", "NS records"],
    resultChecks: [
      { label: "A record found", status: "healthy" },
      { label: "MX records configured", status: "healthy" },
      { label: "SPF record present", status: "healthy" },
      { label: "DMARC record", status: "warning" },
      { label: "NS records valid", status: "healthy" },
    ],
    relatedTool: { label: "Check email security", path: "/tools/email-security-checker" },
    featurePath: "/features/dns-monitoring",
    faqItems: [
      { q: "What DNS records does the checker look up?", a: "The DNS checker retrieves A records (your website IP), MX records (email routing), CNAME records, TXT records (including SPF and DMARC), and NS records (name servers)." },
      { q: "Why would my DNS records change unexpectedly?", a: "DNS changes can happen due to account compromises, accidental modifications at your domain registrar, hosting migrations, or technical errors. Unexpected DNS changes are a red flag worth investigating immediately." },
      { q: "What is an MX record?", a: "An MX (mail exchanger) record tells the internet which server receives email for your domain. If your MX records are incorrect or missing, email sent to your domain may not arrive." },
      { q: "How long does it take for DNS changes to propagate?", a: "DNS changes can take up to 48 hours to propagate globally, though most changes are visible within a few hours." },
    ],
    howItWorks: ["Enter your domain", "We query public DNS servers for your records", "See all your DNS records in plain language", "Identify issues or unexpected configurations"],
  },
  "email-security-checker": {
    slug: "email-security-checker",
    metaTitle: "Free Email Security Checker — SPF, DKIM & DMARC | Presence",
    metaDescription: "Check your email security configuration for free. Verify SPF, DKIM and DMARC records to protect your business from email spoofing.",
    h1: "Free Email Security Checker",
    intro: "Check your SPF, DKIM and DMARC email security configuration in seconds. Protect your business email from spoofing and impersonation — explained in plain language.",
    inputPlaceholder: "example.com",
    inputLabel: "Your domain",
    buttonLabel: "Check email security",
    checks: ["SPF record", "DKIM record", "DMARC policy", "DMARC enforcement level", "Email reputation"],
    resultChecks: [
      { label: "SPF record configured", status: "healthy" },
      { label: "DKIM record found", status: "healthy" },
      { label: "DMARC record present", status: "warning" },
      { label: "DMARC enforcement: none (low protection)", status: "warning" },
      { label: "No blocklist entries", status: "healthy" },
    ],
    relatedTool: { label: "Check DNS records", path: "/tools/dns-checker" },
    featurePath: "/features/email-security",
    faqItems: [
      { q: "What do SPF, DKIM and DMARC do?", a: "SPF specifies which servers are allowed to send email from your domain. DKIM adds a cryptographic signature to verify emails are authentic. DMARC tells email providers what to do when an email fails SPF or DKIM checks — and allows you to receive reports about fraudulent use of your domain." },
      { q: "My business is small. Do I really need DMARC?", a: "Yes. Email impersonation doesn't only target large companies. Criminals impersonate small business emails to scam suppliers, customers, and staff. DMARC is free to implement and significantly reduces this risk." },
      { q: "What does 'DMARC policy: none' mean?", a: "A DMARC policy of 'none' means you're monitoring but not enforcing. Emails that fail verification are still delivered. Upgrading to 'quarantine' or 'reject' provides actual protection against spoofed emails." },
      { q: "Can this checker fix my email security?", a: "The checker identifies issues and recommends what to add or change. Implementing the changes requires adding DNS records at your domain registrar or hosting provider — or asking your web developer to do so." },
    ],
    howItWorks: ["Enter your domain", "We look up your email security DNS records", "Results show what's configured and what's missing", "Plain-language recommendations for each finding"],
  },
};

type CheckStatus = "healthy" | "warning" | "neutral";

const statusStyles: Record<CheckStatus, { icon: string; bg: string; text: string }> = {
  healthy: { icon: "🟢", bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-800" },
  warning: { icon: "🟠", bg: "bg-amber-50 border-amber-200", text: "text-amber-800" },
  neutral: { icon: "⚪", bg: "bg-slate-50 border-slate-200", text: "text-slate-700" },
};

function ToolContent({ config }: { config: ToolConfig }) {
  const [domain, setDomain] = useState("");
  const [scanning, setScanning] = useState(false);
  const [done, setDone] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const runCheck = () => {
    if (!domain.trim()) return;
    setScanning(true);
    setDone(false);
    setTimeout(() => { setScanning(false); setDone(true); }, 2200);
  };

  const score = 74;

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={config.metaTitle}
        description={config.metaDescription}
        path={`/tools/${config.slug}`}
        structuredData={[
          { "@context": "https://schema.org", "@type": "WebApplication", name: config.h1, url: `https://presence.io/tools/${config.slug}`, applicationCategory: "BusinessApplication", offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" } },
          faqSchema(config.faqItems),
          breadcrumbSchema([
            { name: "Home", url: "/" },
            { name: "Free tools", url: "/tools/website-checker" },
            { name: config.h1, url: `/tools/${config.slug}` },
          ]),
        ]}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3" fill="white" /></svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/tools/website-checker" className="hover:text-slate-900">Free checker</Link>
            <Link to="/#features" className="hover:text-slate-900">Features</Link>
            <Link to="/pricing" className="hover:text-slate-900">Pricing</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-slate-600 hover:text-slate-900">Log in</Link>
            <Link to="/register"><button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">Get started</button></Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero + tool */}
        <section className="pt-14 pb-20 px-4 bg-gradient-to-b from-indigo-50/40 to-white">
          <div className="max-w-2xl mx-auto">
            <Breadcrumb items={[
              { label: "Home", path: "/" },
              { label: "Free tools", path: "/tools/website-checker" },
              { label: config.h1, path: `/tools/${config.slug}` },
            ]} />
            <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">{config.h1}</h1>
            <p className="text-lg text-slate-500 mb-8">{config.intro}</p>

            {/* Tool input */}
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
              <label htmlFor="domain-input" className="block text-sm font-medium text-slate-700 mb-2">{config.inputLabel}</label>
              <div className="flex gap-3 flex-col sm:flex-row">
                <div className="flex-1 flex items-center border border-slate-300 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent bg-white">
                  <div className="pl-3 text-slate-400"><Globe size={16} /></div>
                  <input
                    id="domain-input"
                    type="text"
                    placeholder={config.inputPlaceholder}
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && runCheck()}
                    className="flex-1 px-3 py-3 text-sm bg-transparent focus:outline-none placeholder:text-slate-400"
                    aria-label={config.inputLabel}
                  />
                </div>
                <button
                  onClick={runCheck}
                  disabled={scanning || !domain.trim()}
                  className="px-5 py-3 bg-indigo-600 text-white font-semibold text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-60 transition-colors flex items-center gap-2 whitespace-nowrap"
                >
                  {scanning && <Loader size={14} className="animate-spin" />}
                  {config.buttonLabel}
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-2">No account required. Results in seconds.</p>

              {/* Scanning state */}
              {scanning && (
                <div className="mt-5 pt-5 border-t border-slate-100">
                  <div className="flex items-center gap-3 text-slate-600">
                    <Loader size={16} className="animate-spin text-indigo-600" />
                    <span className="text-sm font-medium">Checking {domain}...</span>
                  </div>
                  <div className="mt-3 space-y-1.5">
                    {config.checks.map((c, i) => (
                      <div key={c} className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" style={{ animationDelay: `${i * 0.15}s` }} />
                        {c}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Results */}
              {done && (
                <div className="mt-5 pt-5 border-t border-slate-100">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-sm font-semibold text-slate-800">Results for <span className="text-indigo-600">{domain}</span></p>
                    <div className="flex items-center gap-2">
                      <span className={`text-lg font-black ${score >= 80 ? "text-emerald-600" : score >= 60 ? "text-amber-600" : "text-red-600"}`}>{score}</span>
                      <span className="text-xs text-slate-400">/ 100</span>
                    </div>
                  </div>
                  <div className="space-y-2 mb-5">
                    {config.resultChecks.map(({ label, status }) => (
                      <div key={label} className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm font-medium ${statusStyles[status].bg} ${statusStyles[status].text}`}>
                        <span>{statusStyles[status].icon}</span>
                        {label}
                      </div>
                    ))}
                  </div>
                  <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-xl">
                    <p className="text-sm font-semibold text-indigo-800 mb-2">Want continuous monitoring?</p>
                    <p className="text-sm text-indigo-700 mb-3">This was a one-time check. Presence can monitor your website automatically and alert you when something changes.</p>
                    <div className="flex gap-3 flex-wrap">
                      <Link to="/register"><button className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2">Create free account <ArrowRight size={14} /></button></Link>
                      <Link to="/pricing"><button className="px-4 py-2 border border-indigo-300 text-indigo-700 text-sm font-semibold rounded-lg hover:bg-indigo-100 transition-colors">View pricing</button></Link>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* What we check */}
        <section className="py-16 px-4 bg-slate-50 border-y border-slate-100">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">What this tool checks</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {config.checks.map((c) => (
                <div key={c} className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3">
                  <CheckCircle size={15} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-sm text-slate-700">{c}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="py-16 px-4">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">How it works</h2>
            <ol className="space-y-4">
              {config.howItWorks.map((step, i) => (
                <li key={i} className="flex items-start gap-4">
                  <span className="w-7 h-7 bg-indigo-600 text-white text-sm font-bold rounded-full flex items-center justify-center flex-shrink-0">{i + 1}</span>
                  <p className="text-slate-700 pt-0.5">{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 px-4 bg-slate-50">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Frequently asked questions</h2>
            <div className="space-y-3">
              {config.faqItems.map((faq, i) => (
                <div key={i} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <button
                    className="w-full flex items-center justify-between px-5 py-4 text-left"
                    onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                    aria-expanded={activeFaq === i}
                  >
                    <span className="font-medium text-slate-900 text-sm">{faq.q}</span>
                    <ChevronDown size={15} className={`text-slate-400 flex-shrink-0 transition-transform ${activeFaq === i ? "rotate-180" : ""}`} />
                  </button>
                  {activeFaq === i && (
                    <div className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">{faq.a}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Related tools + feature link */}
        <section className="py-12 px-4">
          <div className="max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 p-6 bg-indigo-50 border border-indigo-100 rounded-2xl">
            <div>
              <p className="font-semibold text-indigo-900">Want automatic monitoring?</p>
              <p className="text-sm text-indigo-700 mt-1">Presence monitors your website 24/7 and alerts you when something changes.</p>
            </div>
            <div className="flex gap-3 flex-shrink-0">
              {config.relatedTool && (
                <Link to={config.relatedTool.path}>
                  <button className="px-4 py-2.5 border border-indigo-300 text-indigo-700 text-sm font-semibold rounded-xl hover:bg-indigo-100 transition-colors">{config.relatedTool.label}</button>
                </Link>
              )}
              <Link to="/register">
                <button className="px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-1.5">Start free <ArrowRight size={14} /></button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">© 2026 Presence — <Link to="/" className="hover:text-slate-600">Home</Link> · <Link to="/pricing" className="hover:text-slate-600">Pricing</Link> · <Link to="/faq" className="hover:text-slate-600">FAQ</Link></p>
      </footer>
    </div>
  );
}

export default function ToolPage({ tool }: { tool: string }) {
  const config = toolConfigs[tool];
  if (!config) return <div className="p-8 text-center text-slate-500">Tool not found.</div>;
  return <ToolContent config={config} />;
}
