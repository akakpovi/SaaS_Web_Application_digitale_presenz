import React, { useState } from 'react';
import { useSearchParams, useNavigate, Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function Register() {
  const { register } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { lang } = useParams<{ lang?: string }>();
  const { i18n } = useTranslation();

  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';

  const scanId = searchParams.get('scan_id');
  const initialUrl = searchParams.get('url') || '';
  const source = searchParams.get('source');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await register(email, password, name || email.split('@')[0]);

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
        err.response?.data?.email?.[0] ||
        "Erreur lors de l'inscription. Veuillez vérifier vos informations."
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
            {currentLang === 'fr' ? 'Créer votre compte gratuit' : currentLang === 'de' ? 'Kostenloses Konto erstellen' : 'Create your free account'}
          </h2>
          {source === 'rate_limit' ? (
            <p className="mt-2 text-xs text-amber-600 font-medium bg-amber-50 p-2 rounded-lg border border-amber-200">
              ⚡ {currentLang === 'fr' ? 'Débloquez des scans illimités et la surveillance automatique pour votre site.' : 'Unlock unlimited scans and automated monitoring.'}
            </p>
          ) : (
            <p className="mt-2 text-sm text-slate-500">
              {currentLang === 'fr' ? 'Accédez au diagnostic complet, aux alertes et au monitoring illimité.' : 'Access full diagnostics, alerts and unlimited monitoring.'}
            </p>
          )}
          {initialUrl && (
            <p className="mt-1 text-xs text-slate-400">
              Site : <strong className="text-slate-600">{initialUrl}</strong>
            </p>
          )}
        </div>

        {error && (
          <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
            {error}
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              {currentLang === 'fr' ? 'Nom ou Entreprise' : 'Name / Company'}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mon Nom"
              className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

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
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              {currentLang === 'fr' ? 'Mot de passe *' : 'Password *'}
            </label>
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
            {loading ? '...' : currentLang === 'fr' ? 'Démarrer gratuitement' : 'Get started for free'}
          </button>
        </form>

        <div className="text-center text-xs text-slate-500">
          {currentLang === 'fr' ? 'Déjà un compte ?' : 'Already have an account?'} {' '}
          <Link to={`/${currentLang}/login${searchParams.toString() ? `?${searchParams.toString()}` : ''}`} className="font-semibold text-indigo-600 hover:text-indigo-500">
            {currentLang === 'fr' ? 'Se connecter' : 'Log in'}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Register;
