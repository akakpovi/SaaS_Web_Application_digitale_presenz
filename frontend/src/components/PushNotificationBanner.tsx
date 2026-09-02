import React, { useState, useEffect } from "react";
import { BellRing, Bell, X } from "lucide-react";
import api from "../services/api";

export const PushNotificationBanner: React.FC = () => {
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [loading, setLoading] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if ("Notification" in window) {
      setPermission(Notification.permission);
      if (Notification.permission === "granted") {
        setSubscribed(true);
      }
    }
  }, []);

  const subscribeUser = async () => {
    if (!("serviceWorker" in navigator) || !("Notification" in window)) {
      alert("Votre navigateur ne supporte pas les notifications push.");
      return;
    }

    setLoading(true);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);

      if (perm === "granted") {
        const reg = await navigator.serviceWorker.ready;
        let sub = await reg.pushManager.getSubscription();
        
        if (!sub) {
          const applicationServerKey = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U";
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
          });
        }

        const subData = sub.toJSON();
        await api.post("/notifications/push/subscribe/", {
          endpoint: sub.endpoint,
          keys: subData.keys || {}
        });

        setSubscribed(true);
        new Notification("🎉 Notifications Activées !", {
          body: "Vous serez prévenu instantanément en cas d'incident sur vos sites web.",
          icon: "/favicon.ico"
        });
      }
    } catch (err) {
      console.error("Erreur souscription push:", err);
    } finally {
      setLoading(false);
    }
  };

  if (dismissed || subscribed || permission === "denied") {
    return null;
  }

  return (
    <div className="p-4 bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-2xl shadow-lg flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 transition-all">
      <div className="flex items-center gap-3.5 text-left">
        <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center flex-shrink-0">
          <BellRing size={20} className="text-indigo-100 animate-pulse" />
        </div>
        <div>
          <h4 className="font-bold text-sm">Activer les alertes push instantanées</h4>
          <p className="text-xs text-indigo-100 mt-0.5">
            Soyez alerté directement sur votre écran dès qu'un certificat SSL expire ou qu'un site tombe en panne.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
        <button
          onClick={subscribeUser}
          disabled={loading}
          className="px-4 py-2 bg-white text-indigo-700 hover:bg-indigo-50 font-bold rounded-xl text-xs shadow-sm transition-all flex items-center gap-1.5"
        >
          <Bell size={14} /> {loading ? "Activation..." : "Activer en 1 clic"}
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="p-1.5 hover:bg-white/10 text-indigo-200 rounded-lg transition-colors"
          title="Fermer"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};

export default PushNotificationBanner;
