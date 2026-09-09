import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import { 
  Bell, AlertTriangle, Settings, RefreshCw, X, Save, 
  Plus, Trash2, Edit, Moon, Calendar, Clock,
  Mail, Send, MessageCircle, Globe
} from 'lucide-react';

interface Alert {
  id: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  status: 'firing' | 'acknowledged' | 'resolved';
  title: string;
  message: string;
  website: { id: number; domain: string; display_name: string } | null;
  created_at: string;
}

interface AlertPreference {
  ssl_expiring_enabled: boolean;
  ssl_invalid_enabled: boolean;
  website_offline_enabled: boolean;
  dns_problem_enabled: boolean;
  email_security_enabled: boolean;
  security_headers_enabled: boolean;
  performance_enabled: boolean;
  score_drop_enabled: boolean;
  scan_failed_enabled: boolean;
  ssl_expiry_warning_days: number;
  score_drop_threshold: number;
  digest_frequency: 'immediate' | 'hourly' | 'daily';
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}

interface MuteWindow {
  id: number;
  start_at: string;
  end_at: string;
  reason: 'maintenance' | 'deployment' | 'migration' | 'other';
  note: string;
  is_active: boolean;
  websites: { id: number; domain: string }[];
}

interface NotificationChannel {
  id: number;
  name: string;
  channel_type: 'email' | 'slack' | 'discord' | 'webhook';
  enabled: boolean;
  config: Record<string, any>;
  severities: string[];
  alert_types: string[];
}

interface AlertRule {
  id: number;
  name: string;
  metric: 'health_score' | 'ssl_days_remaining' | 'load_time_ms' | 'page_size_kb';
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'eq';
  threshold: number;
  severity: 'warning' | 'critical';
  enabled: boolean;
  cooldown_minutes: number;
  website: { id: number; domain: string } | null;
}

const ALERT_TYPES = [
  { key: 'ssl_expiring_enabled', icon: '🔒', label: 'SSL expire bientôt' },
  { key: 'ssl_invalid_enabled', icon: '❌', label: 'SSL invalide' },
  { key: 'website_offline_enabled', icon: '🌐', label: 'Site hors ligne' },
  { key: 'dns_problem_enabled', icon: '🌍', label: 'Problème DNS' },
  { key: 'email_security_enabled', icon: '📧', label: 'Sécurité email' },
  { key: 'security_headers_enabled', icon: '🛡️', label: 'En-têtes de sécurité' },
  { key: 'performance_enabled', icon: '⚡', label: 'Performance' },
  { key: 'score_drop_enabled', icon: '📉', label: 'Baisse de score' },
  { key: 'scan_failed_enabled', icon: '❌', label: 'Échec du scan' },
];

const REASONS = [
  { value: 'maintenance', label: 'Maintenance planifiée' },
  { value: 'deployment', label: 'Déploiement' },
  { value: 'migration', label: 'Migration' },
  { value: 'other', label: 'Autre' },
];

const DIGEST_FREQUENCIES = [
  { value: 'immediate', label: 'Immédiat' },
  { value: 'hourly', label: 'Toutes les heures' },
  { value: 'daily', label: 'Quotidien' },
];

const CHANNEL_TYPES = [
  { value: 'email', icon: '📧', label: 'Email', description: 'Recevez les alertes par email' },
  { value: 'slack', icon: '💬', label: 'Slack', description: 'Recevez les alertes sur Slack' },
  { value: 'discord', icon: '🎮', label: 'Discord', description: 'Recevez les alertes sur Discord' },
  { value: 'webhook', icon: '🌐', label: 'Webhook', description: 'Recevez les alertes via un webhook personnalisé' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: 'ℹ️ Info' },
  { value: 'warning', label: '⚠️ Warning' },
  { value: 'critical', label: '🔴 Critical' },
];

const RULE_METRICS = [
  { value: 'health_score', label: 'Score de santé' },
  { value: 'ssl_days_remaining', label: 'Jours SSL restants' },
  { value: 'load_time_ms', label: 'Temps de charge (ms)' },
  { value: 'page_size_kb', label: 'Taille de la page (KB)' },
];

