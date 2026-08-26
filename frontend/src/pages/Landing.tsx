import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { CheckCircle, ChevronDown, Globe, Shield, Mail, Zap, Bell, Star, FileText, ArrowRight, Play, Activity } from "lucide-react";
import { Button } from "../components/ui";
import SEO, { organizationSchema, websiteSchema, softwareAppSchema, faqSchema } from "../components/SEO";

const plans = [
  {
    name: "Free",
    price: "€0",
    period: "/month",
    description: "Get started with basic monitoring",
    features: ["1 website", "Manual checks", "Basic report", "Email alerts"],
    cta: "Start free",
    path: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "€5.99",
    period: "/month",
    description: "For growing businesses",
    features: ["10 websites", "Automatic monitoring", "Email & push alerts", "PDF reports", "History", "Advanced checks"],
    cta: "Start Pro",
    path: "/register",
    highlight: true,
  },
  {
    name: "Business",
    price: "€14.99",
    period: "/month",
    description: "For agencies and multiple locations",
    features: ["50 websites", "Hourly monitoring", "Review monitoring", "Multiple users", "Priority support", "Advanced analytics"],
    cta: "Start Business",
    path: "/register",
    highlight: false,
  },
];

const faqs = [
  { q: "What does Presence monitor?", a: "Presence monitors your website availability, SSL certificate, DNS configuration, email security, security headers, uptime, performance, and online reviews — all from one simple dashboard." },
  { q: "Do I need technical knowledge?", a: "Not at all. Presence is designed specifically for non-technical business owners. Everything is explained in plain language, and technical details are always optional." },
  { q: "Does Presence change my website?", a: "No. Presence only reads publicly available information about your website. It never modifies or accesses your website files or code." },
  { q: "How often is my website checked?", a: "On the Pro plan, your website is checked every hour automatically. On the Business plan, checks happen even more frequently. On the Free plan, you can run checks manually." },
  { q: "What happens if my website goes offline?", a: "You'll receive an immediate alert via email or push notification. Presence will continue monitoring and notify you again when your website comes back online." },
  { q: "Can I monitor multiple websites?", a: "Yes. Depending on your plan, you can monitor 1, 10, or 50 websites. You can add websites from your settings at any time." },
  { q: "Can I install Presence as an app?", a: "Yes! Presence is available as a Progressive Web App (PWA). You can install it on your phone, tablet, or computer for faster access and push notifications." },
  { q: "Can I cancel anytime?", a: "Yes. There are no long-term contracts. You can cancel your subscription at any time from your account settings." },
];


const LANGS = [
  { code: "en", label: "EN", full: "English" },
  { code: "fr", label: "FR", full: "Français" },
  { code: "de", label: "DE", full: "Deutsch" },
  { code: "es", label: "ES", full: "Español" },
];

