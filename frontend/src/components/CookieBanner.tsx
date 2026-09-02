import React, { useEffect, useState } from "react";
import { Cookie, X, ChevronDown, ChevronUp } from "lucide-react";
import { useModalQueue } from "../context/ModalQueueContext";
import { useCookieConsent } from "../hooks/useCookieConsent";
import api from "../services/api";

const TRANSLATIONS: Record<string, any> = {
  fr: {
    desc: "Nous utilisons des cookies pour sécuriser votre session, analyser le trafic anonymement et vous envoyer des alertes.",
    customize: "Personnaliser",
    essential: "Essentiels uniquement",
    acceptAll: "Tout accepter",
    essentialLabel: "Session & Sécurité (obligatoire)",
    analyticsLabel: "Analytics (trafic anonyme)",
    marketingLabel: "Marketing (sponsors)",
  },
  en: {
    desc: "We use cookies to secure your session, analyze traffic anonymously, and send you alerts.",
    customize: "Customize",
    essential: "Essential only",
    acceptAll: "Accept all",
    essentialLabel: "Session & Security (required)",
    analyticsLabel: "Analytics (anonymous traffic)",
    marketingLabel: "Marketing (sponsors)",
  },
  de: {
    desc: "Wir verwenden Cookies, um Ihre Sitzung zu sichern, den Traffic anonym zu messen und Ihnen Benachrichtigungen zu senden.",
    customize: "Anpassen",
    essential: "Nur essentielle",
    acceptAll: "Alle akzeptieren",
    essentialLabel: "Sitzung & Sicherheit (erforderlich)",
    analyticsLabel: "Analysen (anonymer Traffic)",
    marketingLabel: "Marketing (Sponsoren)",
  }
};

function detectLang(): string {
  const nav = navigator.language?.slice(0, 2).toLowerCase() || "en";
  return ["fr", "en", "de"].includes(nav) ? nav : "en";
}

export const CookieBanner: React.FC = () => {
  const { activeModal, registerModal, dismissModal } = useModalQueue();
  const { consent, isResolved, setConsent } = useCookieConsent();
  const [expanded, setExpanded] = useState(false);
  const [visible, setVisible] = useState(false);
  const [lang, setLang] = useState("en");
  const [shouldBounce, setShouldBounce] = useState(false);

  useEffect(() => {
    setLang(detectLang());

    if (!isResolved) {
      registerModal("cookie", 1);
      const showTimer = setTimeout(() => setVisible(true), 500);

      // Animation de rebond léger après 10s d'inactivité
      const bounceTimer = setTimeout(() => {
        setShouldBounce(true);
        // Retirer la classe de bounce après 3 secondes (3 rebonds)
        setTimeout(() => setShouldBounce(false), 3000);
      }, 10000);

      return () => {
        clearTimeout(showTimer);
        clearTimeout(bounceTimer);
      };
    }
  }, [isResolved, registerModal]);

  const handleChoice = (type: "essential" | "all") => {
    setConsent(type);
    setVisible(false);
    dismissModal("cookie");
    api.post("/analytics/events/track/", { event_type: `cookie_${type}` }).catch(() => {});
  };

  if (isResolved || !visible || activeModal !== "cookie") return null;

  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  // Injection du style CSS pour le bounce sans modifier les fichiers Tailwind
  const bounceStyle = `
    @keyframes cookie-bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-12px); }
    }
    .animate-cookie-bounce {
      animation: cookie-bounce 1s ease-in-out infinite;
    }
  `;

  return (
    <>
      <style>{bounceStyle}</style>
      
      {/* Wrapper global : pointer-events-none garantit que le site en arrière-plan reste cliquable */}
      <div className="fixed inset-x-0 bottom-0 z-50 pointer-events-none flex flex-col items-center justify-end">
        
        {/* Le composant lui-même réactive les clics (pointer-events-auto) */}
        <div 
          className={`pointer-events-auto w-full bg-white shadow-[0_-15px_30px_rgba(0,0,0,0.1)] transition-all duration-500 border-t-[3px] border-indigo-600
            /* Styles Desktop : hauteur fixe 110px, texte 16px */
            lg:h-[110px] lg:flex lg:items-center lg:py-0
            /* Styles Mobile : bottom sheet couvrant 35% de la hauteur de l'écran, coins supérieurs arrondis */
            max-lg:h-[35vh] max-lg:rounded-t-2xl max-lg:p-5 max-lg:overflow-y-auto
            ${shouldBounce ? "animate-cookie-bounce" : "animate-in slide-in-from-bottom duration-500"}
          `}
        >
          <div className="max-w-7xl mx-auto w-full px-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            
            {/* Description principale */}
            <div className="flex items-start lg:items-center gap-3.5 flex-1 text-left">
              <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl flex-shrink-0">
                <Cookie size={22} />
              </div>
              <p className="text-base font-medium text-slate-700 leading-snug">
                {t.desc}
              </p>
            </div>

            {/* Actions & Boutons */}
            <div className="flex flex-wrap items-center gap-3 flex-shrink-0 self-end lg:self-auto w-full lg:w-auto">
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800 flex items-center gap-1 py-2 px-3 border border-transparent hover:border-slate-200 rounded-xl transition-all"
              >
                {t.customize} {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              
              <button
                onClick={() => handleChoice("essential")}
                className="flex-1 lg:flex-none px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 hover:bg-slate-50 rounded-xl transition-colors whitespace-nowrap"
              >
                {t.essential}
              </button>
              
              {/* Bouton "Tout accepter" : bleu, légèrement plus grand */}
              <button
                onClick={() => handleChoice("all")}
                className="flex-1 lg:flex-none px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-indigo-200 whitespace-nowrap"
              >
                {t.acceptAll}
              </button>
            </div>
          </div>
        </div>

        {/* Détails de personnalisation (s'affiche au-dessus du bandeau en cas d'expansion) */}
        {expanded && (
          <div className="pointer-events-auto w-full bg-slate-50 border-t border-slate-100 p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-700 max-w-7xl mx-auto rounded-t-xl mb-[110px] hidden lg:grid">
            <label className="flex items-center gap-2.5 p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
              <input type="checkbox" checked disabled className="accent-indigo-600 h-4 w-4" />
              <span><strong>{t.essentialLabel}</strong></span>
            </label>
            <label className="flex items-center gap-2.5 p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
              <input type="checkbox" defaultChecked className="accent-indigo-600 h-4 w-4" />
              <span><strong>{t.analyticsLabel}</strong></span>
            </label>
            <label className="flex items-center gap-2.5 p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
              <input type="checkbox" defaultChecked className="accent-indigo-600 h-4 w-4" />
              <span><strong>{t.marketingLabel}</strong></span>
            </label>
          </div>
        )}
      </div>
    </>
  );
};

export default CookieBanner;
