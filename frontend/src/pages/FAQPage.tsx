import React, { useState } from 'react';
import { Link } from "react-router-dom";
import { ChevronDown, ArrowRight } from "lucide-react";
import SEO, { faqSchema } from "../components/SEO";

const faqs = [
  {
    category: "General",
    items: [
      { q: "What is website monitoring?", a: "Website monitoring is the automated, continuous process of checking whether your website is accessible, performing well, and correctly configured. A monitoring service like Presence checks your website regularly — every hour or more — and alerts you immediately if something goes wrong." },
      { q: "Why should I monitor my website?", a: "Your website is often the first thing a potential customer sees. If it's offline, loading slowly, or showing a security warning, visitors leave immediately. Website monitoring ensures you're always the first to know about problems — before your customers notice." },
      { q: "Does Presence work for small businesses?", a: "Absolutely. Presence is designed specifically for small business owners who don't have a technical team. Everything is explained in plain language, and you don't need any technical knowledge to use it." },
      { q: "Is Presence suitable for restaurants?", a: "Yes. Presence is perfect for restaurants, cafés and local businesses. It monitors your website, checks your SSL certificate, and alerts you instantly if your site goes down — so you never miss a customer booking or online order." },
      { q: "Can I use Presence if my business is based in Germany?", a: "Absolutely. Presence works for any website, anywhere in the world. Many of our users are restaurants, shops and Geschäfte in Germany, Austria and Switzerland. The platform is available in English, German, French and Spanish." },
      { q: "Funktioniert Presence für kleine Restaurants und Geschäfte?", a: "Ja. Presence wurde speziell für Kleinunternehmen wie Restaurants, Cafés, Bäckereien und Ladengeschäfte entwickelt. Sie müssen kein technisches Wissen mitbringen — alles wird in einfacher Sprache erklärt." },
      { q: "Does Presence change or access my website?", a: "No. Presence only checks publicly available information about your website — the same information a visitor or search engine would see. We never access your files, database, or CMS." },
    ],
  },
  {
    category: "Monitoring",
    items: [
      { q: "How often is my website checked?", a: "On the Pro plan, your website is checked every hour automatically. On the Business plan, checks happen even more frequently. On the Free plan, you can run checks manually at any time." },
      { q: "What does Presence monitor?", a: "Presence monitors website availability, SSL certificate validity, DNS configuration, email security (SPF, DKIM, DMARC), security headers, website performance, uptime statistics, and online reviews." },
      { q: "How does uptime monitoring work?", a: "Presence sends a request to your website on a regular schedule and records whether your website responded successfully. The results are compiled into your uptime history, giving you an accurate record of your website availability over time." },
      { q: "What happens if my website goes offline?", a: "You receive an immediate alert by email or push notification. Presence continues monitoring and sends another notification as soon as your website comes back online." },
      { q: "Can I monitor multiple websites?", a: "Yes. Depending on your plan, you can monitor 1, 10, or 50 websites from the same dashboard." },
    ],
  },
  {
    category: "SSL & Security",
    items: [
      { q: "How does SSL monitoring work?", a: "Presence checks your SSL certificate every day. It verifies that your certificate is valid, trusted by major browsers, and tracks its expiry date. You receive an alert 30 days before your certificate expires." },
      { q: "What is DNS monitoring?", a: "DNS monitoring tracks your domain's DNS records and alerts you when they change unexpectedly. Unexpected DNS changes can indicate account compromises, configuration errors, or unauthorized modifications." },
      { q: "What are SPF, DKIM and DMARC?", a: "SPF, DKIM and DMARC are email authentication standards that protect your domain from email spoofing. SPF specifies which servers can send email on your behalf. DKIM adds a cryptographic signature to your emails. DMARC tells email providers what to do with unauthenticated emails." },
      { q: "Why is email security important for small businesses?", a: "Without proper email security, anyone can send emails that appear to come from your domain — phishing your customers and damaging your reputation. SPF, DKIM and DMARC significantly reduce this risk." },
      { q: "What are security headers?", a: "Security headers are HTTP response headers that instruct browsers to behave safely. Common examples include X-Frame-Options (prevents your site from being embedded in iframes), Content-Security-Policy (restricts which resources can load), and HSTS (forces HTTPS)." },
    ],
  },
  {
    category: "PWA & App",
    items: [
      { q: "Can I install Presence as a mobile app?", a: "Yes. Presence is a Progressive Web App (PWA). You can install it on your iPhone, Android phone, or computer directly from your browser — no app store required. It works like a native app with push notifications." },
      { q: "How do I install Presence on my phone?", a: "On Android: open Presence in Chrome and tap 'Add to home screen' in the browser menu. On iOS: open Presence in Safari, tap the Share button, and select 'Add to Home Screen'." },
      { q: "Does the PWA work offline?", a: "Yes. Presence caches your most recent dashboard data so you can view it even when you're offline. The data will be updated as soon as your connection is restored." },
    ],
  },
  {
    category: "Billing & Plans",
    items: [
      { q: "Can I cancel anytime?", a: "Yes. There are no long-term contracts. You can cancel your subscription at any time from your account settings. Your account remains active until the end of the current billing period." },
      { q: "Is there a free trial?", a: "All paid plans include a 14-day free trial. No credit card is required to start your trial." },
      { q: "What's included in the free plan?", a: "The free plan includes 1 website, manual checks, and a basic monthly report. It's a great way to start and see what Presence can do before upgrading." },
      { q: "Is my data secure?", a: "Yes. Presence collects only the information necessary to monitor your digital presence. We use encrypted connections, secure data storage, and are GDPR compliant." },
    ],
  },
];

