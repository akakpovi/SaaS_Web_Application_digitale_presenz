import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

const T = {
  fr: {
    title: "Centre de Pilotage (Admin)",
    subtitle: "Métriques globales, croissance et monétisation.",
    users: "Utilisateurs",
    sites: "Sites Suivis",
    scans: "Scans Exécutés",
    monetization: "Indice Monétisation",
    traffic: "Trafic 14 derniers jours",
    views: "Vues",
    uniques: "Visiteurs uniques",
    humans: "Humains",
    bots: "Bots",
    funnel: "Funnel de Conversion",
    signups: "Inscriptions",
    addedSites: "Sites ajoutés",
    scansTriggered: "Scans lancés",
    cookies: "Consentement Cookies",
    acceptedAll: "Tout accepté",
    essentialOnly: "Essentiels uniquement",
    acceptanceRate: "Taux d'acceptation",
    pwa: "Application PWA",
    installs: "Installations",
    dismissed: "Reportées",
    revenue: "Revenus Estimés",
    ads: "Publicité (CPM)",
    affiliate: "Affiliation",
    total: "Total estimé",
    recentUsers: "Derniers inscrits",
    sitesCount: "sites",
    noData: "Aucune donnée disponible",
    errorAdmin: "Accès réservé aux administrateurs.",
    errorLoad: "Erreur lors du chargement des statistiques.",
  },
  en: {
    title: "Admin Dashboard",
    subtitle: "Global metrics, growth and monetization.",
    users: "Users",
    sites: "Monitored Sites",
    scans: "Scans Executed",
    monetization: "Monetization Index",
    traffic: "Traffic (Last 14 days)",
    views: "Views",
    uniques: "Unique visitors",
    humans: "Humans",
    bots: "Bots",
    funnel: "Conversion Funnel",
    signups: "Signups",
    addedSites: "Sites added",
    scansTriggered: "Scans triggered",
    cookies: "Cookie Consent",
    acceptedAll: "All accepted",
    essentialOnly: "Essential only",
    acceptanceRate: "Acceptance rate",
    pwa: "PWA App",
    installs: "Installs",
    dismissed: "Dismissed",
    revenue: "Estimated Revenue",
    ads: "Ads (CPM)",
    affiliate: "Affiliate",
    total: "Estimated total",
    recentUsers: "Recent signups",
    sitesCount: "sites",
    noData: "No data available",
    errorAdmin: "Admin access required.",
    errorLoad: "Error loading statistics.",
  },
  de: {
    title: "Admin-Cockpit",
    subtitle: "Globale Metriken, Wachstum und Monetarisierung.",
    users: "Benutzer",
    sites: "Überwachte Sites",
    scans: "Ausgeführte Scans",
    monetization: "Monetarisierungsindex",
    traffic: "Traffic (Letzte 14 Tage)",
    views: "Aufrufe",
    uniques: "Eindeutige Besucher",
    humans: "Menschen",
    bots: "Bots",
    funnel: "Conversion-Funnel",
    signups: "Registrierungen",
    addedSites: "Sites hinzugefügt",
    scansTriggered: "Scans ausgelöst",
    cookies: "Cookie-Einwilligung",
    acceptedAll: "Alle akzeptiert",
    essentialOnly: "Nur essenzielle",
    acceptanceRate: "Akzeptanzrate",
    pwa: "PWA-App",
    installs: "Installationen",
    dismissed: "Abgelehnt",
    revenue: "Geschätzte Einnahmen",
    ads: "Werbung (CPM)",
    affiliate: "Affiliate",
    total: "Geschätzt gesamt",
    recentUsers: "Letzte Registrierungen",
    sitesCount: "Sites",
    noData: "Keine Daten verfügbar",
    errorAdmin: "Admin-Zugang erforderlich.",
    errorLoad: "Fehler beim Laden der Statistiken.",
  },
};

