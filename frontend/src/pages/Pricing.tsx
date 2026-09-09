import React, { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Check, Zap, Shield, ArrowRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';

export function Pricing() {
  const { lang } = useParams<{ lang?: string }>();
  const currentLang = (lang || 'fr').split('-')[0].toLowerCase();
  const { user, plan, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [loadingTier, setLoadingTier] = useState<string | null>(null);

  const handleUpgrade = async (tier: string) => {
    if (!user) {
      navigate(`/${currentLang}/register`);
      return;
    }
    
    setLoadingTier(tier);
    try {
      const token = localStorage.getItem('access_token');
      await api.post('/subscriptions/upgrade/', {
        plan_tier: tier,
        billing_cycle: 'monthly'
      }, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      await refreshUser();
      navigate(`/${currentLang}/app/dashboard`);
    } catch (error) {
      console.error(error);
      alert(currentLang === 'fr' ? 'Erreur lors de la mise à niveau.' : 'Error during upgrade.');
    } finally {
      setLoadingTier(null);
    }
  };

  const isCurrentPlan = (tier: string) => {
    if (!plan) return tier === 'free';
    return plan.tier === tier;
  };

  const texts = {
    fr: {
      title: "Des tarifs simples, sans surprise",
      subtitle: "Choisissez le plan adapté à la taille de votre entreprise. Commencez gratuitement.",
      free: "Gratuit",
      pro: "Pro",
      business: "Business",
      current: "Plan actuel",
      upgrade: "Passer à ce plan",
      loading: "Traitement...",
      freeDesc: "Idéal pour tester ou pour un seul petit projet.",
      proDesc: "Pour les indépendants et petites entreprises.",
      bizDesc: "Pour les agences et grandes entreprises.",
      features: {
        sites1: "1 site web",
        sites5: "5 sites web",
        sitesU: "Sites illimités",
        uptime: "Monitoring Uptime",
        seoBasic: "Audit SEO basique",
        seoAdv: "Audit SEO avancé & Mots-clés",
        reports: "Rapports PDF Marque Blanche",
        support: "Support prioritaire",
        security: "Analyse sécurité avancée",
      }
    },
    en: {
      title: "Simple, transparent pricing",
      subtitle: "Choose the plan that fits your business. Start for free.",
      free: "Free",
      pro: "Pro",
      business: "Business",
      current: "Current plan",
      upgrade: "Upgrade to this plan",
      loading: "Processing...",
      freeDesc: "Perfect for testing or a single small project.",
      proDesc: "For freelancers and small businesses.",
      bizDesc: "For agencies and large companies.",
      features: {
        sites1: "1 website",
        sites5: "5 websites",
        sitesU: "Unlimited websites",
        uptime: "Uptime Monitoring",
        seoBasic: "Basic SEO Audit",
        seoAdv: "Advanced SEO & Keywords",
        reports: "White-label PDF Reports",
        support: "Priority Support",
        security: "Advanced Security Analysis",
      }
    },
    de: {
      title: "Einfache, transparente Preise",
      subtitle: "Wählen Sie den Plan, der zu Ihnen passt. Kostenlos starten.",
      free: "Kostenlos",
      pro: "Pro",
      business: "Business",
      current: "Aktueller Plan",
      upgrade: "Jetzt upgraden",
      loading: "Wird bearbeitet...",
      freeDesc: "Ideal zum Testen oder für ein kleines Projekt.",
      proDesc: "Für Freiberufler und kleine Unternehmen.",
      bizDesc: "Für Agenturen und Großunternehmen.",
      features: {
        sites1: "1 Website",
        sites5: "5 Websites",
        sitesU: "Unbegrenzte Websites",
        uptime: "Uptime Monitoring",
        seoBasic: "Basis SEO-Audit",
        seoAdv: "Erweitertes SEO & Keywords",
        reports: "White-Label PDF-Berichte",
        support: "Prioritäts-Support",
        security: "Erweiterte Sicherheitsanalyse",
      }
    }
  };

  const t = texts[currentLang as keyof typeof texts] || texts.en;

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to={`/${currentLang}/`} className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-sm">P</span>
            </div>
            <span className="font-bold text-slate-900 tracking-tight">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link to={`/${currentLang}/blog`} className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">Blog</Link>
          </nav>
          {user ? (
            <Link to={`/${currentLang}/app/dashboard`} className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-bold rounded-xl shadow-lg shadow-indigo-200 hover:bg-indigo-700 hover:-translate-y-0.5 transition-all">
              Dashboard
            </Link>
          ) : (
            <Link to={`/${currentLang}/login`} className="px-5 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-bold rounded-xl shadow-sm hover:bg-slate-50 transition-all">
              Se connecter
            </Link>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-24">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight mb-4">{t.title}</h1>
          <p className="text-lg text-slate-600">{t.subtitle}</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 items-start">
          {/* Free */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm relative">
            <h3 className="text-xl font-bold text-slate-900 mb-2">{t.free}</h3>
            <p className="text-sm text-slate-500 mb-6 h-10">{t.freeDesc}</p>
            <div className="mb-6">
              <span className="text-4xl font-black text-slate-900">0€</span>
              <span className="text-slate-500"> / mois</span>
            </div>
            
            <button
              disabled={isCurrentPlan('free')}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm transition-all mb-8 ${isCurrentPlan('free') ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'}`}
            >
              {isCurrentPlan('free') ? t.current : t.upgrade}
            </button>

            <ul className="space-y-4 text-sm text-slate-600">
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.sites1}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.uptime}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.seoBasic}</li>
            </ul>
          </div>

          {/* Pro */}
          <div className="bg-slate-900 rounded-3xl p-8 border border-slate-800 shadow-2xl relative transform md:-translate-y-4">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-indigo-500 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              Populaire
            </div>
            <h3 className="text-xl font-bold text-white mb-2">{t.pro}</h3>
            <p className="text-sm text-slate-400 mb-6 h-10">{t.proDesc}</p>
            <div className="mb-6">
              <span className="text-4xl font-black text-white">29€</span>
              <span className="text-slate-400"> / mois</span>
            </div>
            
            <button
              onClick={() => handleUpgrade('pro')}
              disabled={isCurrentPlan('pro') || loadingTier === 'pro'}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm transition-all mb-8 ${
                isCurrentPlan('pro') 
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-indigo-500 text-white hover:bg-indigo-400 shadow-lg shadow-indigo-500/25'
              }`}
            >
              {loadingTier === 'pro' ? t.loading : (isCurrentPlan('pro') ? t.current : t.upgrade)}
            </button>

            <ul className="space-y-4 text-sm text-slate-300">
              <li className="flex items-center gap-3"><Check size={18} className="text-indigo-400" /> {t.features.sites5}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-indigo-400" /> {t.features.uptime}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-indigo-400" /> {t.features.seoAdv}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-indigo-400" /> {t.features.reports}</li>
            </ul>
          </div>

          {/* Business */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm relative">
            <h3 className="text-xl font-bold text-slate-900 mb-2">{t.business}</h3>
            <p className="text-sm text-slate-500 mb-6 h-10">{t.bizDesc}</p>
            <div className="mb-6">
              <span className="text-4xl font-black text-slate-900">99€</span>
              <span className="text-slate-500"> / mois</span>
            </div>
            
            <button
              onClick={() => handleUpgrade('business')}
              disabled={isCurrentPlan('business') || loadingTier === 'business'}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm transition-all mb-8 ${isCurrentPlan('business') ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'}`}
            >
              {loadingTier === 'business' ? t.loading : (isCurrentPlan('business') ? t.current : t.upgrade)}
            </button>

            <ul className="space-y-4 text-sm text-slate-600">
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.sitesU}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.security}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.seoAdv}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.reports}</li>
              <li className="flex items-center gap-3"><Check size={18} className="text-emerald-500" /> {t.features.support}</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}

export default Pricing;
