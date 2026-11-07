import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { UpgradeBanner } from '../components/UpgradeBanner';
import { ActionRequired } from '../components/ActionRequired';
import { RemediationBlock } from '../components/RemediationBlock';
import { REMEDIATION_GUIDES } from '../types/remediation';
import { WhiteLabelReport } from '../components/WhiteLabelReport';
import { Clock, RefreshCw, ChevronDown } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface CheckItem {
  category: string;
  status: 'healthy' | 'warning' | 'critical' | 'neutral';
  score: number | null;
  max_score: number | null;
  summary: string;
  recommendation?: string;
  technical_details?: Record<string, any>;
}

interface WebsiteData {
  id: number;
  domain: string;
  display_name: string;
  is_active: boolean;
  health_score: number | null;
  health_status: string | null;
  last_scan_id: number | null;
  last_scan_status: string | null;
  checks: CheckItem[];
  created_at: string;
  last_scan_at: string | null;
}

interface MonitoringConfig {
  id: number;
  website: number;
  enabled: boolean;
  interval: string;
  last_scan_at: string | null;
  next_scan_at: string | null;
  consecutive_failures: number;
  escalation_level: number;
}

// Intervalles disponibles
const INTERVALS = [
  { value: '5m', label: '5 minutes' },
  { value: '15m', label: '15 minutes' },
  { value: '30m', label: '30 minutes' },
  { value: '1h', label: '1 heure' },
  { value: '6h', label: '6 heures' },
  { value: '24h', label: '24 heures' },
];

// Traductions des intervalles
const INTERVAL_LABELS = {
  fr: {
    '5m': '5 minutes',
    '15m': '15 minutes',
    '30m': '30 minutes',
    '1h': '1 heure',
    '6h': '6 heures',
    '24h': '24 heures',
  },
  en: {
    '5m': '5 minutes',
    '15m': '15 minutes',
    '30m': '30 minutes',
    '1h': '1 hour',
    '6h': '6 hours',
    '24h': '24 hours',
  },
  de: {
    '5m': '5 Minuten',
    '15m': '15 Minuten',
    '30m': '30 Minuten',
    '1h': '1 Stunde',
    '6h': '6 Stunden',
    '24h': '24 Stunden',
  },
};

