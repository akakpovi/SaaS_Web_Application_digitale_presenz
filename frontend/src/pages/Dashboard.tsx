import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { UpgradeBanner } from '../components/UpgradeBanner';
import { ActionRequired } from '../components/ActionRequired';

interface Website {
  id: string;
  domain: string;
  display_name: string;
  health_score: number;
  health_status: 'healthy' | 'warning' | 'critical' | 'neutral';
  is_active: boolean;
  created_at: string;
  last_scan_at: string;
}

interface Alert {
  id: string;
  message: string;
  [key: string]: any; 
}

export const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const { lang } = useParams<{ lang: string }>();
  const currentLang = lang || 'en';
  const { plan } = useAuth();
  
  const [websites, setWebsites] = useState<Website[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUpgradeBanner, setShowUpgradeBanner] = useState(true);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [websitesRes, alertsRes] = await Promise.all([
        api.get('/websites/'),
        api.get('/alerts/', { params: { status: 'firing' } })
      ]);
      
      const websitesData = Array.isArray(websitesRes.data) ? websitesRes.data : websitesRes.data?.results || [];
      const alertsData = alertsRes.data?.results || [];
      
      setWebsites(websitesData);
      setAlerts(alertsData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(t('dashboard.error_loading', 'Erreur lors du chargement du tableau de bord.'));
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto p-8 flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto p-8 flex flex-col items-center justify-center h-64">
        <p className="text-red-500 mb-4">{error}</p>
        <button 
          onClick={fetchData}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl font-bold transition-colors"
        >
          {t('common.retry', 'Réessayer')}
        </button>
      </div>
    );
  }

  // Calculate KPIs
  const monitoredSites = websites.length;
  const averageHealth = monitoredSites 
    ? Math.round(websites.reduce((acc, site) => acc + site.health_score, 0) / monitoredSites) 
    : 0;
  const nonCriticalSites = websites.filter(s => s.health_status !== 'critical').length;
  const estimatedUptime = monitoredSites ? Math.round((nonCriticalSites / monitoredSites) * 100) : 100;
  const openAlerts = alerts.length;

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-600 bg-emerald-50';
    if (score >= 50) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-emerald-100 text-emerald-800';
      case 'warning': return 'bg-amber-100 text-amber-800';
      case 'critical': return 'bg-red-100 text-red-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return t('common.never', 'Jamais scanné');
    return new Date(dateString).toLocaleDateString(currentLang, { 
      year: 'numeric', month: 'short', day: 'numeric', 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          {t('dashboard.title', 'Tableau de bord')}
        </h1>
        <p className="text-sm text-slate-500">
          {t('dashboard.subtitle', 'Aperçu de vos sites web et performances')}
        </p>
      </div>

      {/* Upgrade Banner */}
      {plan?.tier === 'free' && showUpgradeBanner && (
        <UpgradeBanner 
          usedSites={websites.length} 
          maxSites={plan?.limits?.websites || 1} 
          onDismiss={() => setShowUpgradeBanner(false)} 
        />
      )}

      {/* Action Required for Alerts */}
      {alerts.length > 0 && (
        <ActionRequired 
          alerts={alerts.length} 
          issuesCount={alerts.length} 
          onViewAll={() => {}} 
        />
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col bg-gradient-to-br from-white to-slate-50">
          <span className="text-sm text-slate-500 font-medium">{t('dashboard.avg_score', 'Santé moyenne')}</span>
          <span className={`text-3xl font-black mt-2 ${getScoreColor(averageHealth).split(' ')[0]}`}>
            {averageHealth}/100
          </span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col bg-gradient-to-br from-white to-slate-50">
          <span className="text-sm text-slate-500 font-medium">{t('dashboard.monitored_sites', 'Sites surveillés')}</span>
          <span className="text-3xl font-black mt-2 text-slate-900">{monitoredSites}</span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col bg-gradient-to-br from-white to-slate-50">
          <span className="text-sm text-slate-500 font-medium">{t('dashboard.uptime', 'Temps de fonctionnement estimé')}</span>
          <span className="text-3xl font-black mt-2 text-emerald-600">{estimatedUptime}%</span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col bg-gradient-to-br from-white to-slate-50">
          <span className="text-sm text-slate-500 font-medium">{t('dashboard.open_alerts', 'Alertes ouvertes')}</span>
          <span className={`text-3xl font-black mt-2 ${openAlerts > 0 ? 'text-red-600' : 'text-slate-900'}`}>
            {openAlerts}
          </span>
        </div>
      </div>

      {/* Websites Grid */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4">
          {t('dashboard.your_sites', 'Vos sites web')}
        </h2>
        
        {websites.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 text-center flex flex-col items-center">
            <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">
              {t('dashboard.no_sites_title', 'Aucun site web ajouté')}
            </h3>
            <p className="text-slate-500 mb-6 max-w-md">
              {t('dashboard.no_sites_desc', 'Commencez à surveiller votre présence numérique en ajoutant votre premier site web.')}
            </p>
            <Link 
              to={`/${currentLang}/app/websites/new`}
              className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-6 py-3 font-bold transition-all shadow-sm hover:shadow"
            >
              {t('dashboard.add_first_site', 'Ajouter un site web')}
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {websites.map(site => (
              <Link 
                key={site.id} 
                to={`/${currentLang}/app/websites/${site.id}`}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 block hover:shadow-md hover:border-indigo-200 transition-all group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      {site.display_name || site.domain}
                    </h3>
                    <p className="text-sm text-slate-500">{site.domain}</p>
                  </div>
                  <div className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${getStatusColor(site.health_status)}`}>
                    {t(`dashboard.status.${site.health_status}`, site.health_status)}
                  </div>
                </div>
                
                <div className="flex items-center justify-between mt-6">
                  <div className="flex items-center space-x-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${getScoreColor(site.health_score)}`}>
                      {site.health_score}
                    </div>
                    <div className="text-xs text-slate-500">
                      <div>{t('dashboard.health_score', 'Score de santé')}</div>
                      <div>{formatDate(site.last_scan_at)}</div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