const RULE_OPERATORS = [
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'gte', label: '>=' },
  { value: 'lte', label: '<=' },
  { value: 'eq', label: '=' },
];

export function Alerts() {
  const { t, i18n } = useTranslation();
  const { lang } = useParams<{ lang?: string }>();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [preferences, setPreferences] = useState<AlertPreference | null>(null);
  const [muteWindows, setMuteWindows] = useState<MuteWindow[]>([]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [websites, setWebsites] = useState<{ id: number; domain: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<'all' | 'firing' | 'acknowledged' | 'resolved'>('all');
  const [showPreferences, setShowPreferences] = useState(false);
  const [showMuteForm, setShowMuteForm] = useState(false);
  const [showChannelForm, setShowChannelForm] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingMute, setEditingMute] = useState<MuteWindow | null>(null);
  const [editingChannel, setEditingChannel] = useState<NotificationChannel | null>(null);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [muteForm, setMuteForm] = useState({
    start_at: '',
    end_at: '',
    reason: 'maintenance' as const,
    note: '',
    websites: [] as number[],
  });
  const [channelForm, setChannelForm] = useState({
    name: '',
    channel_type: 'email' as NotificationChannel['channel_type'],
    enabled: true,
    config: {} as Record<string, any>,
    severities: ['info', 'warning', 'critical'] as string[],
    alert_types: [] as string[],
  });
  const [ruleForm, setRuleForm] = useState({
    name: '',
    metric: 'health_score' as AlertRule['metric'],
    operator: 'lt' as AlertRule['operator'],
    threshold: 80,
    severity: 'warning' as AlertRule['severity'],
    enabled: true,
    cooldown_minutes: 60,
    website_id: '' as string | number,
  });

  const currentLang = lang || i18n.language || 'fr';

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      const token = localStorage.getItem('access_token');

      try {
        // Alertes
        const alertsRes = await api.get('/alerts/', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = alertsRes.data?.results || alertsRes.data || [];
        setAlerts(Array.isArray(data) ? data : []);

        // Préférences
        try {
          const prefRes = await api.get('/alerts/preferences/', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          setPreferences(prefRes.data);
        } catch {
          setPreferences({
            ssl_expiring_enabled: true,
            ssl_invalid_enabled: true,
            website_offline_enabled: true,
            dns_problem_enabled: true,
            email_security_enabled: true,
            security_headers_enabled: true,
            performance_enabled: true,
            score_drop_enabled: true,
            scan_failed_enabled: true,
            ssl_expiry_warning_days: 30,
            score_drop_threshold: 10,
            digest_frequency: 'immediate',
            quiet_hours_start: null,
            quiet_hours_end: null,
          });
        }

        // Fenêtres de silence
        try {
          const muteRes = await api.get('/alerts/mute-windows/', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          const muteData = muteRes.data?.results || muteRes.data || [];
          setMuteWindows(Array.isArray(muteData) ? muteData : []);
        } catch {
          setMuteWindows([]);
        }

        // Canaux de notification
        try {
          const channelRes = await api.get('/notifications/channels/', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          const channelData = channelRes.data?.results || channelRes.data || [];
          setChannels(Array.isArray(channelData) ? channelData : []);
        } catch {
          setChannels([]);
        }

        // Règles
        try {
          const ruleRes = await api.get('/alerts/rules/', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          const ruleData = ruleRes.data?.results || ruleRes.data || [];
          setRules(Array.isArray(ruleData) ? ruleData : []);
        } catch {
          setRules([]);
        }

        // Sites
        try {
          const sitesRes = await api.get('/websites/', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          const sitesData = sitesRes.data?.results || sitesRes.data || [];
          setWebsites(Array.isArray(sitesData) ? sitesData.map((s: any) => ({ id: s.id, domain: s.domain })) : []);
        } catch {
          setWebsites([]);
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Erreur de chargement');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSavePreferences = async () => {
    if (!preferences) return;
    setSaving(true);
    const token = localStorage.getItem('access_token');
    try {
      await api.put('/alerts/preferences/', preferences, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSuccess('✅ Préférences sauvegardées');
      setTimeout(() => setSuccess(null), 3000);
      setShowPreferences(false);
    } catch (err) {
      setError('Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleAcknowledge = async (alertId: string) => {
    const token = localStorage.getItem('access_token');
    try {
      await api.post(`/alerts/${alertId}/acknowledge/`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setAlerts(prev => prev.map(a => 
        a.id === alertId ? { ...a, status: 'acknowledged' } : a
      ));
      setSuccess('✅ Alerte acquittée');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Erreur lors de l\'acquittement');
    }
  };

  const handleResolve = async (alertId: string) => {
    const token = localStorage.getItem('access_token');
    try {
      await api.post(`/alerts/${alertId}/resolve/`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setAlerts(prev => prev.map(a => 
        a.id === alertId ? { ...a, status: 'resolved' } : a
      ));
      setSuccess('✅ Alerte résolue');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Erreur lors de la résolution');
    }
  };

  const handleCreateMute = async () => {
    setSaving(true);
    const token = localStorage.getItem('access_token');
    try {
      const payload = {
        ...muteForm,
        websites: muteForm.websites.length > 0 ? muteForm.websites : [],
      };
      
      let res;
      if (editingMute) {
        res = await api.put(`/alerts/mute-windows/${editingMute.id}/`, payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setMuteWindows(muteWindows.map(m => m.id === editingMute.id ? res.data : m));
        setSuccess('✅ Fenêtre de silence mise à jour');
      } else {
        res = await api.post('/alerts/mute-windows/', payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setMuteWindows([...muteWindows, res.data]);
        setSuccess('✅ Fenêtre de silence créée');
      }
      
      setTimeout(() => setSuccess(null), 3000);
      setShowMuteForm(false);
      setEditingMute(null);
      setMuteForm({
        start_at: '',
        end_at: '',
        reason: 'maintenance',
        note: '',
        websites: [],
      });
    } catch (err) {
      setError('Erreur lors de la création de la fenêtre de silence');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteMute = async (muteId: number) => {
    const token = localStorage.getItem('access_token');
    try {
      await api.delete(`/alerts/mute-windows/${muteId}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setMuteWindows(muteWindows.filter(m => m.id !== muteId));
      setSuccess('✅ Fenêtre de silence supprimée');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Erreur lors de la suppression');
    }
  };

  const handleCreateChannel = async () => {
    setSaving(true);
    const token = localStorage.getItem('access_token');
    try {
      const payload = {
        ...channelForm,
        config: channelForm.config,
      };
      
      let res;
      if (editingChannel) {
        res = await api.put(`/notifications/channels/${editingChannel.id}/`, payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setChannels(channels.map(c => c.id === editingChannel.id ? res.data : c));
        setSuccess('✅ Canal de notification mis à jour');
      } else {
        res = await api.post('/notifications/channels/', payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setChannels([...channels, res.data]);
        setSuccess('✅ Canal de notification créé');
      }
      
      setTimeout(() => setSuccess(null), 3000);
      setShowChannelForm(false);
      setEditingChannel(null);
      setChannelForm({
        name: '',
        channel_type: 'email',
        enabled: true,
        config: {},
        severities: ['info', 'warning', 'critical'],
        alert_types: [],
      });
    } catch (err) {
      setError('Erreur lors de la création du canal de notification');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteChannel = async (channelId: number) => {
    const token = localStorage.getItem('access_token');
    try {
      await api.delete(`/notifications/channels/${channelId}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setChannels(channels.filter(c => c.id !== channelId));
      setSuccess('✅ Canal de notification supprimé');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Erreur lors de la suppression');
    }
  };

  const editChannel = (channel: NotificationChannel) => {
    setEditingChannel(channel);
    setChannelForm({
      name: channel.name,
      channel_type: channel.channel_type,
      enabled: channel.enabled,
      config: channel.config || {},
      severities: channel.severities || ['info', 'warning', 'critical'],
      alert_types: channel.alert_types || [],
    });
    setShowChannelForm(true);
  };

  const handleCreateRule = async () => {
    setSaving(true);
    const token = localStorage.getItem('access_token');
    try {
      const payload = {
        ...ruleForm,
        website_id: ruleForm.website_id || null,
      };
      
      let res;
      if (editingRule) {
        res = await api.put(`/alerts/rules/${editingRule.id}/`, payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setRules(rules.map(r => r.id === editingRule.id ? res.data : r));
        setSuccess('✅ Règle mise à jour');
      } else {
        res = await api.post('/alerts/rules/', payload, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setRules([...rules, res.data]);
        setSuccess('✅ Règle créée');
      }
      
      setTimeout(() => setSuccess(null), 3000);
      setShowRuleForm(false);
      setEditingRule(null);
      setRuleForm({
        name: '',
        metric: 'health_score',
        operator: 'lt',
        threshold: 80,
        severity: 'warning',
        enabled: true,
        cooldown_minutes: 60,
        website_id: '',
      });
    } catch (err) {
      setError('Erreur lors de la création de la règle');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    const token = localStorage.getItem('access_token');
    try {
      await api.delete(`/alerts/rules/${ruleId}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setRules(rules.filter(r => r.id !== ruleId));
      setSuccess('✅ Règle supprimée');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Erreur lors de la suppression');
    }
  };

  const editRule = (rule: AlertRule) => {
    setEditingRule(rule);
    setRuleForm({
      name: rule.name,
      metric: rule.metric,
      operator: rule.operator,
      threshold: rule.threshold,
      severity: rule.severity,
      enabled: rule.enabled,
      cooldown_minutes: rule.cooldown_minutes,
      website_id: rule.website ? rule.website.id : '',
    });
    setShowRuleForm(true);
  };

  const handleChannelConfigChange = (key: string, value: any) => {
    setChannelForm({
      ...channelForm,
      config: { ...channelForm.config, [key]: value },
    });
  };

  const editMute = (mute: MuteWindow) => {
    setEditingMute(mute);
    setMuteForm({
      start_at: mute.start_at.slice(0, 16),
      end_at: mute.end_at.slice(0, 16),
      reason: mute.reason,
      note: mute.note,
      websites: mute.websites ? mute.websites.map(w => w.id) : [],
    });
    setShowMuteForm(true);
  };

  const formatDate = (date: string) => {
    return new Date(date).toLocaleString(currentLang === 'fr' ? 'fr-FR' : currentLang === 'de' ? 'de-DE' : 'en-US');
  };

  const getSeverityConfig = (severity: string) => {
    const configs: Record<string, { color: string; icon: string }> = {
      info: { color: 'bg-blue-100 text-blue-700', icon: 'ℹ️' },
      warning: { color: 'bg-yellow-100 text-yellow-700', icon: '⚠️' },
      critical: { color: 'bg-red-100 text-red-700', icon: '🔴' },
    };
    return configs[severity] || configs.info;
  };

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; label: string }> = {
      firing: { color: 'bg-red-100 text-red-700', label: 'Active' },
      acknowledged: { color: 'bg-yellow-100 text-yellow-700', label: 'Acquittée' },
      resolved: { color: 'bg-green-100 text-green-700', label: 'Résolue' },
    };
    return configs[status] || configs.resolved;
  };

  const getTimeAgo = (date: string) => {
    if (!date) return 'N/A';
    const diff = Date.now() - new Date(date).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'À l\'instant';
    if (minutes < 60) return `Il y a ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `Il y a ${hours}h`;
    const days = Math.floor(hours / 24);
    return `Il y a ${days}j`;
  };

  const getChannelTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      email: '📧',
      slack: '💬',
      discord: '🎮',
      webhook: '🌐',
    };
    return icons[type] || '🔔';
  };

  const safeAlerts = Array.isArray(alerts) ? alerts : [];
  const activeAlerts = safeAlerts.filter(a => a.status === 'firing').length;
  const filteredAlerts = safeAlerts.filter(a => {
    if (filterStatus === 'all') return true;
    return a.status === filterStatus;
  });

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent mx-auto" />
          <p className="text-sm text-gray-500 mt-3">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {success && (
        <div className="fixed bottom-4 right-4 z-50 px-6 py-3 rounded-xl shadow-lg bg-emerald-600 text-white animate-slide-up">
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-center gap-2">
          <AlertTriangle size={18} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
            <X size={18} />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Bell className="text-indigo-600" />
            Alertes & Notifications
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Gérez vos alertes, notifications et canaux de communication
            {activeAlerts > 0 && (
              <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                {activeAlerts} alertes actives
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowPreferences(!showPreferences)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-sm font-medium transition"
          >
            <Settings size={16} />
            Préférences
          </button>
          <button
            onClick={() => window.location.reload()}
            className="p-2 bg-gray-100 hover:bg-gray-200 rounded-xl transition"
          >
            <RefreshCw size={18} className="text-gray-500" />
          </button>
        </div>
      </div>

      {/* Préférences */}
      {showPreferences && preferences && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4 animate-in slide-in-from-top duration-300">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">Configuration des alertes</h2>
            <div className="flex gap-2">
              <button onClick={() => setShowPreferences(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-lg transition">
                Annuler
              </button>
              <button onClick={handleSavePreferences} disabled={saving} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center gap-2">
                {saving ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : <Save size={16} />}
                Enregistrer
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {ALERT_TYPES.map(({ key, icon, label }) => (
              <label key={key} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl cursor-pointer hover:bg-gray-100 transition">
                <input
                  type="checkbox"
                  checked={preferences[key as keyof AlertPreference] as boolean}
                  onChange={(e) => setPreferences({ ...preferences, [key]: e.target.checked })}
                  className="w-4 h-4 text-indigo-600 rounded border-gray-300"
                />
                <span className="text-sm font-medium text-gray-700">{icon} {label}</span>
              </label>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-200">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Jours avant expiration SSL</label>
              <input type="number" value={preferences.ssl_expiry_warning_days} onChange={(e) => setPreferences({ ...preferences, ssl_expiry_warning_days: parseInt(e.target.value) || 30 })} className="w-full px-3 py-2 border border-gray-300 rounded-xl" min={1} max={90} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Seuil de baisse de score</label>
              <input type="number" value={preferences.score_drop_threshold} onChange={(e) => setPreferences({ ...preferences, score_drop_threshold: parseInt(e.target.value) || 10 })} className="w-full px-3 py-2 border border-gray-300 rounded-xl" min={1} max={50} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fréquence des résumés</label>
              <select value={preferences.digest_frequency} onChange={(e) => setPreferences({ ...preferences, digest_frequency: e.target.value as any })} className="w-full px-3 py-2 border border-gray-300 rounded-xl">
                {DIGEST_FREQUENCIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Heures silencieuses</label>
              <div className="flex gap-2">
                <input type="time" value={preferences.quiet_hours_start || ''} onChange={(e) => setPreferences({ ...preferences, quiet_hours_start: e.target.value || null })} className="flex-1 px-3 py-2 border border-gray-300 rounded-xl" />
                <span className="text-gray-500 self-center">→</span>
                <input type="time" value={preferences.quiet_hours_end || ''} onChange={(e) => setPreferences({ ...preferences, quiet_hours_end: e.target.value || null })} className="flex-1 px-3 py-2 border border-gray-300 rounded-xl" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Canaux de notification */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Send size={18} />
            Canaux de notification
          </h2>
          <button onClick={() => { setEditingChannel(null); setChannelForm({ name: '', channel_type: 'email', enabled: true, config: {}, severities: ['info', 'warning', 'critical'], alert_types: [] }); setShowChannelForm(!showChannelForm); }} className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition">
            <Plus size={16} /> Ajouter un canal
          </button>
        </div>

        {showChannelForm && (
          <div className="bg-gray-50 rounded-xl p-4 space-y-3 animate-in slide-in-from-top duration-300">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Nom du canal</label>
                <input type="text" value={channelForm.name} onChange={(e) => setChannelForm({ ...channelForm, name: e.target.value })} placeholder="Mon canal Slack" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" required />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Type de canal</label>
                <select value={channelForm.channel_type} onChange={(e) => { const type = e.target.value as any; setChannelForm({ ...channelForm, channel_type: type, config: type === 'email' ? { email: '' } : { webhook_url: '' } }); }} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  {CHANNEL_TYPES.map(t => <option key={t.value} value={t.value}>{t.icon} {t.label}</option>)}
                </select>
              </div>
            </div>

            <div className="bg-white rounded-lg p-3 border border-gray-200">
              <p className="text-xs font-medium text-gray-500 mb-2">Configuration</p>
              {channelForm.channel_type === 'email' && (
                <input type="email" value={channelForm.config.email || ''} onChange={(e) => handleChannelConfigChange('email', e.target.value)} placeholder="destinataire@example.com" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              )}
              {(channelForm.channel_type === 'slack' || channelForm.channel_type === 'discord') && (
                <input type="url" value={channelForm.config.webhook_url || ''} onChange={(e) => handleChannelConfigChange('webhook_url', e.target.value)} placeholder="https://hooks.slack.com/services/..." className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              )}
              {channelForm.channel_type === 'webhook' && (
                <>
                  <input type="url" value={channelForm.config.url || ''} onChange={(e) => handleChannelConfigChange('url', e.target.value)} placeholder="https://votre-webhook.com/endpoint" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2" />
                  <input type="text" value={channelForm.config.secret || ''} onChange={(e) => handleChannelConfigChange('secret', e.target.value)} placeholder="Secret (optionnel)" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                </>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Sévérités</label>
                <div className="flex flex-wrap gap-2">
                  {SEVERITY_OPTIONS.map(s => (
                    <label key={s.value} className="flex items-center gap-1.5 text-xs">
                      <input type="checkbox" checked={channelForm.severities.includes(s.value)} onChange={(e) => { if (e.target.checked) { setChannelForm({ ...channelForm, severities: [...channelForm.severities, s.value] }); } else { setChannelForm({ ...channelForm, severities: channelForm.severities.filter(v => v !== s.value) }); } }} className="w-3 h-3 text-indigo-600 rounded border-gray-300" />
                      {s.label}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Actif</label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={channelForm.enabled} onChange={(e) => setChannelForm({ ...channelForm, enabled: e.target.checked })} className="w-4 h-4 text-indigo-600 rounded border-gray-300" />
                  Canal actif
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
              <button onClick={() => { setShowChannelForm(false); setEditingChannel(null); }} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-lg transition">
                Annuler
              </button>
              <button onClick={handleCreateChannel} disabled={saving || !channelForm.name} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center gap-2">
                {saving && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {editingChannel ? 'Mettre à jour' : 'Créer'}
              </button>
            </div>
          </div>
        )}

        {channels.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Aucun canal de notification configuré</p>
        ) : (
          <div className="space-y-2">
            {channels.map(channel => (
              <div key={channel.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-indigo-600">{getChannelTypeIcon(channel.channel_type)}</span>
                    <span className="text-sm font-medium text-gray-900">{channel.name}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${channel.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {channel.enabled ? '✅ Actif' : '⏸ Inactif'}
                    </span>
                    <span className="text-xs text-gray-400">{channel.channel_type}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Sévérités: {channel.severities.join(', ')}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => editChannel(channel)} className="p-1.5 text-gray-400 hover:text-gray-600 transition rounded">
                    <Edit size={16} />
                  </button>
                  <button onClick={() => handleDeleteChannel(channel.id)} className="p-1.5 text-gray-400 hover:text-red-600 transition rounded">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Règles avancées */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Settings size={18} />
            Règles d'alertes personnalisées
          </h2>
          <button onClick={() => { setEditingRule(null); setRuleForm({ name: '', metric: 'health_score', operator: 'lt', threshold: 80, severity: 'warning', enabled: true, cooldown_minutes: 60, website_id: '' }); setShowRuleForm(!showRuleForm); }} className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition">
            <Plus size={16} /> Ajouter une règle
          </button>
        </div>

        {showRuleForm && (
          <div className="bg-gray-50 rounded-xl p-4 space-y-3 animate-in slide-in-from-top duration-300">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Nom de la règle</label>
                <input type="text" value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} placeholder="Alerte score faible" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" required />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Site concerné</label>
                <select value={ruleForm.website_id} onChange={(e) => setRuleForm({ ...ruleForm, website_id: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="">Tous les sites</option>
                  {websites.map(site => <option key={site.id} value={site.id}>{site.domain}</option>)}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Métrique</label>
                <select value={ruleForm.metric} onChange={(e) => setRuleForm({ ...ruleForm, metric: e.target.value as any })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  {RULE_METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Opérateur</label>
                <select value={ruleForm.operator} onChange={(e) => setRuleForm({ ...ruleForm, operator: e.target.value as any })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  {RULE_OPERATORS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Seuil</label>
                <input type="number" value={ruleForm.threshold} onChange={(e) => setRuleForm({ ...ruleForm, threshold: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Cooldown (min)</label>
                <input type="number" value={ruleForm.cooldown_minutes} onChange={(e) => setRuleForm({ ...ruleForm, cooldown_minutes: parseInt(e.target.value) || 0 })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Sévérité</label>
                <select value={ruleForm.severity} onChange={(e) => setRuleForm({ ...ruleForm, severity: e.target.value as any })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="warning">⚠️ Warning</option>
                  <option value="critical">🔴 Critical</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Statut</label>
                <label className="flex items-center gap-2 text-sm h-9">
                  <input type="checkbox" checked={ruleForm.enabled} onChange={(e) => setRuleForm({ ...ruleForm, enabled: e.target.checked })} className="w-4 h-4 text-indigo-600 rounded border-gray-300" />
                  Règle active
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
              <button onClick={() => { setShowRuleForm(false); setEditingRule(null); }} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-lg transition">
                Annuler
              </button>
              <button onClick={handleCreateRule} disabled={saving || !ruleForm.name} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center gap-2">
                {saving && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {editingRule ? 'Mettre à jour' : 'Créer'}
              </button>
            </div>
          </div>
        )}

        {rules.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Aucune règle d'alerte configurée</p>
        ) : (
          <div className="space-y-2">
            {rules.map(rule => (
              <div key={rule.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{rule.name}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${rule.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {rule.enabled ? '✅ Active' : '⏸ Inactive'}
                    </span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${rule.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                      {rule.severity === 'critical' ? '🔴' : '⚠️'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    SI <span className="font-mono bg-white px-1 py-0.5 rounded border border-gray-200">{RULE_METRICS.find(m => m.value === rule.metric)?.label || rule.metric}</span> {RULE_OPERATORS.find(o => o.value === rule.operator)?.label || rule.operator} <span className="font-bold">{rule.threshold}</span>
                    {rule.website && <span className="ml-2">— Site: {rule.website.domain}</span>}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => editRule(rule)} className="p-1.5 text-gray-400 hover:text-gray-600 transition rounded">
                    <Edit size={16} />
                  </button>
                  <button onClick={() => handleDeleteRule(rule.id)} className="p-1.5 text-gray-400 hover:text-red-600 transition rounded">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Fenêtres de silence */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Moon size={18} />
            Fenêtres de silence
          </h2>
          <button onClick={() => { setEditingMute(null); setMuteForm({ start_at: '', end_at: '', reason: 'maintenance', note: '', websites: [] }); setShowMuteForm(!showMuteForm); }} className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition">
            <Plus size={16} /> Ajouter
          </button>
        </div>

        {showMuteForm && (
          <div className="bg-gray-50 rounded-xl p-4 space-y-3 animate-in slide-in-from-top duration-300">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Début</label>
                <input type="datetime-local" value={muteForm.start_at} onChange={(e) => setMuteForm({ ...muteForm, start_at: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fin</label>
                <input type="datetime-local" value={muteForm.end_at} onChange={(e) => setMuteForm({ ...muteForm, end_at: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Raison</label>
                <select value={muteForm.reason} onChange={(e) => setMuteForm({ ...muteForm, reason: e.target.value as any })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  {REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Sites concernés</label>
                <select multiple value={muteForm.websites.map(String)} onChange={(e) => { const values = Array.from(e.target.selectedOptions, opt => parseInt(opt.value)); setMuteForm({ ...muteForm, websites: values }); }} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm h-20">
                  {websites.map(site => <option key={site.id} value={site.id}>{site.domain}</option>)}
                </select>
                <p className="text-xs text-gray-400 mt-1">Maintenez Ctrl pour sélectionner plusieurs sites</p>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Note</label>
              <input type="text" value={muteForm.note} onChange={(e) => setMuteForm({ ...muteForm, note: e.target.value })} placeholder="Raison de la fenêtre de silence..." className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => { setShowMuteForm(false); setEditingMute(null); }} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-lg transition">
                Annuler
              </button>
              <button onClick={handleCreateMute} disabled={saving || !muteForm.start_at || !muteForm.end_at} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center gap-2">
                {saving && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {editingMute ? 'Mettre à jour' : 'Créer'}
              </button>
            </div>
          </div>
        )}

        {muteWindows.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Aucune fenêtre de silence</p>
        ) : (
          <div className="space-y-2">
            {muteWindows.map(mute => (
              <div key={mute.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${mute.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {mute.is_active ? '✅ Actif' : '⏸ Inactif'}
                    </span>
                    <span className="text-sm font-medium text-gray-900">{REASONS.find(r => r.value === mute.reason)?.label || mute.reason}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {formatDate(mute.start_at)} → {formatDate(mute.end_at)}
                    {mute.websites && mute.websites.length > 0 && <span className="ml-2">• {mute.websites.map(w => w.domain).join(', ')}</span>}
                  </p>
                  {mute.note && <p className="text-xs text-gray-400 mt-0.5">📝 {mute.note}</p>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => editMute(mute)} className="p-1.5 text-gray-400 hover:text-gray-600 transition rounded">
                    <Edit size={16} />
                  </button>
                  <button onClick={() => handleDeleteMute(mute.id)} className="p-1.5 text-gray-400 hover:text-red-600 transition rounded">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap items-center gap-3">
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value as any)} className="px-3 py-1.5 border border-gray-200 rounded-lg bg-white text-gray-700 text-sm">
          <option value="all">Toutes</option>
          <option value="firing">Actives</option>
          <option value="acknowledged">Acquittées</option>
          <option value="resolved">Résolues</option>
        </select>
        <span className="text-sm text-gray-500">{filteredAlerts.length} alertes</span>
      </div>

      {/* Liste des alertes */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-bold text-gray-900">Liste des alertes</h2>
        </div>

        {filteredAlerts.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-4xl mb-3">🔕</div>
            <p className="text-gray-500">Aucune alerte</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredAlerts.map((alert) => {
              const severity = getSeverityConfig(alert.severity);
              const status = getStatusConfig(alert.status);
              return (
                <div key={alert.id} className="p-4 hover:bg-gray-50 transition">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full ${severity.color.split(' ')[0]}`}>
                        {severity.icon}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-semibold text-gray-900">{alert.title}</h3>
                          <p className="text-sm text-gray-600 mt-0.5">{alert.message}</p>
                          <div className="flex flex-wrap items-center gap-2 mt-1.5">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severity.color}`}>
                              {severity.icon} {alert.severity}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${status.color}`}>
                              {status.label}
                            </span>
                            {alert.website && (
                              <Link to={`/${currentLang}/app/websites/${alert.website.id}`} className="text-xs text-indigo-600 hover:underline">
                                {alert.website.display_name || alert.website.domain}
                              </Link>
                            )}
                            <span className="text-xs text-gray-400">{getTimeAgo(alert.created_at)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {alert.status === 'firing' && (
                            <>
                              <button onClick={() => handleAcknowledge(alert.id)} className="px-3 py-1 text-xs font-medium bg-yellow-100 hover:bg-yellow-200 text-yellow-700 rounded-lg transition">
                                Acquitter
                              </button>
                              <button onClick={() => handleResolve(alert.id)} className="px-3 py-1 text-xs font-medium bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition">
                                Résoudre
                              </button>
                            </>
                          )}
                          {alert.status === 'acknowledged' && (
                            <button onClick={() => handleResolve(alert.id)} className="px-3 py-1 text-xs font-medium bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition">
                              Résoudre
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default Alerts;