export function WebsiteDetails() {
  const { t, i18n } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const { user, plan } = useAuth();
  const [website, setWebsite] = useState<WebsiteData | null>(null);
  const [monitoring, setMonitoring] = useState<MonitoringConfig | null>(null);
  const [activeTab, setActiveTab] = useState<'health' | 'reports' | 'security' | 'seo'>('health');
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [updatingInterval, setUpdatingInterval] = useState(false);
  const [scanFeedback, setScanFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showIntervalDropdown, setShowIntervalDropdown] = useState(false);

  const currentLang = (i18n.language || 'fr').split('-')[0].toLowerCase() as 'fr' | 'en' | 'de';
  const intervalLabels = INTERVAL_LABELS[currentLang] || INTERVAL_LABELS.fr;

  const fetchWebsiteData = async () => {
    setLoading(true);
    setError(null);
    const token = localStorage.getItem('access_token');

    try {
      // Récupérer les données du site
      const siteRes = await api.get(`/websites/${id}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setWebsite(siteRes.data);

      // Récupérer la configuration de monitoring
      try {
        const monitorRes = await api.get(`/monitoring/websites/${id}/`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setMonitoring(monitorRes.data);
      } catch {
        // Pas de config de monitoring, utiliser les valeurs par défaut
        setMonitoring({
          id: 0,
          website: Number(id),
          enabled: true,
          interval: '24h',
          last_scan_at: null,
          next_scan_at: null,
          consecutive_failures: 0,
          escalation_level: 0,
        });
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError(t('websites.errors.unauthorized'));
      } else if (err.response?.status === 404) {
        setError(t('websites.errors.not_found'));
      } else {
        setError(t('websites.errors.load_failed'));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchWebsiteData();
  }, [id]);

  const handleTriggerScan = async () => {
    setScanning(true);
    setScanFeedback(null);
    const token = localStorage.getItem('access_token');
    try {
      await api.post(
        `/websites/${id}/scan/`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      setScanFeedback({ type: 'success', message: t('websites.scan_success') });
      setTimeout(() => {
        setScanFeedback(null);
        fetchWebsiteData();
      }, 3000);
    } catch (err: any) {
      setScanFeedback({
        type: 'error',
        message: err.response?.data?.detail || t('websites.errors.scan_failed'),
      });
      setTimeout(() => setScanFeedback(null), 5000);
    } finally {
      setScanning(false);
    }
  };

  const handleUpdateInterval = async (newInterval: string) => {
    if (!monitoring) return;
    setUpdatingInterval(true);
    setError(null);
    const token = localStorage.getItem('access_token');

    try {
      const payload = {
        ...monitoring,
        interval: newInterval,
      };

      if (monitoring.id === 0) {
        // Créer une nouvelle config
        const res = await api.post(
          '/monitoring/',
          {
            website: Number(id),
            enabled: true,
            interval: newInterval,
          },
          { headers: token ? { Authorization: `Bearer ${token}` } : {} }
        );
        setMonitoring(res.data);
      } else {
        // Mettre à jour la config existante
        const res = await api.put(
          `/monitoring/websites/${id}/`,
          payload,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} }
        );
        setMonitoring(res.data);
      }

      setShowIntervalDropdown(false);
      setScanFeedback({ type: 'success', message: t('websites.interval_updated') });
      setTimeout(() => setScanFeedback(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('websites.errors.interval_update_failed'));
    } finally {
      setUpdatingInterval(false);
    }
  };

  const getStatusIcon = (status: string) => {
    const icons: Record<string, string> = {
      healthy: '✅',
      warning: '⚠️',
      critical: '❌',
      neutral: '⚪',
    };
    return icons[status] || icons.neutral;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      healthy: 'bg-emerald-500',
      warning: 'bg-amber-500',
      critical: 'bg-red-500',
      neutral: 'bg-gray-400',
    };
    return colors[status] || colors.neutral;
  };

  const getStatusBadgeColor = (status: string) => {
    const colors: Record<string, string> = {
      healthy: 'bg-emerald-100 text-emerald-700 border-emerald-200',
      warning: 'bg-amber-100 text-amber-700 border-amber-200',
      critical: 'bg-red-100 text-red-700 border-red-200',
      neutral: 'bg-gray-100 text-gray-500 border-gray-200',
    };
    return colors[status] || colors.neutral;
  };

  const isProFeature = (category: string) => {
    return ['security_headers', 'reviews', 'seo'].includes(category);
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-sm text-slate-500 font-medium">{t('common.loading')}</p>
      </div>
    );
  }

  if (error || !website) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <h3 className="text-lg font-bold text-red-700">{t('websites.error_title')}</h3>
        <p className="mt-2 text-sm text-red-600">{error || t('websites.not_found')}</p>
        <div className="mt-4 flex justify-center gap-3">
          <Link to="/app/websites" className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-700 border border-slate-300 hover:bg-slate-50">
            {t('websites.back')}
          </Link>
          <button onClick={fetchWebsiteData} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
            {t('common.retry')}
          </button>
        </div>
      </div>
    );
  }

  const score = website.health_score ?? 0;
  const scoreBadgeColor =
    score >= 80
      ? 'text-emerald-700 bg-emerald-50 border-emerald-300 ring-emerald-100'
      : score >= 50
        ? 'text-amber-700 bg-amber-50 border-amber-300 ring-amber-100'
        : 'text-red-700 bg-red-50 border-red-300 ring-red-100';

  const tabs = [
    { id: 'health', label: t('websites.health_tab', 'Santé'), icon: '🛡️' },
    { id: 'reports', label: t('websites.reports_tab', 'Rapports'), icon: '📄' },
    { id: 'security', label: t('websites.security_tab', 'Sécurité'), icon: '🔒' },
    { id: 'seo', label: t('websites.seo_tab', 'SEO'), icon: '🔍' },
    { id: 'verification', label: t('websites.verification_tab', 'Vérification'), icon: '🔑' },
  ];

  const currentInterval = monitoring?.interval || '24h';

  return (
    <div className="space-y-6">
      {/* Scan Feedback Toast */}
      {scanFeedback && (
        <div className={`fixed bottom-4 right-4 z-50 px-6 py-3 rounded-xl shadow-lg animate-slide-up ${
          scanFeedback.type === 'success'
            ? 'bg-emerald-600 text-white'
            : 'bg-red-600 text-white'
        }`}>
          {scanFeedback.message}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/app/websites" className="text-sm font-medium text-slate-500 hover:text-slate-800">
              ← {t('websites.back')}
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">{website.display_name || website.domain}</h1>
          <a
            href={`https://${website.domain}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            https://{website.domain} ↗
          </a>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* 🔥 NOUVEAU: Sélecteur d'intervalle de monitoring */}
          <div className="relative">
            <button
              onClick={() => setShowIntervalDropdown(!showIntervalDropdown)}
              disabled={updatingInterval}
              className="flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <Clock size={16} className="text-slate-500" />
              <span>{intervalLabels[currentInterval as keyof typeof intervalLabels] || currentInterval}</span>
              <ChevronDown size={14} className={`transition-transform ${showIntervalDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showIntervalDropdown && (
              <div className="absolute right-0 mt-2 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                {INTERVALS.map((interval) => (
                  <button
                    key={interval.value}
                    onClick={() => handleUpdateInterval(interval.value)}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-indigo-50 transition ${
                      currentInterval === interval.value
                        ? 'bg-indigo-50 text-indigo-600 font-semibold'
                        : 'text-slate-700'
                    }`}
                  >
                    {intervalLabels[interval.value as keyof typeof intervalLabels] || interval.label}
                    {currentInterval === interval.value && (
                      <span className="ml-2 text-indigo-600">✓</span>
                    )}
                  </button>
                ))}
                <div className="border-t border-slate-100 mt-1 pt-1">
                  <div className="px-4 py-1.5 text-[10px] text-slate-400">
                    {t('websites.monitoring_interval_hint')}
                  </div>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleTriggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 active:scale-95 disabled:opacity-50"
          >
            <RefreshCw size={16} className={scanning ? 'animate-spin text-indigo-600' : 'text-slate-500'} />
            {scanning ? t('websites.scanning') : t('websites.scan_now')}
          </button>

          <div className={`flex items-center gap-3 rounded-2xl border px-4 py-2 ring-4 ${scoreBadgeColor}`}>
            <div className="text-center">
              <span className="text-2xl font-black">{website.health_score !== null ? website.health_score : '--'}</span>
              <span className="text-xs font-semibold">/100</span>
            </div>
            <span className="text-xs font-bold uppercase tracking-wider">{t('websites.score')}</span>
          </div>
        </div>
      </div>

      {/* Monitoring Info */}
      {monitoring && (
        <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
              <Clock size={16} />
              {t('websites.monitoring_interval')}: <strong>{intervalLabels[currentInterval as keyof typeof intervalLabels] || currentInterval}</strong>
            </span>
            {monitoring.next_scan_at && (
              <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                📅 {t('websites.next_scan')}: {new Date(monitoring.next_scan_at).toLocaleString()}
              </span>
            )}
            {monitoring.enabled ? (
              <span className="text-emerald-600 dark:text-emerald-400">✅ {t('websites.monitoring_enabled')}</span>
            ) : (
              <span className="text-red-600 dark:text-red-400">❌ {t('websites.monitoring_disabled')}</span>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {tab.icon} {tab.label} {tab.id === 'health' && `(${website.checks.length})`}
          </button>
        ))}
      </div>

      {/* Tab Health */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          {website.checks.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
              <div className="text-4xl mb-3">📊</div>
              <p className="text-slate-500">{t('websites.no_scans')}</p>
              <button
                onClick={handleTriggerScan}
                disabled={scanning}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {scanning ? t('websites.scanning') : t('websites.first_scan')}
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-900">{t('websites.checks_title')}</h3>
                <span className="text-xs text-slate-400 cursor-help" title={t('websites.score_explanation')}>
                  ℹ️ {t('websites.score_legend')}
                </span>
              </div>

              <div className="space-y-4">
                {website.checks.map((check) => {
                  const categoryKey = check.category.replace(/_/g, '_');
                  const proFeature = isProFeature(check.category);

                  return (
                    <div key={check.category} className={`rounded-xl border p-4 transition ${
                      check.status === 'healthy'
                        ? 'border-emerald-200 bg-emerald-50/50'
                        : check.status === 'warning'
                        ? 'border-amber-200 bg-amber-50/50'
                        : 'border-red-200 bg-red-50/50'
                    } hover:border-indigo-200`}>
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-3">
                          <span className={`h-3 w-3 rounded-full ${getStatusColor(check.status)}`} />
                          <span className="font-semibold text-slate-900 text-sm">
                            {t(`checks.${categoryKey}`) || check.category}
                          </span>
                          <span className="text-sm">
                            {getStatusIcon(check.status)}
                          </span>
                          {proFeature && (
                            <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">
                              🔒 Pro
                            </span>
                          )}
                        </div>
                        {check.score !== null && (
                          <span className={`text-xs font-bold px-2 py-1 rounded-md ${getStatusBadgeColor(check.status)}`}>
                            {`${check.score}${typeof check.max_score === 'number' ? `/${check.max_score}` : ''}`}
                          </span>
                        )}
                      </div>

                      <p className="mt-2 text-sm text-slate-700 ml-3">{check.summary}</p>

                      {check.recommendation && (
                        <p className="mt-1 text-sm text-indigo-600 ml-3">
                          💡 {check.recommendation}
                        </p>
                      )}

                      {/* Pro Feature Upgrade CTA */}
                      {proFeature && check.status !== 'healthy' && (
                        <div className="mt-3 ml-3">
                          <div className="p-3 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg">
                            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                              <span className="text-sm text-indigo-700 dark:text-indigo-300">
                                {t('websites.pro_feature', { feature: t(`checks.${categoryKey}`) })}
                              </span>
                              <Link
                                to="/pricing"
                                className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 whitespace-nowrap"
                              >
                                {t('plan.upgrade')} →
                              </Link>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Remediation Guides */}
                      {check.category === 'email_security' && check.status !== 'healthy' && (
                        <RemediationBlock guide={REMEDIATION_GUIDES.spf_missing} />
                      )}
                      {check.category === 'security_headers' && check.status !== 'healthy' && (
                        <RemediationBlock guide={REMEDIATION_GUIDES.security_headers_missing} />
                      )}
                      {check.category === 'ssl' && check.status !== 'healthy' && (
                        <RemediationBlock guide={REMEDIATION_GUIDES.ssl_expiring_soon} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab Reports */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <WhiteLabelReport
            scanId={String(website.last_scan_id || '')}
            domain={website.domain}
          />
        </div>
      )}

      {/* Tab Security */}
      {activeTab === 'security' && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900">{t('websites.security_title')}</h3>
          <p className="text-sm text-slate-600 mt-2">
            {t('websites.security_desc', { domain: website.domain })}
          </p>
        </div>
      )}

      {/* Tab SEO */}
      {activeTab === 'seo' && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900">{t('websites.seo_title', 'SEO')}</h3>
          <p className="text-sm text-slate-600 mt-2">
            {t('websites.seo_desc', 'Detailed SEO analysis for {{domain}}', { domain: website.domain })}
          </p>
        </div>
      )}

      {/* Tab Verification */}
      {activeTab === 'verification' && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900 mb-2">{t('websites.verification.title', 'Vérification de propriété')}</h3>
            <p className="text-sm text-slate-600 mb-6">{t('websites.verification.desc', 'Prouvez que vous êtes le propriétaire de ce domaine en utilisant l\'une des méthodes ci-dessous.')}</p>
            
            <div className="space-y-6">
              {/* Méthode 1: DNS */}
              <div className="border border-slate-200 rounded-xl p-5">
                <h4 className="font-bold text-slate-900 flex items-center gap-2 mb-3">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs">1</span>
                  {t('websites.verification.method1', 'Méthode 1 : Enregistrement DNS (Recommandé)')}
                </h4>
                <p className="text-sm text-slate-600 mb-4">{t('websites.verification.method1_desc', 'Ajoutez l\'enregistrement TXT suivant à la configuration DNS de votre domaine.')}</p>
                
                <div className="bg-slate-50 p-4 rounded-lg font-mono text-sm border border-slate-200 mb-4 break-all">
                  <span className="text-slate-400 select-none">{t('websites.verification.method1_type', 'Type: TXT | Nom: @ | Valeur: ')}</span>
                  <span className="text-indigo-600 font-semibold">presence-site-verification={website.id}-fake-token-abcd</span>
                </div>
                
                <button 
                  onClick={() => {
                    alert(t('websites.verification.in_dev', 'Verification en cours de développement...'));
                  }}
                  className="bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-slate-50 transition"
                >
                  {t('websites.verification.method1_btn', 'Vérifier l\'enregistrement DNS')}
                </button>
              </div>

              {/* Méthode 2: Meta Tag */}
              <div className="border border-slate-200 rounded-xl p-5">
                <h4 className="font-bold text-slate-900 flex items-center gap-2 mb-3">
                  <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center text-xs">2</span>
                  {t('websites.verification.method2', 'Méthode 2 : Balise Meta')}
                </h4>
                <p className="text-sm text-slate-600 mb-4">{t('websites.verification.method2_desc', 'Ajoutez cette balise meta dans la section <head> de votre page d\'accueil.')}</p>
                
                <div className="bg-slate-50 p-4 rounded-lg font-mono text-sm border border-slate-200 mb-4 break-all">
                  &lt;meta name="presence-site-verification" content="{website.id}-fake-token-abcd" /&gt;
                </div>
                
                <button 
                  onClick={() => {
                    alert(t('websites.verification.in_dev', 'Verification en cours de développement...'));
                  }}
                  className="bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-slate-50 transition"
                >
                  {t('websites.verification.method2_btn', 'Vérifier la balise Meta')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default WebsiteDetails;
