import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link } from 'react-router-dom';
import { Activity, Clock, AlertCircle, CheckCircle, RefreshCw, Plus, Play, Power, Globe } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

interface Website {
  id: string;
  domain: string;
  display_name: string;
  health_score: number;
  health_status: 'healthy' | 'warning' | 'critical' | 'neutral';
  is_active: boolean;
  last_scan_at: string | null;
}

interface MonitoringConfig {
  id: string;
  website: string;
  enabled: boolean;
  interval: '5m' | '15m' | '30m' | '1h' | '6h' | '24h';
  last_scan_at: string | null;
  next_scan_at: string | null;
  consecutive_failures: number;
  escalation_level: number;
}

interface MergedSite {
  website: Website;
  config: MonitoringConfig | null;
}

export const Monitoring: React.FC = () => {
  const { t } = useTranslation();
  const { lang = 'en' } = useParams<{ lang: string }>();
  const [mergedSites, setMergedSites] = useState<MergedSite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState<Record<string, boolean>>({});
  const [isToggling, setIsToggling] = useState<Record<string, boolean>>({});

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [websitesRes, configsRes] = await Promise.all([
        api.get('/websites/'),
        api.get('/monitoring/')
      ]);

      const websitesData = Array.isArray(websitesRes.data) ? websitesRes.data : (websitesRes.data.results || []);
      const configsData = Array.isArray(configsRes.data) ? configsRes.data : (configsRes.data.results || []);

      const merged = websitesData.map((website: Website) => {
        const config = configsData.find((c: MonitoringConfig) => c.website === website.id) || null;
        return { website, config };
      });

      setMergedSites(merged);
    } catch (err) {
      console.error('Failed to fetch monitoring data', err);
      setError(t('monitoring.errors.load_failed', 'Erreur lors de la récupération des données de surveillance'));
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleToggleMonitoring = async (websiteId: string, currentStatus: boolean) => {
    setIsToggling(prev => ({ ...prev, [websiteId]: true }));
    try {
      await api.patch(`/monitoring/websites/${websiteId}/`, { enabled: !currentStatus });
      setMergedSites(prev => prev.map(site => {
        if (site.website.id === websiteId && site.config) {
          return { ...site, config: { ...site.config, enabled: !currentStatus } };
        }
        return site;
      }));
    } catch (err) {
      console.error('Failed to toggle monitoring', err);
    } finally {
      setIsToggling(prev => ({ ...prev, [websiteId]: false }));
    }
  };

  const handleScanNow = async (websiteId: string) => {
    setIsScanning(prev => ({ ...prev, [websiteId]: true }));
    try {
      await api.post(`/monitoring/websites/${websiteId}/scan/`);
      // Optimistically trigger a refetch after a short delay
      setTimeout(fetchData, 2000);
    } catch (err) {
      console.error('Failed to trigger scan', err);
    } finally {
      setIsScanning(prev => ({ ...prev, [websiteId]: false }));
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return t('monitoring.never', 'Jamais');
    return new Date(dateString).toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  };

  const totalSites = mergedSites.length;
  const sitesOnline = mergedSites.filter(s => s.website.health_status === 'healthy' || s.website.health_status === 'warning').length;
  const sitesOffline = mergedSites.filter(s => s.website.health_status === 'critical').length;
  const activeConfigs = mergedSites.filter(s => s.config?.enabled).length;

  if (isLoading && mergedSites.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            {t('monitoring.title', 'Surveillance')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {t('monitoring.subtitle', 'Surveillez l\'état de vos sites en temps réel')}
          </p>
        </div>
        <button 
          onClick={fetchData}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors shadow-sm font-medium text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('monitoring.refresh', 'Actualiser')}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center justify-between">
          <div className="flex items-center gap-3 text-red-700">
            <AlertCircle className="w-5 h-5" />
            <p className="font-medium">{error}</p>
          </div>
          <button onClick={fetchData} className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm font-bold hover:bg-red-200">
            {t('common.retry', 'Réessayer')}
          </button>
        </div>
      )}

      {/* KPIs */}
      {mergedSites.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-500">{t('monitoring.total_sites', 'Total Sites')}</h3>
              <Globe className="w-5 h-5 text-indigo-500" />
            </div>
            <p className="text-3xl font-black text-slate-900">{totalSites}</p>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-500">{t('monitoring.sites_online', 'En ligne')}</h3>
              <Activity className="w-5 h-5 text-emerald-500" />
            </div>
            <p className="text-3xl font-black text-slate-900">{sitesOnline}</p>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-500">{t('monitoring.sites_offline', 'Hors ligne')}</h3>
              <AlertCircle className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-3xl font-black text-slate-900">{sitesOffline}</p>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-500">{t('monitoring.active_monitors', 'Surveillances Actives')}</h3>
              <Clock className="w-5 h-5 text-indigo-500" />
            </div>
            <p className="text-3xl font-black text-slate-900">{activeConfigs}</p>
          </div>
        </div>
      )}

      {mergedSites.length === 0 && !isLoading && !error && (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center shadow-sm">
          <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Activity className="w-8 h-8 text-indigo-600" />
          </div>
          <h3 className="text-xl font-bold text-slate-900 mb-2">
            {t('monitoring.empty.title', 'Aucun site à surveiller')}
          </h3>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            {t('monitoring.empty.subtitle', 'Ajoutez votre premier site web pour commencer à surveiller sa disponibilité et ses performances.')}
          </p>
          <Link
            to={`/${lang}/app/websites/new`}
            className="inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-6 py-3 font-bold transition-colors"
          >
            <Plus className="w-5 h-5" />
            {t('monitoring.add_first_site', 'Ajouter un site')}
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {mergedSites.map(({ website, config }) => {
          const isOnline = website.health_status === 'healthy' || website.health_status === 'warning';
          const isOffline = website.health_status === 'critical';
          const isUnknown = website.health_status === 'neutral' || !config;
          const statusColor = isOnline ? 'text-emerald-500 bg-emerald-50 border-emerald-200' : isOffline ? 'text-red-500 bg-red-50 border-red-200' : 'text-slate-500 bg-slate-50 border-slate-200';
          const dotColor = isOnline ? 'bg-emerald-500' : isOffline ? 'bg-red-500' : 'bg-slate-500';

          return (
            <div key={website.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
              <div className="p-6 flex-1">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">{website.display_name}</h3>
                    <p className="text-sm text-slate-500">{website.domain}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-full border text-xs font-bold flex items-center gap-2 ${statusColor}`}>
                    <span className="relative flex h-2 w-2">
                      {isOnline && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                      <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`}></span>
                    </span>
                    {isOnline ? t('monitoring.status.online', 'En ligne') : isOffline ? t('monitoring.status.offline', 'Hors ligne') : t('monitoring.status.unknown', 'Inconnu')}
                  </div>
                </div>

                {config ? (
                  <div className="grid grid-cols-2 gap-y-4 gap-x-6 mt-6">
                    <div>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">{t('monitoring.interval', 'Intervalle')}</p>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                        {config.interval}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">{t('monitoring.failures', 'Échecs consécutifs')}</p>
                      <span className={`text-sm font-bold ${config.consecutive_failures > 0 ? 'text-red-600' : 'text-slate-700'}`}>
                        {config.consecutive_failures}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">{t('monitoring.last_scan', 'Dernier scan')}</p>
                      <p className="text-sm text-slate-700 font-medium">{formatDate(config.last_scan_at)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">{t('monitoring.next_scan', 'Prochain scan')}</p>
                      <p className="text-sm text-slate-700 font-medium">{formatDate(config.next_scan_at)}</p>
                    </div>
                  </div>
                ) : (
                  <div className="mt-6 p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <p className="text-sm text-slate-500">{t('monitoring.no_config', 'Aucune configuration de surveillance')}</p>
                  </div>
                )}
              </div>
              
              <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
                <button
                  onClick={() => handleToggleMonitoring(website.id, config?.enabled ?? false)}
                  disabled={!config || isToggling[website.id]}
                  className={`inline-flex items-center gap-2 text-sm font-bold transition-colors ${
                    !config ? 'text-slate-400 cursor-not-allowed' :
                    config.enabled ? 'text-amber-600 hover:text-amber-700' : 'text-emerald-600 hover:text-emerald-700'
                  }`}
                >
                  {isToggling[website.id] ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Power className="w-4 h-4" />
                  )}
                  {config?.enabled ? t('monitoring.disabled', 'Désactiver') : t('monitoring.enabled', 'Activer')}
                </button>
                
                <button
                  onClick={() => handleScanNow(website.id)}
                  disabled={isScanning[website.id]}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-bold transition-colors disabled:opacity-50"
                >
                  {isScanning[website.id] ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {t('monitoring.trigger_scan', 'Scanner maintenant')}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Monitoring;
