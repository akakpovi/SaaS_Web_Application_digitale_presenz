import React, { useState, useEffect } from "react";
import { Cookie, ShieldCheck, TrendingUp, Bell, Lock, X, Check } from "lucide-react";
import api from "../services/api";

const COOLDOWN_MS = 3 * 60 * 1000; // ⏱️ Rappel après 3 minutes

const TRANSLATIONS: Record<string, any> = {
  fr: {
    title: "Gestion des Cookies",
    desc: "Nous utilisons des cookies pour améliorer votre expérience, sécuriser votre compte et mesurer l'audience de manière anonyme (RGPD).",
    acceptAll: "Accepter tout & Activer les avantages",
    essential: "Essentiels uniquement",
    benefitsTitle: "Pourquoi accepter les cookies ?",
    benefits: [
      { icon: "lock", text: "Session sécurisée : restez connecté automatiquement sur mobile et PC" },
      { icon: "bell", text: "Alertes push instantanées en cas de panne de votre site" },
      { icon: "trending", text: "Recommandations de sponsors & codes promos hébergement" },
    ],
  },
  en: {
    title: "Cookie Management",
    desc: "We use cookies to improve your experience, secure your account, and measure traffic anonymously (GDPR compliant).",
    acceptAll: "Accept all & Enable benefits",
    essential: "Essential only",
    benefitsTitle: "Why accept cookies?",
    benefits: [
      { icon: "lock", text: "Secure session: stay logged in automatically on mobile and PC" },
      { icon: "bell", text: "Instant push alerts when your website goes down" },
      { icon: "trending", text: "Sponsor recommendations & hosting discount codes" },
    ],
  },
  de: {
    title: "Cookie-Verwaltung",
    desc: "Wir verwenden Cookies, um Ihre Erfahrung zu verbessern, Ihr Konto zu sichern und den Traffic anonym zu messen (DSGVO-konform).",
    acceptAll: "Alle akzeptieren & Vorteile aktivieren",
    essential: "Nur notwendige",
    benefitsTitle: "Warum Cookies akzeptieren?",
    benefits: [
      { icon: "lock", text: "Sichere Sitzung: auf Handy und PC automatisch angemeldet bleiben" },
      { icon: "bell", text: "Sofortige Push-Benachrichtigungen bei Ausfall Ihrer Website" },
      { icon: "trending", text: "Sponsoren-Empfehlungen & Hosting-Rabattcodes" },
    ],
  },
};

function detectLang(): string {
  const nav = navigator.language?.slice(0, 2).toLowerCase() || "en";
  if (["fr", "en", "de"].includes(nav)) return nav;
  return "en";
}

export const CookieConsent: React.FC = () => {
  const [visible, setVisible] = useState(false);
  const [lang, setLang] = useState("en");

  useEffect(() => {
    setLang(detectLang());

    const checkConsent = () => {
      const consent = localStorage.getItem("presence_cookie_consent");
      const dismissedAt = localStorage.getItem("presence_cookie_dismissed_at");
      const isDismissedRecently = dismissedAt && (Date.now() - Number(dismissedAt)) < COOLDOWN_MS;

      if (consent === "all") {
        setVisible(false);
      } else if (!isDismissedRecently) {
        setVisible(true);
      }
    };

    checkConsent();
    const interval = setInterval(checkConsent, 30000); // Vérifie toutes les 30s si le délai de 3 min est écoulé
    return () => clearInterval(interval);
  }, []);

  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  const handleAcceptAll = () => {
    localStorage.setItem("presence_cookie_consent", "all");
    localStorage.removeItem("presence_cookie_dismissed_at");
    setVisible(false);
    api.post("/analytics/events/track/", { event_type: "cookie_accept" }).catch(() => {});
  };

  const handleEssentialOnly = () => {
    localStorage.setItem("presence_cookie_dismissed_at", Date.now().toString());
    setVisible(false);
    api.post("/analytics/events/track/", { event_type: "cookie_essential" }).catch(() => {});
  };

  const iconMap: Record<string, React.ReactNode> = {
    lock: <Lock size={14} className="text-emerald-400" />,
    bell: <Bell size={14} className="text-indigo-400" />,
    trending: <TrendingUp size={14} className="text-amber-400" />,
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="bg-slate-900/95 text-white p-6 sm:p-8 rounded-3xl shadow-2xl border border-slate-700/50 max-w-md w-full animate-in zoom-in-95 duration-300 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-2xl flex-shrink-0">
              <Cookie size={22} />
            </div>
            <h3 className="font-extrabold text-lg text-white">{t.title} 🍪</h3>
          </div>
          <button onClick={handleEssentialOnly} className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors">
            <X size={18} />
          </button>
        </div>

        <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{t.desc}</p>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 space-y-3">
          <h4 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">{t.benefitsTitle}</h4>
          {t.benefits.map((b: any, i: number) => (
            <div key={i} className="flex items-start gap-2.5 text-xs text-slate-200">
              <div className="mt-0.5 flex-shrink-0">{iconMap[b.icon]}</div>
              <span className="leading-tight">{b.text}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row gap-2 pt-2">
          <button
            onClick={handleAcceptAll}
            className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs sm:text-sm font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-1.5"
          >
            <Check size={16} /> {t.acceptAll}
          </button>
          <button
            onClick={handleEssentialOnly}
            className="py-3 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs sm:text-sm font-semibold transition-colors border border-slate-700"
          >
            {t.essential}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
