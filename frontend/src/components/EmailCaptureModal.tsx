import React, { useState } from 'react';
import { Mail, X, Check, Loader, Send } from "lucide-react";
import api from "../services/api";

interface EmailCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  scanId: string;
}

export const EmailCaptureModal: React.FC<EmailCaptureModalProps> = ({ isOpen, onClose, scanId }) => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes("@")) return;
    setLoading(true);
    setError(null);
    try {
      await api.post(`/public/scan/${scanId}/email/`, { email: email.trim() });
      setSuccess(true);
      setTimeout(() => {
        onClose();
        setSuccess(false);
        setEmail("");
      }, 4000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Échec de l'envoi de l'e-mail.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 sm:p-7 border border-slate-100 relative">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-slate-600 rounded-lg">
          <X size={18} />
        </button>

        {!success ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0">
                <Mail size={20} />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900 text-lg">Recevoir ce rapport complet</h3>
                <p className="text-xs text-slate-500">Nous vous envoyons le bilan PDF et les correctifs.</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Votre adresse e-mail</label>
              <input
                type="email"
                placeholder="votre.email@entreprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            {error && <p className="text-xs text-red-600 font-medium">{error}</p>}

            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-100 disabled:opacity-50"
            >
              {loading ? <Loader size={16} className="animate-spin" /> : <Send size={16} />}
              {loading ? "Envoi du rapport..." : "Envoyer le rapport par e-mail"}
            </button>
          </form>
        ) : (
          <div className="py-4 text-center space-y-2">
            <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
              <Check size={24} />
            </div>
            <h4 className="font-bold text-slate-900 text-base">Rapport envoyé !</h4>
            <p className="text-xs text-slate-500">Vérifiez votre boîte de réception (et vos spams).</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmailCaptureModal;
