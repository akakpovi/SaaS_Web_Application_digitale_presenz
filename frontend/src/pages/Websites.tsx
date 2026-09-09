import React, { useEffect, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../services/api';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { UpgradeBanner } from '../components/UpgradeBanner';
import { Search, RefreshCw, Plus, X, AlertCircle, CheckCircle, Clock, TrendingUp, TrendingDown, Minus, Lock } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface WebsiteItem {
  id: number;
  domain: string;
  display_name: string;
  is_active: boolean;
  health_score: number | null;
  created_at: string;
  last_scan_at: string | null;
  scan_status?: 'idle' | 'scanning' | 'failed' | 'never';
  score_trend?: 'up' | 'down' | 'stable' | null;
  trend_value?: number | null;
}

// Traductions complètes avec toutes les clés nécessaires
const TRANSLATIONS = {
  fr: {
    title: "Vos sites web",
    subtitle: "Gérez et surveillez tous vos sites depuis un seul endroit.",
    addBtn: "Ajouter un site",
    search: "Rechercher un site...",
    filter: "Filtrer",
    filters: {
      all: "Tous les sites",
      healthy: "Sains",
      warning: "Attention",
      critical: "Critiques",
      scanning: "En cours de scan",
    },
    sort: "Trier par",
    sorts: {
      name: "Nom",
      score: "Score",
      date: "Date d'ajout",
      trend: "Tendance",
    },
    count: "{count} sites",
    usage: "{used}/{max} utilisés",
    formTitle: "Surveiller un nouveau domaine",
    domainLabel: "Nom de domaine *",
    nameLabel: "Nom d'affichage (optionnel)",
    placeholderDomain: "ex: monsite.com",
    placeholderName: "Mon Site Web",
    cancel: "Annuler",
    submit: "Ajouter le site",
    adding: "Ajout en cours...",
    score: "Score",
    active: "Actif",
    inactive: "Inactif",
    paused: "En pause",
    scanning: "Scan en cours...",
    scan_failed: "Échec du scan",
    scan_now: "Scanner maintenant",
    retry: "Réessayer",
    scanned: "Scanné le {time}",
    viewDetails: "Voir le diagnostic",
    emptyTitle: "Aucun site surveillé",
    emptyDesc: "Ajoutez votre premier site pour commencer à surveiller votre présence digitale.",
    emptyBtn: "Ajouter votre premier site",
    no_results: "Aucun résultat",
    no_results_desc: "Aucun site ne correspond à votre recherche.",
    lastScan: "Dernier scan",
    neverScanned: "Jamais scanné",
    pro_feature: "Fonctionnalité Pro",
    loading: "Chargement...",
    errors: {
      load_failed: "Erreur lors du chargement des sites",
      add_failed: "Erreur lors de l'ajout du site",
      domain_required: "Le domaine est requis",
      domain_invalid: "Domaine invalide",
    },
    plan: {
      free_badge: "Gratuit - {used}/{max} sites",
      pro_badge: "Pro",
      upgrade: "Passer à Pro",
    },
    status: {
      healthy: "Sain",
      good: "Bon",
      warning: "Attention",
      critical: "Critique",
      unknown: "Inconnu",
    },
    common: {
      refresh: "Rafraîchir",
      loading: "Chargement...",
    },
  },
  en: {
    title: "Your Websites",
    subtitle: "Manage and monitor all your websites from one place.",
    addBtn: "Add website",
    search: "Search websites...",
    filter: "Filter",
    filters: {
      all: "All sites",
      healthy: "Healthy",
      warning: "Warning",
      critical: "Critical",
      scanning: "Scanning",
    },
    sort: "Sort by",
    sorts: {
      name: "Name",
      score: "Score",
      date: "Date added",
      trend: "Trend",
    },
    count: "{count} sites",
    usage: "{used}/{max} used",
    formTitle: "Monitor a new domain",
    domainLabel: "Domain name *",
    nameLabel: "Display name (optional)",
    placeholderDomain: "e.g. mywebsite.com",
    placeholderName: "My Website",
    cancel: "Cancel",
    submit: "Add website",
    adding: "Adding...",
    score: "Score",
    active: "Active",
    inactive: "Inactive",
    paused: "Paused",
    scanning: "Scanning...",
    scan_failed: "Scan failed",
    scan_now: "Scan now",
    retry: "Retry",
    scanned: "Scanned on {time}",
    viewDetails: "View details",
    emptyTitle: "No websites monitored",
    emptyDesc: "Add your first website to start monitoring your digital presence.",
    emptyBtn: "Add your first website",
    no_results: "No results",
    no_results_desc: "No websites match your search.",
    lastScan: "Last scan",
    neverScanned: "Never scanned",
    pro_feature: "Pro Feature",
    loading: "Loading...",
    errors: {
      load_failed: "Failed to load websites",
      add_failed: "Failed to add website",
      domain_required: "Domain is required",
      domain_invalid: "Invalid domain",
    },
    plan: {
      free_badge: "Free - {used}/{max} sites",
      pro_badge: "Pro",
      upgrade: "Upgrade to Pro",
    },
    status: {
      healthy: "Healthy",
      good: "Good",
      warning: "Warning",
      critical: "Critical",
      unknown: "Unknown",
    },
    common: {
      refresh: "Refresh",
      loading: "Loading...",
    },
  },
  de: {
    title: "Ihre Websites",
    subtitle: "Verwalten und überwachen Sie alle Ihre Websites an einem Ort.",
    addBtn: "Website hinzufügen",
    search: "Website suchen...",
    filter: "Filter",
    filters: {
      all: "Alle Websites",
      healthy: "Gesund",
      warning: "Warnung",
      critical: "Kritisch",
      scanning: "Scan läuft",
    },
    sort: "Sortieren nach",
    sorts: {
      name: "Name",
      score: "Score",
      date: "Hinzugefügt am",
      trend: "Trend",
    },
    count: "{count} Websites",
    usage: "{used}/{max} genutzt",
    formTitle: "Neue Domain überwachen",
    domainLabel: "Domain-Name *",
    nameLabel: "Anzeigename (optional)",
    placeholderDomain: "z.B. meine-website.de",
    placeholderName: "Meine Website",
    cancel: "Abbrechen",
    submit: "Website hinzufügen",
    adding: "Hinzufügen...",
    score: "Score",
    active: "Aktiv",
    inactive: "Inaktiv",
    paused: "Pausiert",
    scanning: "Scan läuft...",
    scan_failed: "Scan fehlgeschlagen",
    scan_now: "Jetzt scannen",
    retry: "Wiederholen",
    scanned: "Gescannt am {time}",
    viewDetails: "Details anzeigen",
    emptyTitle: "Keine Websites überwacht",
    emptyDesc: "Fügen Sie Ihre erste Website hinzu, um Ihre digitale Präsenz zu überwachen.",
    emptyBtn: "Erste Website hinzufügen",
    no_results: "Keine Ergebnisse",
    no_results_desc: "Keine Website entspricht Ihrer Suche.",
    lastScan: "Letzter Scan",
    neverScanned: "Nie gescannt",
    pro_feature: "Pro-Funktion",
    loading: "Laden...",
    errors: {
      load_failed: "Fehler beim Laden der Websites",
      add_failed: "Fehler beim Hinzufügen der Website",
      domain_required: "Domain wird benötigt",
      domain_invalid: "Ungültige Domain",
    },
    plan: {
      free_badge: "Kostenlos - {used}/{max} Websites",
      pro_badge: "Pro",
      upgrade: "Auf Pro upgraden",
    },
    status: {
      healthy: "Gesund",
      good: "Gut",
      warning: "Warnung",
      critical: "Kritisch",
      unknown: "Unbekannt",
    },
    common: {
      refresh: "Aktualisieren",
      loading: "Laden...",
    },
  }
};

export function Websites() {
  const { lang } = useParams<{ lang?: string }>();
  const { i18n } = useTranslation();
  const { user, plan } = useAuth();

  const currentLang = (lang || i18n.language || 'fr').split('-')[0].toLowerCase() as 'fr' | 'en' | 'de';
  const t = TRANSLATIONS[currentLang] || TRANSLATIONS.fr;

  // États
  const [websites, setWebsites] = useState<WebsiteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [domainInput, setDomainInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'healthy' | 'warning' | 'critical' | 'scanning'>('all');
  const [sortBy, setSortBy] = useState<'name' | 'score' | 'date' | 'trend'>('date');
  const [showUpgradeBanner, setShowUpgradeBanner] = useState(() => {
    return sessionStorage.getItem('dismissWebsitesUpgrade') !== 'true';
  });

  // Récupérer les sites
  const fetchWebsites = useCallback(() => {
    setLoading(true);
    const token = localStorage.getItem('access_token');
    api
      .get("websites/", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        const list = res.data?.results || res.data || [];
        // Enrichir avec des données de tendance simulées
        const enrichedList = Array.isArray(list) ? list.map((site: any, index: number) => ({
          ...site,
          score_trend: index % 3 === 0 ? 'up' : index % 3 === 1 ? 'down' : 'stable',
          trend_value: index % 3 === 0 ? Math.floor(Math.random() * 10) + 1 :
            index % 3 === 1 ? -(Math.floor(Math.random() * 10) + 1) : 0,
          scan_status: site.health_score === null ? 'never' : 'idle'
        })) : [];
        setWebsites(enrichedList);
      })
      .catch(() => {
        setFormError(t.errors.load_failed);
      })
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

  // Ajouter un site
  const handleCreateWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedDomain = domainInput.trim();

    if (!trimmedDomain) {
      setFormError(t.errors.domain_required);
      return;
    }

    const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$/;
    if (!domainRegex.test(trimmedDomain)) {
      setFormError(t.errors.domain_invalid);
      return;
    }

    setSubmitting(true);
    setFormError(null);
    const token = localStorage.getItem('access_token');

    try {
      await api.post(
        "websites/",
        {
          domain: trimmedDomain,
          display_name: nameInput.trim() || trimmedDomain,
        },
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      setDomainInput('');
      setNameInput('');
      setShowAddForm(false);
      fetchWebsites();
    } catch (err: any) {
      setFormError(
        err.response?.data?.domain?.[0] ||
        err.response?.data?.detail ||
        t.errors.add_failed
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Lancer un scan
  const handleScan = async (websiteId: number) => {
    try {
      const token = localStorage.getItem('access_token');
      await api.post(`websites/${websiteId}/scan/`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      // Mettre à jour le statut local
      setWebsites(prev => prev.map(w =>
        w.id === websiteId ? { ...w, scan_status: 'scanning' } : w
      ));
      // Rafraîchir après quelques secondes
      setTimeout(fetchWebsites, 3000);
    } catch (error) {
      console.error('Error triggering scan:', error);
    }
  };

  // Fonctions utilitaires
  const getScoreStatus = (score: number | null): 'healthy' | 'warning' | 'critical' | 'unknown' => {
    if (score === null) return 'unknown';
    if (score >= 70) return 'healthy';
    if (score >= 50) return 'warning';
    return 'critical';
  };

  const getStatusLabel = (status: string): string => {
    const labels: Record<string, string> = {
      healthy: t.status.healthy,
      warning: t.status.warning,
      critical: t.status.critical,
      unknown: t.status.unknown,
    };
    return labels[status] || status;
  };

  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      healthy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
      critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
      unknown: 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400',
    };
    return colors[status] || colors.unknown;
  };

  const getStatusIcon = (status: string): string => {
    const icons: Record<string, string> = {
      healthy: '🟢',
      warning: '🟡',
      critical: '🔴',
      unknown: '⚪',
    };
    return icons[status] || icons.unknown;
  };

  const getScanStatusDisplay = (site: WebsiteItem) => {
    if (site.scan_status === 'scanning') {
      return {
        icon: <Clock size={14} className="animate-pulse text-blue-500" />,
        label: t.scanning,
        color: 'text-blue-600 dark:text-blue-400',
        action: null,
      };
    }
    if (site.scan_status === 'failed') {
      return {
        icon: <AlertCircle size={14} className="text-red-500" />,
        label: t.scan_failed,
        color: 'text-red-600 dark:text-red-400',
        action: { label: t.retry, onClick: () => handleScan(site.id) },
      };
    }
    if (site.scan_status === 'never' || site.health_score === null) {
      return {
        icon: <Plus size={14} className="text-indigo-500" />,
        label: t.scan_now,
        color: 'text-indigo-600 dark:text-indigo-400 cursor-pointer hover:underline',
        action: { label: t.scan_now, onClick: () => handleScan(site.id) },
      };
    }
    return {
      icon: <CheckCircle size={14} className="text-green-500" />,
      label: site.last_scan_at
        ? t.scanned.replace('{time}', new Date(site.last_scan_at).toLocaleDateString())
        : t.scanned.replace('{time}', new Date(site.created_at).toLocaleDateString()),
      color: 'text-green-600 dark:text-green-400',
      action: null,
    };
  };

  const getTrendDisplay = (site: WebsiteItem) => {
    if (!site.score_trend || site.health_score === null) return null;

    const configs = {
      up: {
        icon: <TrendingUp size={14} className="text-green-500" />,
        color: 'text-green-600 dark:text-green-400',
        prefix: '+',
      },
      down: {
        icon: <TrendingDown size={14} className="text-red-500" />,
        color: 'text-red-600 dark:text-red-400',
        prefix: '',
      },
      stable: {
        icon: <Minus size={14} className="text-gray-400" />,
        color: 'text-gray-400',
        prefix: '',
      },
    };

    const config = configs[site.score_trend];
    return {
      ...config,
      value: site.trend_value !== null && site.trend_value !== undefined ? `${config.prefix}${site.trend_value}` : null,
    };
  };

  // Filtrage et tri
  const filteredWebsites = websites
    .filter(w => {
      const matchesSearch = w.domain.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (w.display_name?.toLowerCase().includes(searchTerm.toLowerCase()) || false);
      if (filterStatus === 'all') return matchesSearch;
      if (filterStatus === 'scanning') return matchesSearch && w.scan_status === 'scanning';
      const status = getScoreStatus(w.health_score);
      return matchesSearch && status === filterStatus;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return (a.display_name || a.domain).localeCompare(b.display_name || b.domain);
        case 'score':
          return (b.health_score || 0) - (a.health_score || 0);
        case 'date':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'trend':
          if (a.score_trend === 'up' && b.score_trend !== 'up') return -1;
          if (a.score_trend === 'down' && b.score_trend === 'up') return 1;
          return 0;
        default:
          return 0;
      }
    });

  // Chargement
  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-sm text-gray-400 font-medium">{t.loading}</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 dark:border-gray-700 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t.title}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t.count.replace('{count}', websites.length.toString())}
            {plan && ` · ${t.usage.replace('{used}', websites.length.toString()).replace('{max}', plan.max_websites.toString())}`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Plan Badge avec lien d'upgrade */}
          {plan && (
            <span className={`text-xs font-medium px-3 py-1.5 rounded-full flex items-center gap-1 ${plan.tier === 'free'
              ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
              : 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
              }`}>
              {plan.tier === 'free'
                ? t.plan.free_badge.replace('{used}', websites.length.toString()).replace('{max}', plan.max_websites.toString())
                : `${plan.tier.charAt(0).toUpperCase() + plan.tier.slice(1)} ${t.plan.pro_badge}`
              }
              {plan.tier === 'free' && (
                <Link to="/pricing" className="ml-1 text-indigo-600 dark:text-indigo-400 hover:underline text-xs font-semibold">
                  {t.plan.upgrade}
                </Link>
              )}
            </span>
          )}

          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2.5 rounded-xl shadow-lg shadow-indigo-100 dark:shadow-indigo-900/20 transition active:scale-95"
            >
              <Plus size={18} />
              {t.addBtn}
            </button>
          )}
        </div>
      </div>

      {/* UPGRADE BANNER */}
      {plan?.tier === 'free' && websites.length > 0 && showUpgradeBanner && (
        <UpgradeBanner
          usedSites={websites.length}
          maxSites={plan.max_websites}
          onDismiss={() => {
            sessionStorage.setItem('dismissWebsitesUpgrade', 'true');
            setShowUpgradeBanner(false);
          }}
        />
      )}

      {/* FORMULAIRE D'AJOUT */}
      {showAddForm && (
        <form
          onSubmit={handleCreateWebsite}
          className="bg-white dark:bg-gray-800 p-6 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-lg space-y-4 max-w-2xl animate-in slide-in-from-top duration-300"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t.formTitle}</h3>
            <button
              type="button"
              onClick={() => {
                setShowAddForm(false);
                setFormError(null);
                setDomainInput('');
                setNameInput('');
              }}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <X size={20} />
            </button>
          </div>

          {formError && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm rounded-lg border border-red-200 dark:border-red-800 flex items-center gap-2">
              <AlertCircle size={16} />
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                {t.domainLabel}
              </label>
              <input
                type="text"
                required
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                placeholder={t.placeholderDomain}
                className="mt-1 block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 rounded-xl text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                {t.nameLabel}
              </label>
              <input
                type="text"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                placeholder={t.placeholderName}
                className="mt-1 block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 rounded-xl text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => {
                setShowAddForm(false);
                setFormError(null);
                setDomainInput('');
                setNameInput('');
              }}
              className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
            >
              {t.cancel}
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? t.adding : t.submit}
            </button>
          </div>
        </form>
      )}

      {/* SEARCH & FILTERS */}
      {websites.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder={t.search}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            />
          </div>

          <div className="flex gap-2 flex-wrap">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as any)}
              className="px-3 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            >
              <option value="all">{t.filters.all}</option>
              <option value="healthy">{t.filters.healthy}</option>
              <option value="warning">{t.filters.warning}</option>
              <option value="critical">{t.filters.critical}</option>
              <option value="scanning">{t.filters.scanning}</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            >
              <option value="date">{t.sorts.date}</option>
              <option value="name">{t.sorts.name}</option>
              <option value="score">{t.sorts.score}</option>
              <option value="trend">{t.sorts.trend}</option>
            </select>

            <button
              onClick={fetchWebsites}
              className="px-3 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
              title={t.common.refresh}
            >
              <RefreshCw size={18} className="text-gray-500" />
            </button>
          </div>
        </div>
      )}

      {/* LISTE DES SITES */}
      {filteredWebsites.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-12 text-center space-y-4">
          <div className="w-16 h-16 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-2xl flex items-center justify-center mx-auto text-2xl">
            🌐
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">
              {websites.length === 0 ? t.emptyTitle : t.no_results}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-sm mx-auto">
              {websites.length === 0 ? t.emptyDesc : t.no_results_desc}
            </p>
          </div>
          {websites.length === 0 && (
            <button
              onClick={() => setShowAddForm(true)}
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-6 py-3 rounded-xl shadow-lg transition"
            >
              <Plus size={18} />
              {t.emptyBtn}
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredWebsites.map((site) => {
            const status = getScoreStatus(site.health_score);
            const scanStatus = getScanStatusDisplay(site);
            const trend = getTrendDisplay(site);

            return (
              <Link
                key={site.id}
                to={`/${currentLang}/app/websites/${site.id}`}
                className="group bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 hover:border-indigo-300 dark:hover:border-indigo-700 hover:shadow-lg transition-all duration-300"
              >
                <div className="flex flex-col h-full">
                  {/* Header Card */}
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${getStatusColor(status)}`}>
                          {getStatusIcon(status)} {getStatusLabel(status)}
                        </span>
                        {site.is_active ? (
                          <span className="text-xs text-green-600 dark:text-green-400">🟢 {t.active}</span>
                        ) : (
                          <span className="text-xs text-gray-400">⏸ {t.paused}</span>
                        )}
                      </div>
                      <h3 className="font-semibold text-gray-900 dark:text-white mt-2 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition truncate">
                        {site.display_name || site.domain}
                      </h3>
                      <p className="text-xs text-gray-400 dark:text-gray-500 truncate">
                        {site.domain}
                      </p>
                    </div>
                    <div className="text-right ml-4 flex-shrink-0">
                      <div className="flex items-center gap-1.5 justify-end">
                        <span className={`text-xl font-bold ${site.health_score !== null
                          ? site.health_score >= 70 ? 'text-green-600'
                            : site.health_score >= 50 ? 'text-yellow-600'
                              : 'text-red-600'
                          : 'text-gray-400'
                          }`}>
                          {site.health_score !== null ? `${site.health_score}/100` : '--/100'}
                        </span>
                        {/* TREND - Nouveau */}
                        {trend && site.health_score !== null && (
                          <span className={`text-xs font-medium ${trend.color}`}>
                            {trend.icon}
                            {trend.value}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Footer Card */}
                  <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs min-w-0">
                      <span className={`flex items-center gap-1 ${scanStatus.color} ${scanStatus.action ? 'cursor-pointer hover:underline' : ''}`}
                        onClick={(e) => {
                          if (scanStatus.action) {
                            e.preventDefault();
                            scanStatus.action.onClick();
                          }
                        }}
                      >
                        {scanStatus.icon}
                        <span className="truncate max-w-[100px]">{scanStatus.label}</span>
                      </span>
                      {site.last_scan_at && site.health_score !== null && (
                        <span className="text-gray-400 dark:text-gray-500 hidden sm:inline">
                          · {new Date(site.last_scan_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400 group-hover:translate-x-1 transition-transform flex items-center gap-1">
                      {t.viewDetails} →
                    </span>
                  </div>

                  {/* PRO FEATURE BADGE - Nouveau */}
                  {site.id % 2 === 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 flex items-center gap-1 text-[10px] text-gray-400 dark:text-gray-500">
                      <Lock size={10} />
                      <span>{t.pro_feature}</span>
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default Websites;

