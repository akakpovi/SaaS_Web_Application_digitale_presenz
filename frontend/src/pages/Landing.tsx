import { PublicScanForm } from "../components/PublicScanForm";
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle, ChevronDown, Globe, Shield, Mail, Zap, Bell, Star, FileText, ArrowRight, Play, Activity } from "lucide-react";
import { Button } from "../components/ui";

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

const trustedBy = ["Restaurants", "Cafés", "Barbershops", "Beauty Salons", "Hotels", "Auto Repair", "Freelancers", "Agencies", "Real Estate"];

const features = [
  { icon: Globe, titleKey: "feature_website_monitoring", descKey: "feature_website_monitoring_desc", color: "bg-indigo-50 text-indigo-600" },
  { icon: Shield, titleKey: "feature_ssl_monitoring", descKey: "feature_ssl_monitoring_desc", color: "bg-emerald-50 text-emerald-600" },
  { icon: Zap, titleKey: "feature_dns_monitoring", descKey: "feature_dns_monitoring_desc", color: "bg-amber-50 text-amber-600" },
  { icon: Mail, titleKey: "feature_email_security", descKey: "feature_email_security_desc", color: "bg-blue-50 text-blue-600" },
  { icon: Activity, titleKey: "feature_performance_monitoring", descKey: "feature_performance_monitoring_desc", color: "bg-purple-50 text-purple-600" },
  { icon: Shield, titleKey: "feature_security_headers", descKey: "feature_security_headers_desc", color: "bg-rose-50 text-rose-600" },
  { icon: Bell, titleKey: "feature_uptime_monitoring", descKey: "feature_uptime_monitoring_desc", color: "bg-cyan-50 text-cyan-600" },
  { icon: Star, titleKey: "feature_reviews", descKey: "feature_reviews_desc", color: "bg-yellow-50 text-yellow-600" },
  { icon: FileText, titleKey: "feature_reports", descKey: "feature_reports_desc", color: "bg-slate-50 text-slate-600" },
];

const stepKeys = [1, 2, 3];
const stepIcons = [Globe, CheckCircle, Bell];

function NavBar({ t, i18n }: { t: (key: string) => string; i18n: any }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const languages = [
    { code: 'en', label: 'EN' },
    { code: 'de', label: 'DE' },
    { code: 'fr', label: 'FR' },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-8">
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

        <nav className="hidden md:flex items-center gap-6 flex-1">
          <a href="#features" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">{t('landing.features')}</a>
          <a href="#how" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">{t('landing.how_it_works')}</a>
          <a href="#pricing" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">{t('landing.pricing')}</a>
          <a href="#faq" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">{t('landing.faq')}</a>
        </nav>

        <div className="hidden md:flex items-center gap-3 ml-auto">
          <div className="flex items-center gap-1">
            {languages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => i18n.changeLanguage(lang.code)}
                className={`px-2 py-1 text-xs font-medium rounded transition ${
                  i18n.language === lang.code
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
          <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2">
            {t('auth.login')}
          </Link>
          <Link to="/register">
            <Button size="sm">{t('auth.get_started')}</Button>
          </Link>
        </div>

        <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden ml-auto text-slate-600">
          <ChevronDown size={20} className={`transition-transform ${menuOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t border-slate-100 bg-white px-4 py-4 flex flex-col gap-3">
          <a href="#features" className="text-sm text-slate-700 py-2">{t('landing.features')}</a>
          <a href="#how" className="text-sm text-slate-700 py-2">{t('landing.how_it_works')}</a>
          <a href="#pricing" className="text-sm text-slate-700 py-2">{t('landing.pricing')}</a>
          <a href="#faq" className="text-sm text-slate-700 py-2">{t('landing.faq')}</a>
          <div className="pt-2 border-t border-slate-100 flex gap-3">
            <Link to="/login" className="flex-1"><Button variant="outline" className="w-full">{t('auth.login')}</Button></Link>
            <Link to="/register" className="flex-1"><Button className="w-full">{t('auth.get_started')}</Button></Link>
          </div>
        </div>
      )}
    </header>
  );
}

