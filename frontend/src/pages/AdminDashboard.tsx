import React, { useEffect, useState } from "react";
import {
  TrendingUp, Users, Globe, Activity, DollarSign,
  Sparkles, Eye, ShieldAlert, Loader, RefreshCw,
  Cookie, Smartphone, UserCheck, Funnel, MousePointerClick
} from "lucide-react";
import api from "../services/api";

interface AdminData {
  metrics: any;
  cookies: { total_consents: number; accepted_all: number; essential_only: number; accept_rate_percent: number };
  pwa: { installs_30d: number; dismissals_30d: number };
  retention: { rate_7d_percent: number; retained_users: number };
  funnel: { landing_visitors: number; signups: number; signup_rate: number; added_website: number; website_rate: number; triggered_scan: number; scan_rate: number };
  monetization: any;
  daily_chart: Array<{ date: string; views: number; uniques: number }>;
  recent_users: Array<{ email: string; full_name: string; date_joined: string; websites_count: number }>;
}

export const AdminDashboard: React.FC = () => {
  const [data, setData] = useState<AdminData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get("/analytics/admin/overview/");
      setData(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Erreur de communication avec le serveur.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadStats(); }, []);

  if (isLoading) return (
    <div className="p-12 text-center">
      <Loader size={36} className="animate-spin text-indigo-600 mx-auto mb-3" />
      <p className="text-sm text-slate-500">Chargement du Centre de Pilotage...</p>
    </div>
  );

  if (error || !data) return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl text-center">
        <ShieldAlert size={36} className="text-red-500 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-red-900">Accès Restreint</h2>
        <p className="text-sm text-red-600 mt-1">{error}</p>
      </div>
    </div>
  );

  const { metrics, cookies, pwa, retention, funnel, monetization, daily_chart, recent_users } = data;
  const maxViews = Math.max(...daily_chart.map(d => d.views), 1);

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-md bg-indigo-600 text-white text-xs font-bold uppercase tracking-wider">Admin</span>
            <h1 className="text-2xl font-bold text-slate-900">Centre de Pilotage & Monétisation</h1>
          </div>
          <p className="text-slate-500 text-sm mt-1">Trafic, cookies, PWA, rétention, funnel et revenus.</p>
        </div>
        <button onClick={loadStats} className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-medium shadow-sm">
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Monétisation */}
      <div className="bg-gradient-to-br from-indigo-900 via-indigo-800 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-center">
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center gap-2 text-indigo-300 text-xs font-bold uppercase tracking-wider">
              <Sparkles size={16} /> Indicateur de Monétisation
            </div>
            <h2 className="text-xl sm:text-2xl font-black">
              Plateforme à <span className="text-emerald-400">{monetization.readiness_percent}%</span> prête
            </h2>
            <div className="w-full bg-white/10 rounded-full h-3.5 p-0.5">
              <div className="bg-gradient-to-r from-amber-400 via-emerald-400 to-indigo-400 h-full rounded-full transition-all" style={{ width: `${Math.max(5, monetization.readiness_percent)}%` }} />
            </div>
            <p className="text-xs text-indigo-100">{monetization.recommendation}</p>
            <p className="text-xs text-indigo-300">💡 {monetization.next_step}</p>
          </div>
          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/10 text-center">
            <p className="text-xs text-indigo-200">Revenus Potentiels</p>
            <p className="text-3xl font-black mt-1">~{monetization.potential_monthly_income_eur} €</p>
            <p className="text-[11px] text-indigo-300 mt-1">/ mois estimé</p>
            <div className="mt-3 pt-3 border-t border-white/10 text-left space-y-1 text-xs text-indigo-100">
              <div className="flex justify-between"><span>Ads estimés :</span><strong>{monetization.ad_revenue_estimate} €</strong></div>
              <div className="flex justify-between"><span>Affiliation :</span><strong>{monetization.affiliate_revenue} €</strong></div>
              <div className="flex justify-between"><span>Clics affiliation :</span><strong>{monetization.affiliate_clicks}</strong></div>
            </div>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Utilisateurs</span><Users size={18} className="text-indigo-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">{metrics.total_users}</p>
          <p className="text-[11px] text-emerald-600 font-semibold mt-1">+{metrics.new_users_30d} (30j) · +{metrics.new_users_7d} (7j)</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Sites Surveillés</span><Globe size={18} className="text-blue-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">{metrics.total_websites}</p>
          <p className="text-[11px] text-slate-500 mt-1">{metrics.total_scans} scans au total</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Visiteurs Aujourd'hui</span><Eye size={18} className="text-emerald-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">{metrics.unique_visitors_today}</p>
          <p className="text-[11px] text-slate-500 mt-1">{metrics.pageviews_today} pages vues</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Humains vs Bots</span><Activity size={18} className="text-purple-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">{metrics.human_requests_30d}</p>
          <p className="text-[11px] text-red-500 font-semibold mt-1">{metrics.bot_requests_30d} requêtes bots bloquées</p>
        </div>
      </div>

      {/* Cookies + PWA + Rétention */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2 mb-3"><Cookie size={16} className="text-amber-500" /> Cookies (30j)</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-slate-600">Total consentements :</span><strong>{cookies.total_consents}</strong></div>
            <div className="flex justify-between"><span className="text-slate-600">Accepté tout :</span><strong className="text-emerald-600">{cookies.accepted_all}</strong></div>
            <div className="flex justify-between"><span className="text-slate-600">Essentiels seuls :</span><strong className="text-amber-600">{cookies.essential_only}</strong></div>
            <div className="flex justify-between border-t pt-2 mt-2"><span className="font-semibold">Taux d'acceptation :</span><strong className="text-indigo-600">{cookies.accept_rate_percent}%</strong></div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2 mb-3"><Smartphone size={16} className="text-indigo-600" /> PWA (30j)</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-slate-600">Installations :</span><strong className="text-emerald-600">{pwa.installs_30d}</strong></div>
            <div className="flex justify-between"><span className="text-slate-600">Reportées :</span><strong className="text-slate-500">{pwa.dismissals_30d}</strong></div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2 mb-3"><UserCheck size={16} className="text-emerald-600" /> Rétention (7j)</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-slate-600">Taux de rétention :</span><strong className="text-indigo-600">{retention.rate_7d_percent}%</strong></div>
            <div className="flex justify-between"><span className="text-slate-600">Utilisateurs revenus :</span><strong>{retention.retained_users}</strong></div>
          </div>
        </div>
      </div>

      {/* Funnel + Graphique */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h3 className="font-bold text-slate-900 text-base mb-4">Trafic 14 derniers jours</h3>
          <div className="h-48 flex items-end gap-2 pb-2">
            {daily_chart.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative">
                <div className="absolute -top-7 bg-slate-800 text-white text-[10px] py-0.5 px-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20">
                  {d.views} vues · {d.uniques} uniques
                </div>
                <div className="w-full bg-indigo-500 group-hover:bg-indigo-600 rounded-t-md transition-all" style={{ height: `${Math.max(8, (d.views / maxViews) * 100)}%` }} />
                <span className="text-[9px] text-slate-400 mt-1">{d.date}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2 mb-4"><Funnel size={16} className="text-indigo-600" /> Funnel de Conversion</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1"><span className="text-slate-600">Visiteurs Landing</span><strong>{funnel.landing_visitors}</strong></div>
              <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-indigo-500 h-2 rounded-full" style={{ width: "100%" }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1"><span className="text-slate-600">Inscriptions</span><strong>{funnel.signups} ({funnel.signup_rate}%)</strong></div>
              <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-indigo-400 h-2 rounded-full" style={{ width: `${Math.max(5, funnel.signup_rate)}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1"><span className="text-slate-600">Sites Ajoutés</span><strong>{funnel.added_website} ({funnel.website_rate}%)</strong></div>
              <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-emerald-400 h-2 rounded-full" style={{ width: `${Math.max(5, funnel.website_rate)}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1"><span className="text-slate-600">Scans Lancés</span><strong>{funnel.triggered_scan} ({funnel.scan_rate}%)</strong></div>
              <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${Math.max(5, funnel.scan_rate)}%` }} /></div>
            </div>
          </div>
        </div>
      </div>

      {/* Derniers Inscrits */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h3 className="font-bold text-slate-900 text-base mb-4">Derniers Inscrits</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {recent_users.map((u, i) => (
            <div key={i} className="p-3 rounded-xl border border-slate-100 hover:bg-slate-50">
              <p className="text-xs font-semibold text-slate-900 truncate">{u.full_name}</p>
              <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">{u.websites_count} site(s)</span>
                <span className="text-[9px] text-slate-400">{u.date_joined}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
