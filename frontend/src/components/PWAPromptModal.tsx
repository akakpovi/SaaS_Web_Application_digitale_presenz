import React, { useState, useEffect } from "react";
import { Download, Smartphone, Share, PlusSquare, X, Sparkles, Zap, Bell, Shield } from "lucide-react";
import api from "../services/api";

const COOLDOWN_MS = 3 * 60 * 1000; // Rappel après 3 minutes

export const PWAPromptModal: React.FC = () => {
  const [show, setShow] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

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
      const cookieDismissed = localStorage.getItem("presence_cookie_dismissed_at");
      const dismissedAt = localStorage.getItem("presence_pwa_dismissed");
      const installed = localStorage.getItem("presence_pwa_installed") === "true";

      const isDismissedRecently = dismissedAt && (Date.now() - Number(dismissedAt)) < COOLDOWN_MS;

      if (installed) {
        setShow(false);
        clearInterval(checkInterval);
        return;
      }

      if ((cookieConsent || cookieDismissed) && !isDismissedRecently) {
        clearInterval(checkInterval);
        setTimeout(() => {
          setShow(true);
        }, 1500);
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
    // Cliquer sur J'ai compris ou Plus tard enregistre que c'est traité
    localStorage.setItem("presence_pwa_installed", "true");
    setShow(false);
    api.post("/analytics/events/track/", { event_type: "pwa_dismiss" }).catch(() => {});
  };

  const handleLater = () => {
    // Plus tard active le cool-down de 3 minutes
    localStorage.setItem("presence_pwa_dismissed", Date.now().toString());
    setShow(false);
    api.post("/analytics/events/track/", { event_type: "pwa_dismiss" }).catch(() => {});
  };

  if (!show || isStandalone) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 sm:p-7 border border-slate-100 relative overflow-hidden transform animate-in zoom-in-95 duration-300">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center shadow-lg shadow-indigo-200">
              <Smartphone size={22} />
            </div>
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                Application Installable
              </span>
              <h3 className="font-extrabold text-slate-900 text-base mt-0.5">Installer Presence</h3>
            </div>
          </div>
          <button onClick={handleDismiss} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
            <X size={18} />
          </button>
        </div>

        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
          Installez Presence sur votre écran d'accueil pour profiter d'une expérience plus rapide, d'un accès instantané et des alertes de surveillance en direct.
        </p>

        <div className="space-y-2.5 mb-5">
          <div className="flex items-center gap-3 p-2.5 bg-emerald-50 border border-emerald-100 rounded-xl">
            <Zap size={16} className="text-emerald-600 flex-shrink-0" />
            <span className="text-xs font-semibold text-slate-700">Accès en 1 clic, plus rapide qu'un site classique</span>
          </div>
          <div className="flex items-center gap-3 p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl">
            <Bell size={16} className="text-indigo-600 flex-shrink-0" />
            <span className="text-xs font-semibold text-slate-700">Notifications push instantanées en cas de panne</span>
          </div>
          <div className="flex items-center gap-3 p-2.5 bg-amber-50 border border-amber-100 rounded-xl">
            <Shield size={16} className="text-amber-600 flex-shrink-0" />
            <span className="text-xs font-semibold text-slate-700">Fonctionne même hors-ligne avec vos données</span>
          </div>
        </div>

        {isIOS && (
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl mb-5 space-y-2 text-xs text-slate-700">
            <p className="font-bold text-slate-900 flex items-center gap-1.5">
              <Sparkles size={14} className="text-indigo-600" /> Sur iPhone / iPad :
            </p>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-[10px]">1</span>
              <span>Appuyez sur <strong>Partager</strong> <Share size={13} className="inline text-blue-600" /> en bas de Safari</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-[10px]">2</span>
              <span>Sélectionnez <strong>« Sur l'écran d'accueil »</strong> <PlusSquare size={13} className="inline" /></span>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          {!isIOS && deferredPrompt ? (
            <button onClick={handleInstall}
              className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-200 transition-all">
              <Download size={16} /> Installer maintenant
            </button>
          ) : (
            <button onClick={handleDismiss}
              className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-200 transition-all">
              J'ai compris
            </button>
          )}
          <button onClick={handleLater}
            className="py-3 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-semibold text-sm transition-colors">
            Plus tard
          </button>
        </div>
      </div>
    </div>
  );
};

export default PWAPromptModal;
