import React, { useEffect, useState } from 'react';
import { Download, Smartphone, Share, PlusSquare, X, Sparkles } from "lucide-react";
import api from "../services/api";

import { useTranslation } from 'react-i18next';

const COOLDOWN_MS = 3 * 60 * 1000; // Rappel après 3 minutes

const TRANSLATIONS: Record<string, any> = {
  fr: {
    title: "Installer Presence",
    desc: "🔔 **{{domain}}** a un score de **{{score}}/100**. Installez Presence pour être alerté instantanément en cas de panne.",
    ios1: "Sur iPhone :",
    ios2: "Appuyez sur",
    ios2Share: "Partager",
    ios3: "Choisissez",
    ios3Add: "« Sur l'écran d'accueil »",
    install: "Installer",
    understood: "J'ai compris",
    later: "Plus tard",
  },
  en: {
    title: "Install Presence",
    desc: "🔔 **{{domain}}** has a score of **{{score}}/100**. Install Presence to be alerted instantly in case of downtime.",
    ios1: "On iPhone:",
    ios2: "Tap",
    ios2Share: "Share",
    ios3: "Choose",
    ios3Add: "« Add to Home Screen »",
    install: "Install",
    understood: "Understood",
    later: "Later",
  },
  de: {
    title: "Presence installieren",
    desc: "🔔 **{{domain}}** hat eine Punktzahl von **{{score}}/100**. Installieren Sie Presence, um bei Ausfällen sofort benachrichtigt zu werden.",
    ios1: "Auf dem iPhone:",
    ios2: "Tippen Sie auf",
    ios2Share: "Teilen",
    ios3: "Wählen Sie",
    ios3Add: "« Zum Home-Bildschirm »",
    install: "Installieren",
    understood: "Verstanden",
    later: "Später",
  },
};

interface PWAPromptModalProps {
  domain: string;
  score: number;
}

export const PWAPromptModal: React.FC<PWAPromptModalProps> = ({ domain, score }) => {
  const { i18n } = useTranslation();
  const [show, setShow] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

  const lang = (i18n.language?.split('-')[0] || 'fr') as 'fr' | 'en' | 'de';
  const t = TRANSLATIONS[lang] || TRANSLATIONS.fr;

  useEffect(() => {
    const checkInstallationState = () => {
      const standalone = window.matchMedia("(display-mode: standalone)").matches
        || (window.navigator as any).standalone === true
        || localStorage.getItem("presence_pwa_installed") === "true";
      setIsStandalone(standalone);
    };

    checkInstallationState();

    const userAgent = window.navigator.userAgent.toLowerCase();
    setIsIOS(/iphone|ipad|ipod/.test(userAgent));

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener("beforeinstallprompt", handler);
    
    window.addEventListener("appinstalled", () => {
      localStorage.setItem("presence_pwa_installed", "true");
      setIsStandalone(true);
      setShow(false);
    });

    const checkInterval = setInterval(() => {
      const cookieConsent = localStorage.getItem("presence_cookie_consent");
      const dismissedAt = localStorage.getItem("presence_pwa_dismissed");
      const installed = localStorage.getItem("presence_pwa_installed") === "true";

      const isDismissedRecently = dismissedAt && (Date.now() - Number(dismissedAt)) < COOLDOWN_MS;

      if (installed) {
        setShow(false);
        clearInterval(checkInterval);
        return;
      }

      // Si le cookie est validé et qu'on n'est pas en cooldown
      if (cookieConsent && !isDismissedRecently) {
        clearInterval(checkInterval);
        setTimeout(() => {
          setShow(true);
        }, 1500); // Petit délai pour ne pas brusquer
      }
    }, 1000);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      clearInterval(checkInterval);
    };
  }, []);

  const handleInstall = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        localStorage.setItem("presence_pwa_installed", "true");
        setShow(false);
        api.post("/analytics/events/track/", { event_type: "pwa_install" }).catch(() => {});
      }
      setDeferredPrompt(null);
    }
  };

  const handleDismiss = () => {
    localStorage.setItem("presence_pwa_installed", "true");
    setShow(false);
    api.post("/analytics/events/track/", { event_type: "pwa_dismiss" }).catch(() => {});
  };

  const handleLater = () => {
    localStorage.setItem("presence_pwa_dismissed", Date.now().toString());
    setShow(false);
    api.post("/analytics/events/track/", { event_type: "pwa_dismiss" }).catch(() => {});
  };

  if (!show || isStandalone) return null;

  return (
    <div className="fixed bottom-0 sm:bottom-4 left-0 sm:left-auto right-0 sm:right-4 z-30 sm:max-w-[340px] w-full p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-indigo-100 p-4 animate-in slide-in-from-bottom sm:slide-in-from-right duration-300">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center text-lg shrink-0">
              📲
            </div>
            <div>
              <p className="text-xs font-bold text-slate-900 leading-tight">{t.title}</p>
            </div>
          </div>
          <button onClick={handleDismiss} className="text-slate-400 hover:text-slate-600">
            <X size={16} />
          </button>
        </div>

        <p className="text-[11px] text-slate-600 leading-relaxed mb-3" dangerouslySetInnerHTML={{ __html: t.desc.replace('{{domain}}', domain).replace('{{score}}', score.toString()).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}>
        </p>

        {isIOS && (
          <div className="p-2 mb-3 bg-slate-50 border border-slate-200 rounded-lg text-[10px] text-slate-600">
            <p className="font-bold text-slate-800 mb-1 flex items-center gap-1">
              <Sparkles size={12} className="text-indigo-600" /> {t.ios1}
            </p>
            <p>1. {t.ios2} <strong>{t.ios2Share}</strong> <Share size={10} className="inline text-blue-600" /></p>
            <p>2. {t.ios3} <strong>{t.ios3Add}</strong> <PlusSquare size={10} className="inline" /></p>
          </div>
        )}

        <div className="flex items-center gap-2">
          {!isIOS && deferredPrompt ? (
            <button onClick={handleInstall}
              className="flex-1 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-xs shadow-sm transition-all flex items-center justify-center gap-1.5">
              <Download size={14} /> {t.install}
            </button>
          ) : !isIOS ? (
            <button onClick={handleDismiss}
              className="flex-1 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-xs shadow-sm transition-all flex items-center justify-center">
              {t.understood}
            </button>
          ) : null}
          <button onClick={handleLater}
            className="flex-1 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-semibold text-xs transition-colors">
            {t.later}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PWAPromptModal;