export function AdminDashboard() {
  const { i18n } = useTranslation();
  const currentLang = ((i18n.language || 'fr').split('-')[0].toLowerCase()) as 'fr' | 'en' | 'de';
  const t = T[currentLang] || T.fr;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    axios.get(`${API_BASE}/analytics/admin/overview/`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then(res => setData(res.data))
      .catch(err => {
        if (err.response?.status === 403) {
          setError(t.errorAdmin);
        } else {
          setError(t.errorLoad);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl text-center text-red-700 text-sm max-w-lg mx-auto">
        👑 {error}
      </div>
    );
  }

  const overview = data?.overview || {};
  const traffic = data?.traffic_14d || [];
  const funnel = data?.funnel || {};
  const cookies = data?.cookies || {};
  const pwa = data?.pwa || {};
  const revenue = data?.estimated_revenue || {};
  const recentUsers = data?.latest_users || [];

  const totalViews = traffic.reduce((acc: number, d: any) => acc + (d.views || 0), 0);
  const totalUniques = traffic.reduce((acc: number, d: any) => acc + (d.uniques || 0), 0);
  const cookieTotal = (cookies.accepted_all || 0) + (cookies.essential_only || 0);
  const cookieRate = cookieTotal > 0 ? Math.round(((cookies.accepted_all || 0) / cookieTotal) * 100) : 0;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* HEADER */}
      <div className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">👑 {t.title}</h1>
        <p className="text-sm text-slate-500 mt-1">{t.subtitle}</p>
      </div>

      {/* KPI CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t.users}</p>
          <p className="text-3xl font-black text-slate-900 mt-2">{overview.total_users || 0}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t.sites}</p>
          <p className="text-3xl font-black text-indigo-600 mt-2">{overview.total_websites || 0}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t.scans}</p>
          <p className="text-3xl font-black text-emerald-600 mt-2">{overview.total_scans || 0}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t.monetization}</p>
          <p className="text-3xl font-black text-amber-600 mt-2">{overview.monetization_index || 0}<span className="text-sm text-slate-400"> / 100</span></p>
        </div>
      </div>

      {/* TRAFFIC & FUNNEL ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Traffic 14j */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{t.traffic}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-indigo-600">{totalViews}</p>
              <p className="text-xs text-slate-500">{t.views}</p>
            </div>
            <div className="bg-slate-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-emerald-600">{totalUniques}</p>
              <p className="text-xs text-slate-500">{t.uniques}</p>
            </div>
          </div>
          {traffic.length > 0 ? (
            <div className="flex items-end gap-1 h-20">
              {traffic.slice(-14).map((d: any, i: number) => {
                const maxV = Math.max(...traffic.map((d2: any) => d2.views || 1));
                const h = Math.max(4, ((d.views || 0) / maxV) * 100);
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full rounded-t bg-indigo-400" style={{ height: `${h}%` }} />
                    <span className="text-[8px] text-slate-400">{d.day?.slice(5) || ''}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-400 text-center py-4">{t.noData}</p>
          )}
        </div>

        {/* Funnel */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{t.funnel}</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between bg-slate-50 p-3 rounded-xl">
              <span className="text-sm font-semibold text-slate-700">📝 {t.signups}</span>
              <span className="text-lg font-black text-indigo-600">{funnel.signups || 0}</span>
            </div>
            <div className="flex items-center justify-between bg-slate-50 p-3 rounded-xl">
              <span className="text-sm font-semibold text-slate-700">🌐 {t.addedSites}</span>
              <span className="text-lg font-black text-emerald-600">{funnel.added_websites || 0}</span>
            </div>
            <div className="flex items-center justify-between bg-slate-50 p-3 rounded-xl">
              <span className="text-sm font-semibold text-slate-700">🔍 {t.scansTriggered}</span>
              <span className="text-lg font-black text-amber-600">{funnel.scans_triggered || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* COOKIES & PWA ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cookies */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">🍪 {t.cookies}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-emerald-600">{cookies.accepted_all || 0}</p>
              <p className="text-xs text-emerald-600">{t.acceptedAll}</p>
            </div>
            <div className="bg-slate-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-slate-600">{cookies.essential_only || 0}</p>
              <p className="text-xs text-slate-500">{t.essentialOnly}</p>
            </div>
          </div>
          <div className="bg-slate-50 p-3 rounded-xl flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-700">{t.acceptanceRate}</span>
            <span className="text-lg font-black text-emerald-600">{cookieRate}%</span>
          </div>
        </div>

        {/* PWA & Revenue */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">📲 {t.pwa} & 💰 {t.revenue}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-indigo-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-indigo-600">{pwa.installs || 0}</p>
              <p className="text-xs text-indigo-600">{t.installs}</p>
            </div>
            <div className="bg-slate-50 p-3 rounded-xl text-center">
              <p className="text-2xl font-black text-slate-600">{pwa.dismissed || 0}</p>
              <p className="text-xs text-slate-500">{t.dismissed}</p>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between bg-slate-50 p-2 rounded-lg text-xs">
              <span className="text-slate-600">{t.ads}</span>
              <span className="font-bold text-slate-700">{revenue.ads_eur || 0} €</span>
            </div>
            <div className="flex items-center justify-between bg-slate-50 p-2 rounded-lg text-xs">
              <span className="text-slate-600">{t.affiliate}</span>
              <span className="font-bold text-slate-700">{revenue.affiliate_eur || 0} €</span>
            </div>
            <div className="flex items-center justify-between bg-emerald-50 p-3 rounded-xl">
              <span className="text-sm font-bold text-emerald-700">{t.total}</span>
              <span className="text-xl font-black text-emerald-600">{revenue.total_eur || 0} €</span>
            </div>
          </div>
        </div>
      </div>

      {/* RECENT USERS */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">👥 {t.recentUsers}</h3>
        {recentUsers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="pb-3">Email</th>
                  <th className="pb-3">{t.sitesCount}</th>
                  <th className="pb-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {recentUsers.map((u: any) => (
                  <tr key={u.id}>
                    <td className="py-3 font-semibold text-slate-900">{u.email}</td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs font-bold">
                        {u.websites_count || 0}
                      </span>
                    </td>
                    <td className="py-3 text-xs text-slate-400">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString(currentLang === 'fr' ? 'fr-FR' : currentLang === 'de' ? 'de-DE' : 'en-US') : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 text-center py-4">{t.noData}</p>
        )}
      </div>
    </div>
  );
}

export default AdminDashboard;
