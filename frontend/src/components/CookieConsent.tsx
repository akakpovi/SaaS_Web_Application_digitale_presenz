import React, { useEffect, useState } from 'react';
import { Cookie, Check } from "lucide-react";
import api from "../services/api";

import { useTranslation } from 'react-i18next';

const COOLDOWN_MS = 3 * 60 * 1000; // Rappel après 3 minutes

const TRANSLATIONS: Record<string, any> = {
  fr: {
    title: "Gestion des Cookies",
    desc: "Nous utilisons des cookies pour améliorer votre expérience, sécuriser votre compte et mesurer l'audience de manière anonyme (RGPD).",
    acceptAll: "Tout accepter",
    essential: "Essentiels uniquement",
    customize: "Personnaliser",
  },
  en: {
    title: "Cookie Management",
    desc: "We use cookies to improve your experience, secure your account, and measure traffic anonymously (GDPR compliant).",
    acceptAll: "Accept all",
    essential: "Essential only",
    customize: "Customize",
  },
  de: {
    title: "Cookie-Verwaltung",
    desc: "Wir verwenden Cookies, um Ihre Erfahrung zu verbessern, Ihr Konto zu sichern und den Traffic anonym zu messen (DSGVO-konform).",
    acceptAll: "Alle akzeptieren",
    essential: "Nur notwendige",
    customize: "Anpassen",
  },
};

export const CookieConsent: React.FC = () => {
  const { i18n } = useTranslation();
  const [visible, setVisible] = useState(false);
  const [isDismissed, setIsDismissed] = useState(true);

  // Sync language with app state
  const lang = (i18n.language?.split('-')[0] || 'fr') as 'fr' | 'en' | 'de';
  const t = TRANSLATIONS[lang] || TRANSLATIONS.fr;

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const checkConsent = () => {
      const consent = localStorage.getItem("presence_cookie_consent");
      const dismissedAt = localStorage.getItem("presence_cookie_dismissed_at");
      const isDismissedRecently = dismissedAt && (Date.now() - Number(dismissedAt)) < COOLDOWN_MS;

      if (consent === "all" || consent === "essential") {
        setVisible(false);
        setIsDismissed(true);
      } else if (!isDismissedRecently) {
        // Add a 3-second delay before showing the banner to avoid immediate popup
        timeoutId = setTimeout(() => {
          setVisible(true);
          setIsDismissed(false);
        }, 3000);
      } else {
        setIsDismissed(true);
      }
    };

    checkConsent();
    const interval = setInterval(() => {
      // Don't use checkConsent here to avoid the 3s timeout repeating, 
      // instead check directly
      const consent = localStorage.getItem("presence_cookie_consent");
      if (consent !== "all" && consent !== "essential" && isDismissed) {
         // Logic to potentially reshow could go here if needed
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [isDismissed]);

  const handleAcceptAll = () => {
    localStorage.setItem("presence_cookie_consent", "all");
    localStorage.removeItem("presence_cookie_dismissed_at");
    setVisible(false);
    setIsDismissed(true);
    api.post("/analytics/events/track/", { event_type: "cookie_accept" }).catch(() => {});
  };

  const handleEssentialOnly = () => {
    localStorage.setItem("presence_cookie_consent", "essential");
    localStorage.setItem("presence_cookie_dismissed_at", Date.now().toString());
    setVisible(false);
    setIsDismissed(true);
    api.post("/analytics/events/track/", { event_type: "cookie_essential" }).catch(() => {});
  };

  const openBanner = () => {
    setVisible(true);
    setIsDismissed(false);
  };

  return (
    <>
      {/* 🛑 Sticky Bottom Banner (No Overlay) */}
      {visible && (
        <div className="fixed bottom-0 left-0 right-0 z-50 p-4 sm:p-6 bg-slate-900 border-t border-slate-800 shadow-[0_-10px_30px_rgba(0,0,0,0.3)] animate-in slide-in-from-bottom duration-300">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-4 md:gap-8 justify-between">
            <div className="flex-1 flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className="hidden sm:flex p-3 bg-indigo-600/20 text-indigo-400 rounded-full flex-shrink-0">
                <Cookie size={24} />
              </div>
              <div>
                <h3 className="font-bold text-white text-sm sm:text-base mb-1">{t.title} 🍪</h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed max-w-3xl">
                  {t.desc}
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto shrink-0">
              <button
                onClick={openBanner}
                className="w-full sm:w-auto py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-colors border border-slate-700"
              >
                {t.customize}
              </button>
              <button
                onClick={handleEssentialOnly}
                className="w-full sm:w-auto py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-colors border border-slate-700"
              >
                {t.essential}
              </button>
              <button
                onClick={handleAcceptAll}
                className="w-full sm:w-auto py-2.5 px-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-1.5"
              >
                <Check size={16} /> {t.acceptAll}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default CookieConsent;