function HeroDashboard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-400" />
          <span className="w-3 h-3 rounded-full bg-amber-400" />
          <span className="w-3 h-3 rounded-full bg-emerald-400" />
        </div>
        <div className="flex-1 mx-4 bg-white border border-slate-200 rounded-lg px-3 py-1 text-xs text-slate-400">app.presence.io/dashboard</div>
      </div>

      <div className="p-5 bg-slate-50">
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

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Your websites</p>
          </div>
          {[
            { domain: "example.de", status: "🟢 Online", score: 92, uptime: "99.99%", ssl: "✅ Valid" },
            { domain: "example.com", status: "🟢 Online", score: 82, uptime: "99.98%", ssl: "✅ Valid" },
            { domain: "example-shop.de", status: "🟠 Attention", score: 64, uptime: "98.91%", ssl: "⚠️ Expires soon" },
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

function FeatureCard({ icon: Icon, title, description, color }: { icon: React.FC<{ size?: number; className?: string }>, title: string, description: string, color: string }) {
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
  const [deferredPrompt, setDeferredPrompt] = React.useState<any>(null);

  React.useEffect(() => {
    const handler = (e: any) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstallPWA = () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(() => setDeferredPrompt(null));
    } else {
      alert("Sur ordinateur : cliquez sur l\'icône ⊕ dans la barre d\'adresse de votre navigateur.\nSur mobile : appuyez sur Partager / Menu puis \'Ajouter à l\'écran d\'accueil\'.");
    }
  };

  const { t, i18n } = useTranslation();
  const [domain, setDomain] = useState("");
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const faqItems = [1, 2, 3, 4, 5].map(i => ({
    q: t(`landing.faq_q_${i}`),
    a: t(`landing.faq_a_${i}`)
  }));

  return (
    <div className="min-h-full bg-white">
      <NavBar t={t} i18n={i18n} />

      {/* Hero */}
      <section className="pt-20 pb-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium mb-8 border border-indigo-100">
              <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
              {t('landing.hero_subtitle')}
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-slate-900 leading-tight mb-6">
              {t('landing.hero_title')}
            </h1>
            <p className="text-xl text-slate-500 leading-relaxed mb-10">
              Monitor your website, SSL, domain, email security and online reputation from one simple dashboard.
            </p>

            <PublicScanForm className="mb-6" />
          </div>

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
            {trustedBy.map(t => (
              <span key={t} className="px-4 py-2 bg-white border border-slate-200 rounded-full">{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">{t('landing.how_it_works_title')}</h2>
            <p className="text-lg text-slate-500">No technical knowledge required.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {stepKeys.map((step, idx) => {
              const Icon = stepIcons[idx];
              return (
                <div key={step} className="relative">
                  <div className="flex items-start gap-5">
                    <div className="flex-shrink-0">
                      <span className="text-5xl font-black text-indigo-100 leading-none">0{step}</span>
                    </div>
                    <div className="pt-2">
                      <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
                        <Icon size={18} className="text-white" />
                      </div>
                      <h3 className="font-bold text-slate-900 text-lg mb-2">{t(`landing.step_${step}_title`)}</h3>
                      <p className="text-slate-500">{t(`landing.step_${step}_desc`)}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Health Score */}
      <section className="py-24 px-4 bg-indigo-600">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="text-white">
              <h2 className="text-4xl font-bold mb-4">One score. Everything you need to know.</h2>
              <p className="text-indigo-200 text-lg mb-8">
                Your Digital Health Score tells you at a glance whether your digital presence is healthy or needs attention.
              </p>
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
            <h2 className="text-4xl font-bold text-slate-900 mb-4">{t('landing.features_title')}</h2>
            <p className="text-lg text-slate-500">We monitor your digital presence so you don't have to.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f) => (
              <FeatureCard key={f.titleKey} icon={f.icon} title={t(`landing.${f.titleKey}`)} description={t(`landing.${f.descKey}`)} color={f.color} />
            ))}
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
                <Button onClick={handleInstallPWA}>📲 Installer l'application Presence</Button>
                <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-slate-800">
                  <Play size={16} /> Learn about the PWA
                </Button>
              </div>
            </div>
            <div className="flex justify-center">
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
            {/* Pricing Section - Mode 100% Gratuit */}
      <section id="pricing" className="py-20 bg-slate-50 border-y border-slate-100">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold uppercase tracking-wider mb-4">
            ✨ Offre de Lancement
          </div>
          <h2 className="text-3xl font-bold text-slate-900 tracking-tight sm:text-4xl">
            Un outil professionnel, <span className="text-indigo-600">100% Gratuit.</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600 max-w-2xl mx-auto">
            Pas d'abonnements, pas de frais cachés. Presence SaaS est financé par des partenariats et sponsors non intrusifs.
          </p>

          <div className="mt-12 bg-white border border-slate-200 rounded-3xl p-8 shadow-xl max-w-2xl mx-auto text-left relative overflow-hidden">
            <div className="absolute top-0 right-0 bg-indigo-600 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider">
              Accès Complet
            </div>
            
            <div className="flex items-baseline justify-between gap-4 border-b border-slate-100 pb-6 mb-6">
              <div>
                <h3 className="text-2xl font-bold text-slate-900">Plan Gratuit & Illimité</h3>
                <p className="text-xs text-slate-500 mt-1">Surveillez vos sites sans sortir de carte bancaire</p>
              </div>
              <div className="text-right">
                <span className="text-4xl font-black text-slate-900">0€</span>
                <span className="text-xs text-slate-500 font-medium"> / mois</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Surveillance de sites illimitée</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Audits & Optimisation SEO</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Scanner de Sécurité complet</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Alertes Emails instantanées</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Contrôles SSL & Performances</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span className="text-sm text-slate-700">Rapports PDF & Historique</span>
              </div>
            </div>

            <Link
              to="/register"
              className="block w-full py-3.5 px-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-center shadow-lg shadow-indigo-100 transition-all text-sm"
            >
              Créer mon compte gratuit maintenant
            </Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24 px-4 bg-slate-50">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">{t('landing.faq_title')}</h2>
          </div>
          <div className="space-y-3">
            {faqItems.map((faq, i) => (
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
          <h2 className="text-4xl font-bold text-slate-900 mb-4">{t('landing.cta_title')}</h2>
          <p className="text-lg text-slate-500 mb-8">{t('landing.cta_subtitle')}</p>
          <div className="flex justify-center gap-4">
            <Link to="/register"><Button size="lg">{t('auth.get_started')} <ArrowRight size={16} /></Button></Link>
            <Link to="/login"><Button variant="outline" size="lg">{t('auth.login')}</Button></Link>
          </div>
          <p className="text-sm text-slate-400 mt-4">{t('landing.no_credit_card')}</p>
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
            <p className="text-xs text-slate-400">© 2026 Presence. {t('landing.footer.rights')}</p>
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

