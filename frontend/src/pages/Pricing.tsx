import React from "react";
import { Link } from "react-router-dom";
import { Check, Heart, ShieldCheck, Zap, Globe, Sparkles, ArrowRight } from "lucide-react";

export const Pricing: React.FC = () => {
  const features = [
    "Surveillance illimitée de vos sites web",
    "Audits techniques & scores SEO complets",
    "Scanner de sécurité (ports, vulnérabilités, malware)",
    "Contrôles SSL, DNS, et en-têtes HTTP",
    "Alertes instantanées par email et webhook",
    "Rapports de santé générés automatiquement",
    "Zéro carte bancaire requise",
    "Accès immédiat à toutes les nouvelles fonctionnalités",
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto w-full text-center">
        {/* Badge Gratuit */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold uppercase tracking-wider mb-6">
          <Sparkles size={14} /> Offre 100% Gratuite
        </div>

        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight">
          Une surveillance complète de vos sites, <span className="text-indigo-600">sans aucun frais.</span>
        </h1>
        <p className="mt-4 text-base sm:text-lg text-slate-600 max-w-2xl mx-auto">
          Presence SaaS est mis à disposition gratuitement pour tous les créateurs, développeurs et entreprises.
        </p>

        {/* Unique Card Free */}
        <div className="mt-10 bg-white border-2 border-indigo-500/30 rounded-3xl p-8 sm:p-10 shadow-xl shadow-indigo-100/50 max-w-2xl mx-auto text-left relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-indigo-600 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider">
            Accès Illimité
          </div>

          <div className="flex items-baseline justify-between gap-4 border-b border-slate-100 pb-6 mb-6">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Plan Gratuit & Ouvert</h2>
              <p className="text-xs text-slate-500 mt-1">Toutes les fonctionnalités incluses sans engagement</p>
            </div>
            <div className="text-right">
              <span className="text-4xl font-black text-slate-900">0€</span>
              <span className="text-xs text-slate-500 font-medium"> / pour toujours</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-8">
            {features.map((feat, idx) => (
              <div key={idx} className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Check size={12} strokeWidth={3} />
                </div>
                <span className="text-xs sm:text-sm font-medium text-slate-700">{feat}</span>
              </div>
            ))}
          </div>

          <Link
            to="/register"
            className="w-full py-3.5 px-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-center flex items-center justify-center gap-2 shadow-lg shadow-indigo-200 transition-all text-sm"
          >
            Commencer gratuitement <ArrowRight size={16} />
          </Link>
        </div>

        {/* Explication du modèle économique */}
        <div className="mt-12 bg-white/60 border border-slate-200 rounded-2xl p-6 max-w-2xl mx-auto text-left">
          <div className="flex items-start gap-3">
            <Heart size={20} className="text-rose-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Pourquoi est-ce gratuit ?</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                Notre mission est d'offrir un outil d'observabilité accessible à tous. La plateforme est financée par des sponsors technologiques et des partenariats ciblés non intrusifs.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="text-center mt-12">
        <Link to="/" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
          ← Retour à l'accueil
        </Link>
      </div>
    </div>
  );
};

export default Pricing;
