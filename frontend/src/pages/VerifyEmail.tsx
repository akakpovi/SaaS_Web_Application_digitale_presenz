import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { CheckCircle, AlertCircle, Loader } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function VerifyEmail() {
  const { lang, uidb64, token } = useParams<{ lang?: string, uidb64: string, token: string }>();
  const { i18n } = useTranslation();
  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    const verify = async () => {
      try {
        await axios.post(`${API_BASE}/auth/email/verify/`, { uidb64, token });
        if (isMounted) setStatus('success');
      } catch (err: any) {
        if (isMounted) {
          setStatus('error');
          setErrorMsg(
            err.response?.data?.detail || 
            err.response?.data?.token?.[0] || 
            "Le lien de vérification est invalide ou a expiré."
          );
        }
      }
    };

    if (uidb64 && token) {
      verify();
    } else {
      setStatus('error');
      setErrorMsg("Paramètres manquants dans l'URL.");
    }

    return () => {
      isMounted = false;
    };
  }, [uidb64, token]);

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

        <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 p-8 border border-slate-100 text-center">
          {status === 'loading' && (
            <div className="space-y-6">
              <div className="flex justify-center">
                <Loader size={48} className="text-indigo-600 animate-spin" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Vérification en cours</h2>
                <p className="text-slate-500 mt-2 text-sm">Veuillez patienter pendant la validation de votre adresse email...</p>
              </div>
            </div>
          )}

          {status === 'success' && (
            <div className="space-y-6">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle size={32} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Email vérifié !</h2>
                <p className="text-slate-500 mt-2 text-sm leading-relaxed">
                  Votre adresse email a été validée avec succès. Vous pouvez maintenant profiter de toutes les fonctionnalités de votre compte.
                </p>
              </div>
              <Link 
                to={`/${currentLang}/login`}
                className="block w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors"
              >
                Se connecter
              </Link>
            </div>
          )}

          {status === 'error' && (
            <div className="space-y-6">
              <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto">
                <AlertCircle size={32} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Échec de la vérification</h2>
                <p className="text-slate-500 mt-2 text-sm leading-relaxed">
                  {errorMsg}
                </p>
              </div>
              <div className="flex gap-4">
                <Link 
                  to={`/${currentLang}/login`}
                  className="flex-1 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors"
                >
                  Retour
                </Link>
                <Link 
                  to={`/${currentLang}/register`}
                  className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors"
                >
                  S'inscrire
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
