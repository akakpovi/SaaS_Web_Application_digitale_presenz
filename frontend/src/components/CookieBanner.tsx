import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

const COOKIE_TEXTS = {
  fr: {
    message: "Nous utilisons des cookies pour sécuriser votre session, analyser le trafic anonymement et vous envoyer des alertes.",
    customize: "Personnaliser",
    essential: "Essentiels uniquement",
    acceptAll: "Tout accepter",
  },
  en: {
    message: "We use cookies to secure your session, anonymously analyze traffic, and send you monitoring alerts.",
    customize: "Customize",
    essential: "Essential only",
    acceptAll: "Accept all",
  },
  de: {
    message: "Wir verwenden Cookies, um Ihre Sitzung zu sichern, den Datenverkehr anonym zu analysieren und Benachrichtigungen zu senden.",
    customize: "Anpassen",
    essential: "Nur essenzielle",
    acceptAll: "Alle akzeptieren",
  },
};

export function CookieBanner() {
  const { i18n } = useTranslation();
  const [visible, setVisible] = useState(false);

  const currentLang = ((i18n.language || 'fr').split('-')[0].toLowerCase()) as 'fr' | 'en' | 'de';
  const t = COOKIE_TEXTS[currentLang] || COOKIE_TEXTS.fr;

  useEffect(() => {
    const consent = localStorage.getItem('cookie_consent');
    if (!consent) {
      setVisible(true);
    }
  }, []);

  const handleAccept = (type: 'all' | 'essential') => {
    localStorage.setItem('cookie_consent', type);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 pointer-events-none flex flex-col items-center justify-end">
      <div className="pointer-events-auto w-full bg-white shadow-[0_-15px_30px_rgba(0,0,0,0.1)] transition-all duration-500 border-t-[3px] border-indigo-600 lg:h-[110px] lg:flex lg:items-center lg:py-0 max-lg:h-[35vh] max-lg:rounded-t-2xl max-lg:p-5 max-lg:overflow-y-auto animate-in slide-in-from-bottom duration-500">
        <div className="max-w-7xl mx-auto w-full px-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start lg:items-center gap-3.5 flex-1 text-left">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl shrink-0 text-xl">
              🍪
            </div>
            <p className="text-base font-medium text-slate-700 leading-snug">
              {t.message}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 shrink-0 self-end lg:self-auto w-full lg:w-auto">
            <button
              onClick={() => handleAccept('essential')}
              className="flex-1 lg:flex-none px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 hover:bg-slate-50 rounded-xl transition-colors whitespace-nowrap"
            >
              {t.essential}
            </button>
            <button
              onClick={() => handleAccept('all')}
              className="flex-1 lg:flex-none px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-indigo-200 whitespace-nowrap"
            >
              {t.acceptAll}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CookieBanner;
