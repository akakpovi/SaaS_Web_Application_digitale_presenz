import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Mail, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function ForgotPassword() {
  const { lang } = useParams<{ lang?: string }>();
  const { i18n } = useTranslation();
  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';

  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await axios.post(`${API_BASE}/auth/password/reset/`, { email });
      setSuccess(true);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.email?.[0] ||
        "Une erreur est survenue."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to={`/${currentLang}`} className="inline-block">
            <div className="flex items-center justify-center gap-2">
              <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-200">
                <span className="text-white font-black text-xl">P</span>
              </div>
              <span className="text-2xl font-black text-slate-900 tracking-tight">Presence</span>
            </div>
          </Link>
        </div>

        <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 p-8 border border-slate-100">
          {success ? (
            <div className="text-center space-y-6">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle size={32} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Email envoyé</h2>
                <p className="text-slate-500 mt-2 text-sm leading-relaxed">
                  Si un compte existe avec l'adresse <strong>{email}</strong>, un email contenant les instructions pour réinitialiser votre mot de passe vous a été envoyé.
                </p>
              </div>
              <Link 
                to={`/${currentLang}/login`}
                className="block w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors"
              >
                Retour à la connexion
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-slate-900">Mot de passe oublié</h2>
                <p className="text-slate-500 mt-2 text-sm">
                  Entrez votre adresse email et nous vous enverrons un lien pour réinitialiser votre mot de passe.
                </p>
              </div>

              {error && (
                <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-xl text-sm font-medium flex items-start gap-3 border border-red-100">
                  <AlertCircle size={18} className="shrink-0 mt-0.5" />
                  <p>{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">
                    Adresse email
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Mail size={18} />
                    </div>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="block w-full pl-10 pr-4 py-3 bg-slate-50 border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors"
                      placeholder="vous@exemple.com"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || !email}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-indigo-200 transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    "Envoyer le lien"
                  )}
                </button>

                <div className="text-center pt-4">
                  <Link 
                    to={`/${currentLang}/login`}
                    className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600 transition-colors"
                  >
                    <ArrowLeft size={16} />
                    Retour à la connexion
                  </Link>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