function LangPicker() {
  const [lang, setLangState] = useState<string>(
    () => localStorage.getItem("presence_lang") ?? "en"
  );
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = () => setLangState(localStorage.getItem("presence_lang") ?? "en");
    window.addEventListener("presence_lang_change", handler);
    return () => window.removeEventListener("presence_lang_change", handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  const handleChange = (code: string) => {
    localStorage.setItem("presence_lang", code);
    setLangState(code);
    window.dispatchEvent(new Event("presence_lang_change"));
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors"
      >
        {current.label} <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-32 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => handleChange(l.code)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
                lang === l.code ? "bg-indigo-50 text-indigo-700 font-semibold" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              {lang === l.code ? "✓ " : "  "}{l.full}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-8">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="1.5" opacity="0.5" />
              <circle cx="8" cy="8" r="3" fill="white" />
              <path d="M8 2v2M8 12v2M2 8h2M12 8h2" stroke="white" strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
            </svg>
          </div>
          <span className="font-bold text-slate-900 text-base">Presence</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 flex-1">
          <a href="#features" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">Features</a>
          <a href="#how" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">How it works</a>
          <a href="#pricing" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">Pricing</a>
          <a href="#faq" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">FAQ</a>
        </nav>

        <div className="hidden md:flex items-center gap-3 ml-auto">
          <LangPicker />
          <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2">
            Log in
          </Link>
          <Link to="/register">
            <Button size="sm">Get started</Button>
          </Link>
        </div>

        <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden ml-auto text-slate-600">
          <ChevronDown size={20} className={`transition-transform ${menuOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t border-slate-100 bg-white px-4 py-4 flex flex-col gap-3">
          <a href="#features" className="text-sm text-slate-700 py-2">Features</a>
          <a href="#how" className="text-sm text-slate-700 py-2">How it works</a>
          <a href="#pricing" className="text-sm text-slate-700 py-2">Pricing</a>
          <a href="#faq" className="text-sm text-slate-700 py-2">FAQ</a>
          <div className="pt-2 border-t border-slate-100 flex gap-3">
            <Link to="/login" className="flex-1"><Button variant="outline" className="w-full">Log in</Button></Link>
            <Link to="/register" className="flex-1"><Button className="w-full">Get started</Button></Link>
          </div>
        </div>
      )}
    </header>
  );
}

function HeroDashboard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-400" />
          <span className="w-3 h-3 rounded-full bg-amber-400" />
          <span className="w-3 h-3 rounded-full bg-emerald-400" />
        </div>
        <div className="flex-1 mx-4 bg-white border border-slate-200 rounded-lg px-3 py-1 text-xs text-slate-400">app.presence.io/dashboard</div>
      </div>

      <div className="p-5 bg-slate-50">
        {/* Score row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center col-span-1">
            <p className="text-xs text-slate-500 mb-1">Digital Health Score</p>
            <p className="text-3xl font-bold text-emerald-600">82</p>
            <p className="text-xs text-slate-400">/ 100 · Good</p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">Uptime</p>
            <p className="text-2xl font-bold text-slate-900">99.98%</p>
            <p className="text-xs text-emerald-600">🟢 Healthy</p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">Websites</p>
            <p className="text-2xl font-bold text-slate-900">3</p>
            <p className="text-xs text-slate-400">monitored</p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">Open Issues</p>
            <p className="text-2xl font-bold text-amber-600">2</p>
            <p className="text-xs text-amber-600">🟠 Attention</p>
          </div>
        </div>

        {/* Website list */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Your websites</p>
          </div>
          {[
            { domain: "restaurant-weber.de", status: "🟢 Online", score: 92, uptime: "99.99%", ssl: "✅ Valid" },
            { domain: "bakery-london.com", status: "🟢 Online", score: 82, uptime: "99.98%", ssl: "✅ Valid" },
            { domain: "boutique-schmidt.de", status: "🟠 Attention", score: 64, uptime: "98.91%", ssl: "⚠️ Expires soon" },
          ].map((site) => (
            <div key={site.domain} className="flex items-center gap-4 px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
              <div className="w-7 h-7 bg-indigo-50 rounded-lg flex items-center justify-center flex-shrink-0">
                <Globe size={14} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900">{site.domain}</p>
                <p className="text-xs text-slate-500">{site.status}</p>
              </div>
              <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
                <span>Score: <span className="font-semibold text-slate-800">{site.score}</span></span>
                <span>Uptime: {site.uptime}</span>
                <span>{site.ssl}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description, color }: { icon: React.FC<{ size?: number; className?: string }>, title: string, description: string, color: string, href?: string }) {
  return (
    <div className="group bg-white border border-slate-200 rounded-2xl p-6 hover:border-indigo-200 hover:shadow-md transition-all duration-200">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${color}`}>
        <Icon size={18} className="text-current" />
      </div>
      <h3 className="font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 leading-relaxed">{description}</p>
    </div>
  );
}

export default function Landing() {
  const [domain, setDomain] = useState("");
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  return (
    <div className="min-h-full bg-white">
      <SEO
        title="Website Monitoring for Restaurants & Small Businesses | Presence"
        description="Monitor your restaurant or shop website automatically. SSL, DNS, uptime and email security from one simple dashboard. Free to start. Trusted by restaurants and small businesses worldwide."
        path="/"
        hreflang={{ en: "/", fr: "/fr/", de: "/de/" }}
        structuredData={[
          organizationSchema,
          websiteSchema,
          softwareAppSchema,
          faqSchema(faqs.map(f => ({ q: f.q, a: f.a }))),
        ]}
      />
      <NavBar />

      {/* Hero */}
      <section className="pt-20 pb-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium mb-8 border border-indigo-100">
              <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
              Website monitoring for restaurants & small businesses
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-slate-900 leading-tight mb-6">
              Your digital presence,{" "}
              <span className="text-indigo-600">always under control.</span>
            </h1>
            <p className="text-xl text-slate-500 leading-relaxed mb-10">
              Monitor your restaurant or shop website automatically. SSL, uptime, DNS, email security and reviews — one simple dashboard, no technical skills needed.
            </p>

            {/* Domain scanner */}
            <div className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto mb-5">
              <div className="flex-1 flex items-center border border-slate-300 rounded-xl overflow-hidden bg-white focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent">
                <div className="pl-4 text-slate-400">
                  <Globe size={16} />
                </div>
                <input
                  type="text"
                  placeholder="yourwebsite.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="flex-1 px-3 py-3 text-sm bg-transparent placeholder:text-slate-400 focus:outline-none"
                />
              </div>
              <Link to="/onboarding">
                <Button size="lg" className="sm:w-auto w-full whitespace-nowrap">
                  Check my website
                  <ArrowRight size={16} />
                </Button>
              </Link>
            </div>
            <p className="text-xs text-slate-400">No credit card required. Free forever plan available.</p>
          </div>

          {/* Dashboard preview */}
          <div className="max-w-4xl mx-auto">
            <HeroDashboard />
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="py-16 border-y border-slate-100 bg-slate-50">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="text-sm font-medium text-slate-400 mb-8 uppercase tracking-widest">Trusted by businesses across Europe</p>
          <div className="flex flex-wrap justify-center gap-4 text-sm text-slate-400 font-medium">
            {["Restaurants", "Cafés", "Barbershops", "Beauty Salons", "Hotels", "Auto Repair", "Freelancers", "Agencies", "Real Estate"].map(t => (
              <span key={t} className="px-4 py-2 bg-white border border-slate-200 rounded-full">{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">Up and running in minutes</h2>
            <p className="text-lg text-slate-500">No technical knowledge required.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: "01", title: "Add your website", desc: "Enter your domain name. That's all you need to get started.", icon: Globe },
              { step: "02", title: "Get your health score", desc: "See what's healthy and what needs attention — in plain language.", icon: CheckCircle },
              { step: "03", title: "Get notified", desc: "Presence monitors your website automatically and alerts you when something changes.", icon: Bell },
            ].map(({ step, title, desc, icon: Icon }) => (
              <div key={step} className="relative">
                <div className="flex items-start gap-5">
                  <div className="flex-shrink-0">
                    <span className="text-5xl font-black text-indigo-100 leading-none">{step}</span>
                  </div>
                  <div className="pt-2">
                    <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
                      <Icon size={18} className="text-white" />
                    </div>
                    <h3 className="font-bold text-slate-900 text-lg mb-2">{title}</h3>
                    <p className="text-slate-500">{desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Health Score */}
      <section className="py-24 px-4 bg-indigo-600">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="text-white">
              <h2 className="text-4xl font-bold mb-4">One score. Everything you need to know.</h2>
              <p className="text-indigo-200 text-lg mb-8">Your Digital Health Score tells you at a glance whether your digital presence is healthy or needs attention.</p>
              <div className="space-y-3">
                {[
                  { label: "Website", score: 20, max: 20 },
                  { label: "SSL certificate", score: 20, max: 20 },
                  { label: "DNS", score: 15, max: 15 },
                  { label: "Email security", score: 10, max: 15 },
                  { label: "Security headers", score: 9, max: 15 },
                  { label: "Performance", score: 8, max: 15 },
                ].map(({ label, score, max }) => (
                  <div key={label} className="flex items-center gap-4">
                    <span className="text-sm text-indigo-200 w-32 flex-shrink-0">{label}</span>
                    <div className="flex-1 h-1.5 bg-indigo-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${score === max ? "bg-emerald-400" : "bg-amber-400"}`}
                        style={{ width: `${(score / max) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-white w-10 text-right">{score}/{max}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex justify-center">
              <div className="bg-white/10 backdrop-blur rounded-3xl p-8 text-center border border-white/20">
                <p className="text-indigo-200 text-sm mb-4">Digital Health Score</p>
                <div className="relative inline-block mb-4">
                  <svg width="160" height="160" viewBox="0 0 160 160">
                    <circle cx="80" cy="80" r="64" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="10" />
                    <circle cx="80" cy="80" r="64" fill="none" stroke="#34d399" strokeWidth="10"
                      strokeDasharray={2 * Math.PI * 64}
                      strokeDashoffset={2 * Math.PI * 64 * (1 - 0.82)}
                      strokeLinecap="round"
                      transform="rotate(-90 80 80)" />
                    <text x="80" y="72" textAnchor="middle" fill="white" fontSize="36" fontWeight="800" fontFamily="Inter">82</text>
                    <text x="80" y="95" textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="14" fontFamily="Inter">/ 100</text>
                  </svg>
                </div>
                <p className="text-emerald-400 font-semibold">Good</p>
                <p className="text-indigo-200 text-sm mt-2">Your digital presence is healthy overall,<br />with a few recommended improvements.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">Everything you need to stay in control</h2>
            <p className="text-lg text-slate-500">We monitor your digital presence so you don't have to.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { icon: Globe, title: "Website Monitoring", description: "Know immediately when your website becomes unavailable.", color: "bg-indigo-50 text-indigo-600", href: "/features/website-monitoring" },
              { icon: Shield, title: "SSL Monitoring", description: "Get notified before your certificate expires.", color: "bg-emerald-50 text-emerald-600", href: "/features/ssl-monitoring" },
              { icon: Zap, title: "DNS Monitoring", description: "Detect important changes to your domain configuration.", color: "bg-amber-50 text-amber-600", href: "/features/dns-monitoring" },
              { icon: Mail, title: "Email Security", description: "Check SPF, DKIM and DMARC configuration — explained simply.", color: "bg-blue-50 text-blue-600", href: "/features/email-security" },
              { icon: Activity, title: "Performance Monitoring", description: "Track website response time and uptime over time.", color: "bg-purple-50 text-purple-600", href: "/features/website-performance" },
              { icon: Shield, title: "Security Headers", description: "Identify missing or weak security-related headers.", color: "bg-rose-50 text-rose-600", href: "/features/security-headers" },
              { icon: Bell, title: "Uptime Monitoring", description: "Track your website availability over time.", color: "bg-cyan-50 text-cyan-600", href: "/features/uptime-monitoring" },
              { icon: Star, title: "Online Reviews", description: "Monitor customer ratings and reviews across platforms.", color: "bg-yellow-50 text-yellow-600", href: "/features/review-monitoring" },
              { icon: FileText, title: "Automatic Reports", description: "Receive clear monthly reports without technical jargon.", color: "bg-slate-50 text-slate-600", href: "/blog/what-is-website-monitoring" },
            ].map(f => <Link key={f.title} to={f.href}><FeatureCard {...f} /></Link>)}
          </div>
        </div>
      </section>

      {/* PWA section */}
      <section className="py-24 px-4 bg-slate-900">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="text-white">
              <h2 className="text-4xl font-bold mb-4">Presence, wherever you are.</h2>
              <p className="text-slate-400 text-lg mb-8">
                Install Presence on your phone or computer and stay informed about your digital presence wherever you work.
              </p>
              <ul className="space-y-3 mb-8">
                {["Instant alerts when something changes", "Works offline with cached data", "Install on iOS, Android, or your computer", "Native-like mobile experience"].map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300">
                    <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <div className="flex gap-3">
                <Button>Install Presence</Button>
                <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-slate-800">
                  <Play size={16} /> Learn about the PWA
                </Button>
              </div>
            </div>
            <div className="flex justify-center">
              {/* Phone mockup */}
              <div className="relative">
                <div className="w-56 bg-slate-800 rounded-3xl border-2 border-slate-700 overflow-hidden shadow-2xl">
                  <div className="h-6 bg-slate-800 flex items-center justify-center">
                    <div className="w-16 h-1 bg-slate-600 rounded-full" />
                  </div>
                  <div className="bg-slate-50 p-4 min-h-80">
                    <div className="bg-white rounded-xl p-3 mb-3 border border-slate-200">
                      <p className="text-xs font-semibold text-slate-900 mb-1">Digital Health</p>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-black text-emerald-600">82</span>
                        <span className="text-xs text-slate-500">/ 100 · Good</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {["example.de 🟢", "example.com 🟢", "example-shop.de 🟠"].map(s => (
                        <div key={s} className="bg-white rounded-lg p-2.5 border border-slate-200 text-xs font-medium text-slate-700">{s}</div>
                      ))}
                    </div>
                    {/* Push notification */}
                    <div className="mt-3 bg-slate-900 text-white rounded-xl p-3 text-xs">
                      <p className="font-semibold mb-0.5">⚠️ SSL expires in 12 days</p>
                      <p className="text-slate-400">example-shop.de</p>
                    </div>
                  </div>
                  <div className="h-8 bg-slate-800 flex items-center justify-center">
                    <div className="w-10 h-1 bg-slate-600 rounded-full" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">Simple, transparent pricing</h2>
            <p className="text-slate-500">Cancel anytime. 14-day free trial on paid plans.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl p-6 border ${plan.highlight ? "border-indigo-500 shadow-xl shadow-indigo-100" : "border-slate-200 bg-white"} ${plan.highlight ? "bg-indigo-600" : ""}`}
              >
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-amber-400 text-amber-900 text-xs font-bold px-3 py-1 rounded-full">Most popular</span>
                  </div>
                )}
                <div className={`mb-4 ${plan.highlight ? "text-white" : "text-slate-900"}`}>
                  <p className={`text-sm font-medium mb-1 ${plan.highlight ? "text-indigo-200" : "text-slate-500"}`}>{plan.name}</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-black">{plan.price}</span>
                    <span className={`text-sm ${plan.highlight ? "text-indigo-300" : "text-slate-400"}`}>{plan.period}</span>
                  </div>
                  <p className={`text-sm mt-1 ${plan.highlight ? "text-indigo-200" : "text-slate-500"}`}>{plan.description}</p>
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm">
                      <CheckCircle size={14} className={plan.highlight ? "text-emerald-400" : "text-emerald-500"} />
                      <span className={plan.highlight ? "text-indigo-100" : "text-slate-600"}>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link to={plan.path}>
                  <button className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-all ${plan.highlight ? "bg-white text-indigo-700 hover:bg-indigo-50" : "bg-indigo-600 text-white hover:bg-indigo-700"}`}>
                    {plan.cta}
                  </button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24 px-4 bg-slate-50">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">Frequently asked questions</h2>
          </div>
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <button
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                  onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                >
                  <span className="font-medium text-slate-900">{faq.q}</span>
                  <ChevronDown
                    size={18}
                    className={`text-slate-400 flex-shrink-0 transition-transform ${activeFaq === i ? "rotate-180" : ""}`}
                  />
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

      {/* CTA */}
      <section className="py-24 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-slate-900 mb-4">Ready to take control of your digital presence?</h2>
          <p className="text-lg text-slate-500 mb-8">Join thousands of restaurants, shops and small businesses monitoring their digital presence with Presence.</p>
          <div className="flex justify-center gap-4">
            <Link to="/register"><Button size="lg">Start for free <ArrowRight size={16} /></Button></Link>
            <Link to="/login"><Button variant="outline" size="lg">Log in</Button></Link>
          </div>
          <p className="text-sm text-slate-400 mt-4">No credit card required.</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="3" fill="white" />
                  </svg>
                </div>
                <span className="font-bold text-slate-900">Presence</span>
              </div>
              <p className="text-sm text-slate-500">Your digital presence, under control.</p>
            </div>
            {[
              { title: "Product", links: ["Features", "Pricing", "Changelog", "Roadmap"] },
              { title: "Company", links: ["About", "Blog", "Careers", "Contact"] },
              { title: "Legal", links: ["Privacy", "Terms", "Cookies", "GDPR"] },
            ].map(col => (
              <div key={col.title}>
                <p className="text-sm font-semibold text-slate-700 mb-3">{col.title}</p>
                <ul className="space-y-2">
                  {col.links.map(l => <li key={l}><a href="#" className="text-sm text-slate-500 hover:text-slate-900">{l}</a></li>)}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-200 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-slate-400">© 2026 Presence. All rights reserved.</p>
            <div className="flex gap-4 text-xs text-slate-400">
              <span>🇪🇺 Made in Europe</span>
              <span>GDPR Compliant</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