const allFaqItems = faqs.flatMap(c => c.items);

export default function FAQPage() {
  const [active, setActive] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filtered = search.trim()
    ? allFaqItems.filter(f => f.q.toLowerCase().includes(search.toLowerCase()) || f.a.toLowerCase().includes(search.toLowerCase()))
    : null;

  return (
    <div className="min-h-full bg-white">
      <SEO
        title="Website Monitoring FAQ | Presence"
        description="Answers to common questions about website monitoring, SSL, DNS, email security, uptime and the Presence platform."
        path="/faq"
        structuredData={faqSchema(allFaqItems)}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3" fill="white" /></svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/#features" className="hover:text-slate-900">Features</Link>
            <Link to="/pricing" className="hover:text-slate-900">Pricing</Link>
            <Link to="/tools/website-checker" className="hover:text-slate-900">Free checker</Link>
          </nav>
          <Link to="/register"><button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">Get started</button></Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-16">
        <h1 className="text-4xl font-bold text-slate-900 mb-4">Frequently asked questions</h1>
        <p className="text-lg text-slate-500 mb-8">Everything you need to know about Presence and website monitoring.</p>

        {/* Search */}
        <div className="mb-10">
          <input
            type="search"
            placeholder="Search questions..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full px-4 py-3 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            aria-label="Search FAQ"
          />
        </div>

        {/* Search results */}
        {filtered ? (
          <div className="space-y-3">
            {filtered.length === 0 ? (
              <p className="text-slate-500 text-sm">No results found for "{search}".</p>
            ) : filtered.map((faq, i) => {
              const key = `s-${i}`;
              return (
                <article key={key} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <button className="w-full flex items-center justify-between px-5 py-4 text-left" onClick={() => setActive(active === key ? null : key)} aria-expanded={active === key}>
                    <span className="font-medium text-slate-900">{faq.q}</span>
                    <ChevronDown size={16} className={`text-slate-400 flex-shrink-0 transition-transform ${active === key ? "rotate-180" : ""}`} />
                  </button>
                  {active === key && <div className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">{faq.a}</div>}
                </article>
              );
            })}
          </div>
        ) : (
          /* Categorized */
          <div className="space-y-10">
            {faqs.map(({ category, items }) => (
              <section key={category} aria-labelledby={`cat-${category}`}>
                <h2 id={`cat-${category}`} className="text-lg font-bold text-slate-800 mb-4">{category}</h2>
                <div className="space-y-2">
                  {items.map((faq, i) => {
                    const key = `${category}-${i}`;
                    return (
                      <article key={key} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                        <button className="w-full flex items-center justify-between px-5 py-4 text-left" onClick={() => setActive(active === key ? null : key)} aria-expanded={active === key}>
                          <span className="font-medium text-slate-900">{faq.q}</span>
                          <ChevronDown size={16} className={`text-slate-400 flex-shrink-0 transition-transform ${active === key ? "rotate-180" : ""}`} />
                        </button>
                        {active === key && <div className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">{faq.a}</div>}
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}

        {/* CTA */}
        <div className="mt-16 p-6 bg-indigo-50 border border-indigo-100 rounded-2xl flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1">
            <p className="font-semibold text-indigo-900">Still have questions?</p>
            <p className="text-sm text-indigo-700 mt-1">Check your website for free — no account required.</p>
          </div>
          <Link to="/tools/website-checker">
            <button className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2 whitespace-nowrap">
              Check your website <ArrowRight size={14} />
            </button>
          </Link>
        </div>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center mt-8">
        <p className="text-sm text-slate-400">© 2026 Presence — <Link to="/" className="hover:text-slate-600">Home</Link> · <Link to="/pricing" className="hover:text-slate-600">Pricing</Link> · <Link to="/about" className="hover:text-slate-600">About</Link></p>
      </footer>
    </div>
  );
}
