import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';

const SHELL_TEXTS = {
  fr: {
    home: "Accueil",
    dashboard: "Vue d'ensemble",
    websites: "Sites Web",
    monitoring: "Surveillance",
    seo: "SEO",
    security: "Sécurité",
    social: "Réseaux Sociaux",
    reports: "Rapports",
    alerts: "Alertes",
    admin: "👑 Admin Pilotage",
    settings: "Paramètres",
    logout: "Déconnexion",
    freePlan: "Plan Gratuit",
    unlimited: "{plan} - {used}/{max} sites",
    blog: "Blog",
  },
  en: {
    home: "Home",
    dashboard: "Dashboard",
    websites: "Websites",
    monitoring: "Monitoring",
    seo: "SEO",
    security: "Security",
    social: "Social Media",
    reports: "Reports",
    alerts: "Alertes",
    admin: "👑 Admin Dashboard",
    settings: "Settings",
    logout: "Sign out",
    freePlan: "Free Plan",
    unlimited: "{plan} - {used}/{max} sites",
    blog: "Blog",
  },
  de: {
    home: "Startseite",
    dashboard: "Übersicht",
    websites: "Websites",
    monitoring: "Überwachung",
    seo: "SEO",
    security: "Sicherheit",
    social: "Social Media",
    reports: "Berichte",
    alerts: "Warnungen",
    admin: "👑 Admin-Cockpit",
    settings: "Einstellungen",
    logout: "Abmelden",
    freePlan: "Kostenlos",
    unlimited: "{plan} - {used}/{max} Websites",
    blog: "Blog",
  },
};

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { lang } = useParams<{ lang?: string }>();
  const { i18n } = useTranslation();
  const { plan } = useAuth();
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const currentLang = ((lang || i18n.language || 'de').split('-')[0].toLowerCase()) as 'fr' | 'en' | 'de';
  const t = SHELL_TEXTS[currentLang] || SHELL_TEXTS.fr;
  const langUpper = currentLang.toUpperCase();

  const maxSites = plan?.max_websites ?? 1;
  const usedSites = plan?.active_websites ?? 0;
  const planName = plan?.name || t.freePlan;
  const quotaLabel = t.unlimited
    .replace('{plan}', planName)
    .replace('{used}', usedSites.toString())
    .replace('{max}', maxSites.toString());

  const handleLanguageChange = (targetLang: string) => {
    i18n.changeLanguage(targetLang.toLowerCase());
    setLangMenuOpen(false);
    const currentPathWithoutLang = location.pathname.replace(/^\/(fr|en|de)/, '');
    navigate(`/${targetLang}${currentPathWithoutLang}`);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate(`/${currentLang}/login`);
  };

  const navItems = [
    { path: `/${currentLang}/app/dashboard`, icon: '📊', label: t.dashboard },
    { path: `/${currentLang}/app/websites`, icon: '🌐', label: t.websites },
    { path: `/${currentLang}/app/monitoring`, icon: '⚡', label: t.monitoring },
    { path: `/${currentLang}/app/seo`, icon: '🔍', label: t.seo },
    { path: `/${currentLang}/app/security`, icon: '🔒', label: t.security },
    { path: `/${currentLang}/app/social`, icon: '🌐', label: t.social },
    { path: `/${currentLang}/app/reports`, icon: '📄', label: t.reports },
    { path: `/${currentLang}/app/alerts`, icon: '🔔', label: t.alerts },
    { path: `/${currentLang}/blog`, icon: '✍️', label: t.blog },
    { path: `/${currentLang}/app/admin`, icon: '👑', label: t.admin },
  ];

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden w-full">
      {/* SIDEBAR */}
      <aside className={`fixed inset-y-0 left-0 z-30 flex flex-col bg-white border-r border-slate-200 transition-all duration-300 lg:static lg:z-auto w-64 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="flex items-center p-4 h-16 border-b border-slate-100 justify-between">
          <Link to={`/${currentLang}/app/dashboard`} className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center font-black text-white text-sm">
              P
            </div>
            <span className="font-bold text-slate-900 text-base tracking-tight">Presence</span>
          </Link>
          <button onClick={() => setMobileMenuOpen(false)} className="lg:hidden text-slate-400 hover:text-slate-600">
            ✕
          </button>
        </div>

        <nav className="flex-1 py-4 px-3 overflow-y-auto space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <span className="text-base">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-slate-100 space-y-2">
          <Link
            to={`/${currentLang}/app/settings`}
            className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50 transition"
          >
            <span>⚙️</span>
            <span>{t.settings}</span>
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition cursor-pointer"
          >
            <span>🚪</span>
            <span>{t.logout}</span>
          </button>

          <div className="pt-2">
            <div className="px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase text-emerald-700">{planName}</span>
              <span className="text-[10px] font-semibold text-emerald-600">{quotaLabel}</span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden h-full">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 lg:px-8 shrink-0">
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="lg:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100"
          >
            ☰
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-2 sm:gap-3">
            <Link 
              to={`/${currentLang}/`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-slate-600 hover:bg-slate-100 transition text-xs font-bold"
            >
              <span>🏠</span>
              <span className="hidden sm:inline">{t.home}</span>
            </Link>

            {/* SELECTEUR DE LANGUE DYNAMIQUE */}
            <div className="relative">
              <button
                onClick={() => setLangMenuOpen(!langMenuOpen)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 hover:bg-slate-100 text-xs font-bold text-slate-700 transition cursor-pointer"
              >
                <span>🌐 {langUpper}</span>
                <span className="text-[10px]">▼</span>
              </button>

              {langMenuOpen && (
                <div className="absolute right-0 mt-1 w-28 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50">
                  <button
                    onClick={() => handleLanguageChange('fr')}
                    className={`w-full text-left px-3 py-1.5 text-xs font-semibold hover:bg-indigo-50 ${langUpper === 'FR' ? 'text-indigo-600 font-bold' : 'text-slate-700'}`}
                  >
                    🇫🇷 Français
                  </button>
                  <button
                    onClick={() => handleLanguageChange('en')}
                    className={`w-full text-left px-3 py-1.5 text-xs font-semibold hover:bg-indigo-50 ${langUpper === 'EN' ? 'text-indigo-600 font-bold' : 'text-slate-700'}`}
                  >
                    🇬🇧 English
                  </button>
                  <button
                    onClick={() => handleLanguageChange('de')}
                    className={`w-full text-left px-3 py-1.5 text-xs font-semibold hover:bg-indigo-50 ${langUpper === 'DE' ? 'text-indigo-600 font-bold' : 'text-slate-700'}`}
                  >
                    🇩🇪 Deutsch
                  </button>
                </div>
              )}
            </div>

            {/* USER PROFILE DROPDOWN */}
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs hover:bg-indigo-200 transition cursor-pointer"
              >
                U
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-200 rounded-xl shadow-xl py-2 z-50">
                  <div className="px-4 py-2 border-b border-slate-100">
                    <p className="text-xs font-bold text-slate-800">Utilisateur</p>
                  </div>
                  <div className="p-2">
                    <div className="px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg flex flex-col mb-2">
                      <span className="text-[10px] font-bold uppercase text-emerald-700">{planName}</span>
                      <span className="text-[10px] font-semibold text-emerald-600">{quotaLabel}</span>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="w-full text-left flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition"
                    >
                      <span>🚪</span> {t.logout}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppShell;
