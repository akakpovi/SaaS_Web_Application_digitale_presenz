import React from "react";
import { Sparkles, ExternalLink } from "lucide-react";

interface AdBannerProps {
  slot?: "sidebar" | "dashboard" | "footer";
  className?: string;
}

export const AdBanner: React.FC<AdBannerProps> = ({ slot = "dashboard", className = "" }) => {
  // Flag d'activation : facile à activer ou brancher à Google AdSense / Sponsors
  const ADS_ENABLED = true;

  if (!ADS_ENABLED) return null;

  if (slot === "sidebar") {
    return (
      <div className={`p-3 mx-2 my-2 rounded-xl bg-gradient-to-br from-indigo-50/50 to-slate-50 border border-indigo-100/60 text-center ${className}`}>
        <div className="flex items-center justify-center gap-1 text-[10px] uppercase font-bold tracking-wider text-indigo-500 mb-1">
          <Sparkles size={10} /> Sponsor
        </div>
        <p className="text-xs font-medium text-slate-700 leading-tight">
          Hébergez vos sites avec notre partenaire Cloud haute vitesse.
        </p>
        <a
          href="#"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 mt-1.5"
        >
          Découvrir <ExternalLink size={10} />
        </a>
      </div>
    );
  }

  return (
    <div className={`p-4 rounded-xl bg-gradient-to-r from-slate-50 via-indigo-50/40 to-slate-50 border border-slate-200/80 flex flex-col sm:flex-row items-center justify-between gap-3 ${className}`}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600/10 text-indigo-600 flex items-center justify-center flex-shrink-0">
          <Sparkles size={16} />
        </div>
        <div className="text-left">
          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-500">Espace Partenaire</span>
          <p className="text-xs font-medium text-slate-700">
            Besoin d'un nom de domaine ou d'un CDN sécurisé ? Profitez de -20% chez notre hébergeur recommandé.
          </p>
        </div>
      </div>
      <a
        href="#"
        target="_blank"
        rel="noopener noreferrer"
        className="px-3 py-1.5 bg-white border border-slate-200 hover:border-indigo-300 text-xs font-semibold text-slate-700 hover:text-indigo-600 rounded-lg shadow-sm transition-all whitespace-nowrap"
      >
        En savoir plus
      </a>
    </div>
  );
};

export default AdBanner;
