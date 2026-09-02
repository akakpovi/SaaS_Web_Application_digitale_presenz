import React, { useState } from "react";
import { BellRing, ShieldAlert, AlertTriangle, Sparkles, Send, Loader, X, RefreshCw } from "lucide-react";
import api from "../services/api";

interface PushTesterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onForceSubscribe?: () => Promise<boolean>;
}

export const PushTesterModal: React.FC<PushTesterModalProps> = ({ isOpen, onClose, onForceSubscribe }) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [noSub, setNoSub] = useState(false);

  if (!isOpen) return null;

  const triggerTest = async (scenario: "down" | "ssl" | "seo") => {
    setLoading(true);
    setResult(null);
    setNoSub(false);
    try {
      const res = await api.post("/notifications/push/test/", { scenario });
      const sent = res.data.result?.sent || 0;
      if (sent > 0) {
        setResult(`🎉 Notification envoyée et reçue avec succès sur ${sent} appareil(s) !`);
      } else {
        setNoSub(true);
        setResult("⚠️ Aucun appareil enregistré sur votre compte Django. Cliquez sur le bouton ci-dessous pour l'enregistrer maintenant.");
      }
    } catch (err: any) {
      setResult(`❌ Erreur serveur : ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReconnect = async () => {
    setLoading(true);
    setResult(null);
    try {
      if (onForceSubscribe) {
        await onForceSubscribe();
        setNoSub(false);
        setResult("✅ Cet appareil a été enregistré en base de données avec succès ! Cliquez sur une alerte ci-dessous pour tester.");
      }
    } catch (e: any) {
      setResult(`❌ Échec de la connexion : ${e.message || "Erreur inconnue"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl max-w-lg w-full p-6 sm:p-7 border border-slate-100 space-y-5 animate-in zoom-in-95">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-2xl">
              <BellRing size={22} className="animate-pulse" />
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900 text-lg">Test des Notifications Push Réelles</h3>
              <p className="text-xs text-slate-500">Testez l'envoi en direct sur votre PC ou Smartphone</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3">
          <button
            onClick={() => triggerTest("down")}
            disabled={loading}
            className="p-4 rounded-2xl border border-red-200 bg-red-50/50 hover:bg-red-50 text-left transition-all flex items-start gap-3.5 group"
          >
            <div className="p-2 bg-red-100 text-red-600 rounded-xl flex-shrink-0 group-hover:scale-105 transition-transform">
              <ShieldAlert size={20} />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-red-950">1. Alerte Critique : Site Down 🔴</span>
                <Send size={14} className="text-red-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-xs text-red-700 mt-0.5">Simule une coupure de serveur immédiate sur votre site principal.</p>
            </div>
          </button>

          <button
            onClick={() => triggerTest("ssl")}
            disabled={loading}
            className="p-4 rounded-2xl border border-amber-200 bg-amber-50/50 hover:bg-amber-50 text-left transition-all flex items-start gap-3.5 group"
          >
            <div className="p-2 bg-amber-100 text-amber-600 rounded-xl flex-shrink-0 group-hover:scale-105 transition-transform">
              <AlertTriangle size={20} />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-amber-950">2. Alerte Warning : Expiration SSL 🟠</span>
                <Send size={14} className="text-amber-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-xs text-amber-700 mt-0.5">Alerte préventive quand un certificat expire dans moins de 7 jours.</p>
            </div>
          </button>

          <button
            onClick={() => triggerTest("seo")}
            disabled={loading}
            className="p-4 rounded-2xl border border-emerald-200 bg-emerald-50/50 hover:bg-emerald-50 text-left transition-all flex items-start gap-3.5 group"
          >
            <div className="p-2 bg-emerald-100 text-emerald-600 rounded-xl flex-shrink-0 group-hover:scale-105 transition-transform">
              <Sparkles size={20} />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-emerald-950">3. Notification Succès : Score SEO 🟢</span>
                <Send size={14} className="text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-xs text-emerald-700 mt-0.5">Notification de fin d'audit avec amélioration des performances.</p>
            </div>
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center gap-2 p-3 bg-indigo-50 text-indigo-700 rounded-xl text-xs font-semibold">
            <Loader size={16} className="animate-spin" /> Communication avec le serveur Push en cours...
          </div>
        )}

        {result && (
          <div className={`p-3.5 rounded-xl text-xs font-medium text-center ${noSub ? "bg-amber-50 text-amber-900 border border-amber-200" : "bg-slate-900 text-white"}`}>
            <p>{result}</p>
            {noSub && (
              <button
                onClick={handleReconnect}
                disabled={loading}
                className="mt-2.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg text-xs flex items-center justify-center gap-1.5 mx-auto transition-colors shadow-sm"
              >
                <RefreshCw size={13} /> Enregistrer cet appareil maintenant
              </button>
            )}
          </div>
        )}

        <div className="flex justify-end pt-1">
          <button onClick={onClose} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-xl text-xs">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};

export default PushTesterModal;
