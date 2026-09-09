import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle,
  Play,
  Bug,
  Server,
  Ban
} from 'lucide-react';
import { format } from 'date-fns';

interface Website {
  id: string;
  domain: string;
  display_name: string;
}

interface Incident {
  id: string;
  incident_type: 'malware' | 'open_port' | 'waf_missing' | 'vulnerability';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  evidence: any;
  is_resolved: boolean;
  detected_at: string;
}

export const SecurityPage: React.FC = () => {
  const { lang } = useParams<{ lang: string }>();
  const { t } = useTranslation();
  const { user } = useAuth();

  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>('');
  
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loadingWebsites, setLoadingWebsites] = useState(true);
  const [loadingIncidents, setLoadingIncidents] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const fetchWebsites = useCallback(async () => {
    try {
      setLoadingWebsites(true);
      const res = await api.get('/websites/');
      const data = res.data.results || res.data;
      setWebsites(data);
      if (data.length > 0) {
        setSelectedWebsiteId(data[0].id);
      }
    } catch (err) {
      console.error(err);
      setError(t('security.errors.load_failed', 'Failed to fetch websites'));
    } finally {
      setLoadingWebsites(false);
    }
  }, [t]);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

  const fetchIncidents = useCallback(async (websiteId: string) => {
    try {
      setLoadingIncidents(true);
      setError(null);
      const res = await api.get(`/websites/${websiteId}/security/incidents/`);
      const data = res.data.results || res.data;
      setIncidents(data);
    } catch (err) {
      console.error(err);
      setError(t('security.errors.load_failed', 'Failed to fetch security incidents'));
    } finally {
      setLoadingIncidents(false);
    }
  }, [t]);

  useEffect(() => {
    if (selectedWebsiteId) {
      fetchIncidents(selectedWebsiteId);
    }
  }, [selectedWebsiteId, fetchIncidents]);

  const handleScan = async () => {
    if (!selectedWebsiteId) return;
    try {
      setScanning(true);
      await api.post(`/websites/${selectedWebsiteId}/security/scan/`);
      alert(t('security.scan_init', 'Security scan started. This may take a few minutes.'));
      // optionally refetch after a delay
      setTimeout(() => fetchIncidents(selectedWebsiteId), 5000);
    } catch (err) {
      console.error(err);
      alert(t('security.errors.scan_failed', 'Failed to start scan'));
    } finally {
      setScanning(false);
    }
  };

  const filteredIncidents = useMemo(() => {
    return incidents.filter(i => {
      const matchSeverity = filterSeverity === 'all' || i.severity === filterSeverity;
      let matchStatus = true;
      if (filterStatus === 'open') matchStatus = !i.is_resolved;
      if (filterStatus === 'resolved') matchStatus = i.is_resolved;
      return matchSeverity && matchStatus;
    });
  }, [incidents, filterSeverity, filterStatus]);

  const kpis = useMemo(() => {
    const total = incidents.length;
    const resolved = incidents.filter(i => i.is_resolved).length;
    const open = total - resolved;
    const critical = incidents.filter(i => i.severity === 'critical' && !i.is_resolved).length;
    return { total, resolved, open, critical };
  }, [incidents]);

  const getSeverityColor = (severity: string) => {
    switch(severity) {
      case 'low': return 'text-emerald-700 bg-emerald-100 ring-emerald-600/20';
      case 'medium': return 'text-amber-700 bg-amber-100 ring-amber-600/20';
      case 'high': return 'text-red-700 bg-red-100 ring-red-600/20';
      case 'critical': return 'text-rose-900 bg-rose-100 ring-rose-900/20 font-black';
      default: return 'text-slate-700 bg-slate-100 ring-slate-600/20';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'malware': return <Bug className="w-5 h-5" />;
      case 'open_port': return <Server className="w-5 h-5" />;
      case 'waf_missing': return <ShieldAlert className="w-5 h-5" />;
      case 'vulnerability': return <AlertTriangle className="w-5 h-5" />;
      default: return <Ban className="w-5 h-5" />;
    }
  };

  if (loadingWebsites) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            {t('security.title', 'Security Center')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {t('security.subtitle', 'Monitor and manage security incidents across your properties.')}
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          <select
            value={selectedWebsiteId}
            onChange={(e) => setSelectedWebsiteId(e.target.value)}
            className="block w-48 rounded-xl border-0 py-2 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6 bg-white shadow-sm"
          >
            {websites.map(w => (
              <option key={w.id} value={w.id}>{w.display_name || w.domain}</option>
            ))}
          </select>
          <button
            onClick={handleScan}
            disabled={scanning || !selectedWebsiteId}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-4 py-2 rounded-xl font-bold transition-colors shadow-sm"
          >
            {scanning ? (
              <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
            ) : (
              <Play className="h-5 w-5" />
            )}
            {t('security.scan_now', 'Run Scan')}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-xl text-sm border border-red-100 flex items-center gap-3 shadow-sm">
          <AlertTriangle className="h-5 w-5 text-red-400" />
          {error}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col">
          <span className="text-sm font-medium text-slate-500">{t('security.kpi_total', 'Total Incidents')}</span>
          <span className="text-3xl font-black text-slate-900 mt-2">{kpis.total}</span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col">
          <span className="text-sm font-medium text-slate-500">{t('security.kpi_open', 'Open Issues')}</span>
          <span className="text-3xl font-black text-slate-900 mt-2">{kpis.open}</span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col">
          <span className="text-sm font-medium text-slate-500">{t('security.kpi_resolved', 'Resolved')}</span>
          <span className="text-3xl font-black text-emerald-600 mt-2">{kpis.resolved}</span>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col">
          <span className="text-sm font-medium text-slate-500">{t('security.kpi_critical', 'Critical Threats')}</span>
          <span className="text-3xl font-black text-rose-600 mt-2">{kpis.critical}</span>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-4 justify-between items-center bg-slate-50/50">
          <h2 className="text-lg font-bold text-slate-800">
            {t('security.incidents_list', 'Incident Log')}
          </h2>
          <div className="flex gap-2">
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="text-sm rounded-lg border-slate-200 py-1.5 pl-3 pr-8 shadow-sm focus:ring-indigo-600"
            >
              <option value="all">{t('security.filter_severity_all', 'All Severities')}</option>
              <option value="critical">{t('security.severity.critical', 'Critical')}</option>
              <option value="high">{t('security.severity.high', 'High')}</option>
              <option value="medium">{t('security.severity.medium', 'Medium')}</option>
              <option value="low">{t('security.severity.low', 'Low')}</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="text-sm rounded-lg border-slate-200 py-1.5 pl-3 pr-8 shadow-sm focus:ring-indigo-600"
            >
              <option value="all">{t('security.filter_status_all', 'All Statuses')}</option>
              <option value="open">{t('security.filter_status_open', 'Open')}</option>
              <option value="resolved">{t('security.filter_status_resolved', 'Resolved')}</option>
            </select>
          </div>
        </div>

        {loadingIncidents ? (
          <div className="p-12 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="p-12 text-center flex flex-col items-center">
            <div className="h-16 w-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mb-4">
              <ShieldCheck className="h-8 w-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">{t('security.empty_title', 'Your site is secure!')}</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-sm">
              {t('security.empty_desc', 'We didn\'t find any security incidents matching your criteria. Great job keeping your site safe.')}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {filteredIncidents.map(incident => (
              <li key={incident.id} className="p-4 hover:bg-slate-50 transition-colors">
                <div className="flex items-start gap-4">
                  <div className={`mt-1 flex-shrink-0 p-2 rounded-xl ${
                    incident.is_resolved ? 'bg-slate-100 text-slate-400' : 
                    incident.severity === 'critical' ? 'bg-rose-100 text-rose-600' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {getTypeIcon(incident.incident_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className={`text-base font-bold truncate ${incident.is_resolved ? 'text-slate-500 line-through' : 'text-slate-900'}`}>
                        {incident.title}
                      </h4>
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getSeverityColor(incident.severity)}`}>
                        {incident.severity.toUpperCase()}
                      </span>
                      {incident.is_resolved && (
                        <span className="inline-flex items-center rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          {t('security.resolved', 'Resolved')}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-600 mb-2 line-clamp-2">
                      {incident.description}
                    </p>
                    <div className="text-xs text-slate-400 flex items-center gap-2">
                      <span>{t('security.detected', 'Detected:')} {format(new Date(incident.detected_at), 'PPP p')}</span>
                      <span>&bull;</span>
                      <span className="uppercase tracking-wider">{incident.incident_type.replace('_', ' ')}</span>
                    </div>
                  </div>
                  {!incident.is_resolved && (
                    <div className="flex-shrink-0">
                      <button className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
                        {t('security.view_details', 'View')}
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default SecurityPage;
