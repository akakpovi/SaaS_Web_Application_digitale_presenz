import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  CheckCircle, 
  Loader, 
  Menu, 
  X, 
  Globe, 
  Shield, 
  Zap, 
  Search, 
  Activity, 
  ChevronDown
} from 'lucide-react';
import { Button, Input, ScoreRing } from '../components/ui';
import SEO, { organizationSchema, softwareAppSchema, faqSchema } from '../components/SEO';
import { PublicScanForm } from '../components/PublicScanForm';
import { useAuth } from '../context/AuthContext';

const checks = [
  "Checking website availability...",
  "Checking SSL certificate...",
  "Checking DNS configuration...",
  "Checking email security...",
  "Checking security headers...",
  "Checking performance...",
  "Calculating your score...",
];

// --- Sub-components ---

function Header() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  
  const currentLang = i18n.language.split('-')[0] || 'fr';

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const changeLanguage = (lang: string) => {
    i18n.changeLanguage(lang);
    setLangOpen(false);
    const path = window.location.pathname.replace(/^\/[a-z]{2}/, `/${lang}`);
    window.history.pushState({}, '', path);
  };

  const navLinks = [
    { name: t('landing.nav.features'), href: '#features' },
    { name: t('landing.nav.pricing'), href: '#pricing' },
    { name: t('landing.nav.faq'), href: '#faq' },
  ];

  return (
    <header className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${isScrolled ? 'bg-white/90 backdrop-blur-md shadow-sm py-3' : 'bg-transparent py-5'}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3.5" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-xl text-slate-900 tracking-tight">Presence</span>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a key={link.name} href={link.href} className="text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors">
                {link.name}
              </a>
            ))}
          </nav>

          <div className="hidden md:flex items-center gap-4">
            <div className="relative">
              <button 
                onClick={() => setLangOpen(!langOpen)}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors"
              >
                <Globe size={16} />
                {currentLang.toUpperCase()}
                <ChevronDown size={14} className={`transition-transform ${langOpen ? 'rotate-180' : ''}`} />
              </button>
              {langOpen && (
                <div className="absolute top-full right-0 mt-2 w-24 bg-white rounded-lg shadow-lg border border-slate-100 py-1">
                  {['fr', 'en', 'de'].map(lang => (
                    <button 
                      key={lang}
                      onClick={() => changeLanguage(lang)}
                      className={`w-full text-left px-4 py-2 text-sm ${currentLang === lang ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                    >
                      {lang.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            {isAuthenticated ? (
              <Link to={`/${currentLang}/app/dashboard`}>
                <Button>Dashboard</Button>
              </Link>
            ) : (
              <>
                <Link to={`/${currentLang}/login`} className="text-sm font-medium text-slate-700 hover:text-indigo-600 transition-colors">
                  {t('landing.nav.login')}
                </Link>
                <Link to={`/${currentLang}/register`}>
                  <Button>{t('landing.nav.register')}</Button>
                </Link>
              </>
            )}
          </div>

          <button className="md:hidden p-2 text-slate-600" onClick={() => setMobileMenuOpen(true)}>
            <Menu size={24} />
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 bg-white">
          <div className="p-4 flex justify-between items-center border-b border-slate-100">
            <span className="font-bold text-xl text-slate-900">Presence</span>
            <button onClick={() => setMobileMenuOpen(false)} className="p-2 text-slate-600">
              <X size={24} />
            </button>
          </div>
          <div className="p-4 flex flex-col gap-4">
            {navLinks.map((link) => (
              <a key={link.name} href={link.href} onClick={() => setMobileMenuOpen(false)} className="text-lg font-medium text-slate-800 py-2 border-b border-slate-50">
                {link.name}
              </a>
            ))}
            <div className="flex gap-4 pt-4">
              <Link to={`/${currentLang}/login`} className="flex-1">
                <Button variant="outline" className="w-full">{t('landing.nav.login')}</Button>
              </Link>
              <Link to={`/${currentLang}/register`} className="flex-1">
                <Button className="w-full">{t('landing.nav.register')}</Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

function Hero() {
  const { t } = useTranslation();
  return (
    <section className="relative pt-32 pb-20 lg:pt-48 lg:pb-32 overflow-hidden bg-slate-50">
      <div className="absolute inset-0 bg-[url('https://presence.io/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))] opacity-20"></div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-sm font-medium mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
          Presence SaaS 2.0
        </div>
        <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold text-slate-900 tracking-tight mb-6 animate-in fade-in slide-in-from-bottom-5 duration-700 delay-100">
          {t('landing.hero.title')}
        </h1>
        <p className="max-w-2xl mx-auto text-lg md:text-xl text-slate-600 mb-10 animate-in fade-in slide-in-from-bottom-6 duration-700 delay-200">
          {t('landing.hero.subtitle')}
        </p>
        
        <div className="max-w-xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300">
          <PublicScanForm className="shadow-xl rounded-xl" />
          <p className="mt-3 text-sm text-slate-500 font-medium">No credit card required. Free forever plan available.</p>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [domain, setDomain] = useState("example.com");
  const [checkIdx, setCheckIdx] = useState(0);

  useEffect(() => {
    if (step === 1) {
      const timer = setInterval(() => {
        setCheckIdx(prev => {
          if (prev < checks.length - 1) return prev + 1;
          clearInterval(timer);
          setTimeout(() => setStep(2), 800);
          return prev;
        });
      }, 700);
      return () => clearInterval(timer);
    }
  }, [step]);

  const reset = () => {
    setStep(0);
    setCheckIdx(0);
  };

  return (
    <section className="py-24 bg-white" id="how-it-works">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-slate-900 mb-4">{t('landing.how_it_works.title')}</h2>
        </div>
        
        <div className="flex flex-col lg:flex-row items-center gap-16">
          <div className="w-full lg:w-1/2 space-y-8">
            {[0, 1, 2].map((i) => (
              <div 
                key={i} 
                className={`flex gap-4 p-6 rounded-2xl transition-all duration-300 ${step === i ? 'bg-indigo-50 border border-indigo-100 shadow-sm' : 'opacity-60'}`}
              >
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold flex-shrink-0 ${step === i ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                  {i + 1}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2">{t(`landing.how_it_works.step${i+1}_title`)}</h3>
                  <p className="text-slate-600 leading-relaxed">{t(`landing.how_it_works.step${i+1}_desc`)}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="w-full lg:w-1/2">
            <div className="bg-slate-50 border border-slate-200 rounded-3xl p-8 shadow-xl max-w-md mx-auto relative overflow-hidden h-[400px] flex flex-col justify-center">
              
              {/* UI Step 0 */}
              <div className={`transition-all duration-500 absolute inset-0 p-8 flex flex-col justify-center bg-white ${step === 0 ? 'opacity-100 z-10' : 'opacity-0 z-0 scale-95'}`}>
                <h4 className="text-lg font-bold text-slate-900 mb-4">Add your website</h4>
                <div className="space-y-4">
                  <Input label="Domain name" placeholder="example.com" value={domain} onChange={setDomain} prefix="https://" />
                  <Button className="w-full" onClick={() => { setStep(1); setCheckIdx(0); }}>Simulate Scan</Button>
                </div>
              </div>

              {/* UI Step 1 */}
              <div className={`transition-all duration-500 absolute inset-0 p-8 flex flex-col justify-center bg-white ${step === 1 ? 'opacity-100 z-10' : 'opacity-0 z-0 scale-95'}`}>
                <div className="flex flex-col items-center mb-6">
                  <Loader size={32} className="text-indigo-600 animate-spin mb-4" />
                  <h4 className="text-lg font-bold text-slate-900">Scanning {domain}...</h4>
                </div>
                <div className="space-y-2">
                  {checks.map((c, i) => (
                    <div key={c} className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${i < checkIdx ? "bg-emerald-50 text-emerald-700" : i === checkIdx ? "bg-indigo-50 text-indigo-700 font-medium" : "text-slate-400"}`}>
                      {i < checkIdx ? <CheckCircle size={14} className="text-emerald-500 flex-shrink-0" /> : i === checkIdx ? <Loader size={14} className="text-indigo-600 animate-spin flex-shrink-0" /> : <div className="w-3.5 h-3.5 rounded-full border border-slate-300 flex-shrink-0" />}
                      {c}
                    </div>
                  )).slice(Math.max(0, checkIdx - 3), Math.max(0, checkIdx - 3) + 4)}
                </div>
              </div>

              {/* UI Step 2 */}
              <div className={`transition-all duration-500 absolute inset-0 p-8 flex flex-col justify-center bg-white text-center ${step === 2 ? 'opacity-100 z-10' : 'opacity-0 z-0 scale-95'}`}>
                <div className="flex justify-center mb-6">
                  <ScoreRing score={92} size={120} label="Health Score" />
                </div>
                <h4 className="text-xl font-bold text-slate-900 mb-2">Report Ready</h4>
                <p className="text-sm text-slate-500 mb-6">Your website is healthy, but there are 2 minor SEO issues.</p>
                <Button variant="outline" className="w-full" onClick={reset}>Scan again</Button>
              </div>

            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Features() {
  const { t } = useTranslation();
  const features = [
    { key: "uptime", icon: <Activity size={24} /> },
    { key: "ssl", icon: <Shield size={24} /> },
    { key: "seo", icon: <Search size={24} /> },
    { key: "security", icon: <Zap size={24} /> },
  ];

  return (
    <section className="py-24 bg-slate-50" id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-slate-900">{t('landing.features.title')}</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((f) => (
            <div key={f.key} className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center mb-6">
                {f.icon}
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">{t(`landing.features.${f.key}.title`)}</h3>
              <p className="text-slate-600">{t(`landing.features.${f.key}.desc`)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  const { t } = useTranslation();
  const plans = ["free", "pro", "business"];

  return (
    <section className="py-24 bg-white" id="pricing">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-slate-900">{t('landing.pricing.title')}</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan, idx) => (
            <div key={plan} className={`p-8 rounded-3xl border ${idx === 1 ? 'bg-slate-900 text-white border-slate-900 shadow-xl scale-105' : 'bg-white text-slate-900 border-slate-200'}`}>
              <h3 className="text-xl font-bold mb-2">{t(`landing.pricing.${plan}.name`)}</h3>
              <p className={`text-sm mb-6 h-10 ${idx === 1 ? 'text-slate-300' : 'text-slate-500'}`}>{t(`landing.pricing.${plan}.desc`)}</p>
              <div className="mb-8">
                <span className="text-4xl font-extrabold">{t(`landing.pricing.${plan}.price`)}</span>
                <span className={`text-sm ${idx === 1 ? 'text-slate-400' : 'text-slate-500'}`}> /mo</span>
              </div>
              <ul className="space-y-4 mb-8">
                {(t(`landing.pricing.${plan}.features`, { returnObjects: true }) as string[]).map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle size={18} className={idx === 1 ? 'text-indigo-400' : 'text-indigo-600'} />
                    <span className="text-sm font-medium">{feature}</span>
                  </li>
                ))}
              </ul>
              <Link to={`/register?plan=${plan}`}>
                <Button variant={idx === 1 ? 'primary' : 'outline'} className={`w-full ${idx === 1 ? 'bg-indigo-500 hover:bg-indigo-400 text-white border-0' : ''}`}>
                  {t(`landing.pricing.${plan}.cta`)}
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FAQ() {
  const { t } = useTranslation();
  return (
    <section className="py-24 bg-slate-50" id="faq">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-slate-900">{t('landing.faq.title')}</h2>
        </div>
        <div className="space-y-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 mb-2">{t(`landing.faq.q${i}`)}</h3>
              <p className="text-slate-600">{t(`landing.faq.a${i}`)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language.split('-')[0] || 'fr';
  
  return (
    <section className="py-24 bg-indigo-600">
      <div className="max-w-4xl mx-auto px-4 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">{t('landing.cta.title')}</h2>
        <p className="text-xl text-indigo-100 mb-10">{t('landing.cta.subtitle')}</p>
        <Link to={`/${currentLang}/register`}>
          <Button size="lg" className="bg-white text-indigo-600 hover:bg-slate-50 border-0 text-lg font-bold px-8">
            {t('landing.cta.button')}
          </Button>
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="bg-slate-900 text-slate-400 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="3.5" fill="white" />
            </svg>
          </div>
          <span className="font-bold text-white tracking-tight">Presence</span>
        </div>
        <div className="text-sm">
          &copy; {new Date().getFullYear()} Presence. {t('landing.footer.rights')}
        </div>
        <div className="flex gap-6 text-sm">
          <a href="#" className="hover:text-white transition-colors">{t('landing.footer.terms')}</a>
          <a href="#" className="hover:text-white transition-colors">{t('landing.footer.privacy')}</a>
          <a href="#" className="hover:text-white transition-colors">{t('landing.footer.legal')}</a>
        </div>
      </div>
    </footer>
  );
}

export default function Landing() {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language.split('-')[0] as "en" | "fr" | "de";
  
  const faqItems = [1, 2, 3].map(i => ({
    q: t(`landing.faq.q${i}`),
    a: t(`landing.faq.a${i}`)
  }));

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-indigo-100 selection:text-indigo-900">
      <SEO 
        title={t('landing.hero.title')}
        description={t('landing.hero.subtitle')}
        lang={currentLang}
        structuredData={[organizationSchema, softwareAppSchema, faqSchema(faqItems)]}
      />
      <Header />
      <Hero />
      <HowItWorks />
      <Features />
      <Pricing />
      <FAQ />
      <CTA />
      <Footer />
    </div>
  );
}
