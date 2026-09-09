import React, { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Lock, ArrowLeft, CheckCircle, AlertCircle, Eye, EyeOff } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function ResetPassword() {
  const { lang, uidb64, token } = useParams<{ lang?: string, uidb64: string, token: string }>();
  const { i18n } = useTranslation();
  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    if (password.length < 12) {
      setError("Le mot de passe doit contenir au moins 12 caractères.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await axios.post(`${API_BASE}/auth/password/reset/confirm/`, { 
        uidb64, 
        token, 
        new_password: password 
      });
      setSuccess(true);
      setTimeout(() => {
        navigate(`/${currentLang}/login`);
      }, 3000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.token?.[0] ||
        err.response?.data?.new_password?.[0] ||
        "Le lien de réinitialisation est invalide ou a expiré."
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
                <h2 className="text-xl font-bold text-slate-900">Mot de passe modifié</h2>
                <p className="text-slate-500 mt-2 text-sm leading-relaxed">
                  Votre mot de passe a été réinitialisé avec succès. Vous allez être redirigé vers la page de connexion...
                </p>
              </div>
              <Link 
                to={`/${currentLang}/login`}
                className="block w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors"
              >
                Se connecter maintenant
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-slate-900">Nouveau mot de passe</h2>
                <p className="text-slate-500 mt-2 text-sm">
                  Veuillez choisir un nouveau mot de passe sécurisé pour votre compte.
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
                    Nouveau mot de passe
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Lock size={18} />
                    </div>
                    <input
                      type={showPassword ? "text" : "password"}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="block w-full pl-10 pr-10 py-3 bg-slate-50 border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors"
                      placeholder="Min. 12 caractères"
                    />
                    <button
                      type="button"
                      className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">
                    Confirmer le mot de passe
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Lock size={18} />
                    </div>
                    <input
                      type={showPassword ? "text" : "password"}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="block w-full pl-10 pr-4 py-3 bg-slate-50 border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors"
                      placeholder="Répéter le mot de passe"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || !password || !confirmPassword}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-indigo-200 transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    "Réinitialiser le mot de passe"
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
