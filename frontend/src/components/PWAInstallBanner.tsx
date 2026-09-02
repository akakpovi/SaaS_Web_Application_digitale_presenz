import React, { useState, useEffect } from "react";
import { Download, BellRing, Smartphone, CheckCircle2, Loader } from "lucide-react";
import api from "../services/api";

const VAPID_PUBLIC_KEY = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U";

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export const PWAInstallBanner: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [loadingPush, setLoadingPush] = useState(false);
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

  const subscribeToPush = async (): Promise<boolean> => {
    if (!("serviceWorker" in navigator) || !("Notification" in window)) return false;
    
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return false;

      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();

      if (!sub) {
        const convertedVapidKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: convertedVapidKey,
        });
      }

      if (sub) {
        const subData = sub.toJSON();
        await api.post("/notifications/push/subscribe/", {
          endpoint: sub.endpoint,
          keys: subData.keys || {},
        });
        setPushSubscribed(true);
        return true;
      }
    } catch (err) {
      console.warn("Push subscription:", err);
    }
    return false;
  };

  useEffect(() => {
    const checkState = () => {
      const standalone = window.matchMedia("(display-mode: standalone)").matches
        || (window.navigator as any).standalone === true
        || localStorage.getItem("presence_pwa_installed") === "true";
      setIsStandalone(standalone);
    };

    checkState();

    if ("Notification" in window && Notification.permission === "granted") {
      subscribeToPush().catch(() => {});
    }

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstall);
    window.addEventListener("appinstalled", () => {
      localStorage.setItem("presence_pwa_installed", "true");
      setIsStandalone(true);
    });

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstall);
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) {
      alert("Sur PC : Cliquez sur l'icône ⊕ dans la barre d'adresse du navigateur.\nSur Mobile : Appuyez sur le menu du navigateur puis 'Ajouter à l'écran d'accueil'.");
      return;
    }
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      localStorage.setItem("presence_pwa_installed", "true");
      setIsStandalone(true);
      setDeferredPrompt(null);
    }
  };

  const handleActivateClick = async () => {
    if (!("Notification" in window)) {
      alert("Votre navigateur ne supporte pas les notifications.");
      return;
    }

    setLoadingPush(true);
    try {
      const ok = await subscribeToPush();
      if (ok) {
        new Notification("🎉 Notifications Activées !", {
          body: "Vous recevrez des alertes automatiques en cas d'incident sur vos sites.",
          icon: "/icons/icon-192.png",
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingPush(false);
    }
  };

  if (isStandalone && pushSubscribed) {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 text-white rounded-2xl p-5 shadow-lg mb-6 border border-indigo-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-start sm:items-center gap-3.5">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center flex-shrink-0">
          <Smartphone size={20} className="text-indigo-300" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-indigo-500 text-white text-[10px] font-bold uppercase tracking-wider">
              {isStandalone ? "Application PWA Active" : "Application Mobile & Bureau"}
            </span>
            {pushSubscribed && (
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold flex items-center gap-1">
                <CheckCircle2 size={12} /> Alertes Push Connectées
              </span>
            )}
          </div>
          <p className="text-xs text-indigo-100 mt-1 font-medium">
            {isStandalone 
              ? "Application installée sur votre appareil. Activez les notifications pour surveiller vos sites en temps réel." 
              : "Installez Presence sur votre écran d'accueil pour être alerté instantanément dès qu'un site tombe en panne."}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap self-start md:self-auto">
        {!isStandalone && (
          <button
            onClick={handleInstallClick}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl text-xs shadow-sm transition-all flex items-center gap-1.5 border border-indigo-400/40"
          >
            <Download size={14} /> Installer l'application
          </button>
        )}

        {!pushSubscribed && (
          <button
            onClick={handleActivateClick}
            disabled={loadingPush}
            className="px-3.5 py-2 bg-white text-indigo-900 hover:bg-indigo-50 font-bold rounded-xl text-xs shadow-sm transition-all flex items-center gap-1.5"
          >
            {loadingPush ? <Loader size={14} className="animate-spin" /> : <BellRing size={14} className="text-indigo-600 animate-bounce" />}
            {loadingPush ? "Activation..." : "Activer les Alertes"}
          </button>
        )}
      </div>
    </div>
  );
};

export default PWAInstallBanner;
