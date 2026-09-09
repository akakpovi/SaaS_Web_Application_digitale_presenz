import React, { useState } from 'react';
import { useNavigate, Link, useParams, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const { lang } = useParams<{ lang?: string }>();
  const { i18n } = useTranslation();

  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchParams] = useSearchParams();
  const scanId = searchParams.get('scan_id');

  // Si l'utilisateur est déjà authentifié, on le redirige
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(`/${currentLang}/app/dashboard`, { replace: true });
    }
  }, [isAuthenticated, navigate, currentLang]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await login(email, password);
      
      if (scanId) {
        try {
          // Token is automatically injected by the api interceptor
          await api.post(`/public/scan/${scanId}/convert/`);
        } catch (convertErr) {
          console.error("Failed to convert public scan:", convertErr);
        }
      }

      navigate(`/${currentLang}/app/dashboard`);

    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        "Identifiants incorrects. Veuillez réessayer."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-2xl shadow-xl border border-slate-200">
        <div className="text-center">
          <Link to={`/${currentLang}/`} className="inline-flex items-center gap-2 font-bold text-indigo-600 text-xl">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm">
              P
            </div>
            Presence
          </Link>
          <h2 className="mt-4 text-2xl font-black text-slate-900 tracking-tight">
            {currentLang === 'fr' ? 'Se connecter' : currentLang === 'de' ? 'Einloggen' : 'Log in'}
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            {currentLang === 'fr' ? 'Accédez à votre tableau de bord et à vos rapports.' : 'Access your dashboard and reports.'}
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
            {error}
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              {currentLang === 'fr' ? 'Adresse Email *' : 'Email Address *'}
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="contact@votresite.com"
              className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                {currentLang === 'fr' ? 'Mot de passe *' : 'Password *'}
              </label>
              <Link to={`/${currentLang}/forgot-password`} className="text-xs font-medium text-indigo-600 hover:text-indigo-500">
                {currentLang === 'fr' ? 'Mot de passe oublié ?' : 'Forgot password?'}
              </Link>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-lg text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition active:scale-95 disabled:opacity-50"
          >
            {loading ? '...' : currentLang === 'fr' ? 'Se connecter' : 'Log in'}
          </button>
        </form>

        <div className="text-center text-xs text-slate-500">
          {currentLang === 'fr' ? "Pas encore de compte ?" : "Don't have an account?"} {' '}
          <Link to={`/${currentLang}/register${searchParams.toString() ? `?${searchParams.toString()}` : ''}`} className="font-semibold text-indigo-600 hover:text-indigo-500">
            {currentLang === 'fr' ? 'Créer un compte' : 'Sign up'}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Login;
