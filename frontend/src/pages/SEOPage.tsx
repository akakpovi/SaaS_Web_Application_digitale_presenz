import React, { useEffect, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../services/api';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import {
  Search, TrendingUp, TrendingDown, Minus,
  RefreshCw, Plus, X, AlertCircle, CheckCircle,
  BarChart3, Globe, FileText, Link as LinkIcon,
  Rocket, Zap, Shield
} from 'lucide-react';

interface KeywordItem {
  id: number;
  term: string;
  current_rank: number;
  previous_rank: number | null;
  search_volume: number;
  difficulty: number;
  trend: 'up' | 'down' | 'stable' | null;
}

interface SEOAudit {
  id: number;
  title: string;
  meta_description: string;
  robots_txt: boolean;
  sitemap_xml: boolean;
  h1_count: number;
  h2_count: number;
  images_with_alt: number;
  total_images: number;
  load_time: number;
  score: number;
  created_at: string;
}

export function SEOPage() {
  const { lang } = useParams<{ lang?: string }>();
  const { t, i18n } = useTranslation();
  const { plan } = useAuth();
  const currentLang = lang || i18n.language || 'fr';

  // Utiliser les traductions i18n avec fallback
  const getTranslation = (key: string, fallback: string) => {
    try {
      const translation = t(key);
      return translation && translation !== key ? translation : fallback;
    } catch {
      return fallback;
    }
  };

  // Traductions complètes avec fallback
  const translations = {
    title: getTranslation('seo.title', 'SEO Optimization & Audit'),
    subtitle: getTranslation('seo.subtitle', 'Track your keyword rankings and technical meta tags health.'),
    techTab: getTranslation('seo.tech_tab', 'Technical Audit'),
    keywordsTab: getTranslation('seo.keywords_tab', 'Tracked Keywords'),
    addKeyword: getTranslation('seo.add_keyword', 'Track a Keyword'),
    keywordLabel: getTranslation('seo.keyword_label', 'Keyword *'),
    placeholderKeyword: getTranslation('seo.placeholder_keyword', 'e.g. best italian restaurant'),
    cancel: getTranslation('common.cancel', 'Cancel'),
    submit: getTranslation('common.submit', 'Add'),
    position: getTranslation('seo.position', 'Position'),
    volume: getTranslation('seo.volume', 'Monthly Volume'),
    emptyTitle: getTranslation('seo.empty_title', 'No websites configured yet'),
    emptyDesc: getTranslation('seo.empty_desc', 'Add a website first to analyze its SEO performance.'),
    emptyBtn: getTranslation('websites.add', 'Add my first website'),
    noKeywords: getTranslation('seo.no_keywords', 'No keywords tracked for this website yet.'),
    runAudit: getTranslation('seo.run_audit', 'Run audit'),
    scanning: getTranslation('seo.scanning', 'Scanning...'),
    backlinks: getTranslation('seo.backlinks', 'Backlinks'),
    noBacklinks: getTranslation('seo.no_backlinks', 'No backlinks detected'),
    proFeature: getTranslation('seo.pro_feature', '🔒 Advanced SEO audit available with Pro plan'),
    upgrade: getTranslation('plan.upgrade', 'Upgrade to Pro →'),
    score: getTranslation('seo.score', 'SEO Score'),
    titleTag: getTranslation('seo.title_tag', 'Title'),
    metaDesc: getTranslation('seo.meta_desc', 'Meta description'),
    robotsTxt: getTranslation('seo.robots_txt', 'Robots.txt'),
    sitemap: getTranslation('seo.sitemap', 'Sitemap.xml'),
    images: getTranslation('seo.images', 'images'),
    notDefined: getTranslation('seo.not_defined', '❌ Not defined'),
    present: getTranslation('seo.present', '✅ Present'),
    missing: getTranslation('seo.missing', '❌ Missing'),
    trend: getTranslation('seo.trend', 'Trend'),
    difficulty: getTranslation('seo.difficulty', 'Difficulty'),
    noAudit: getTranslation('seo.no_audit', 'No SEO audit available'),
    backlinksTab: getTranslation('seo.backlinks_tab', 'Backlinks'),
  };

  const [websites, setWebsites] = useState<any[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [audit, setAudit] = useState<SEOAudit | null>(null);
  const [backlinks, setBacklinks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [keywordInput, setKeywordInput] = useState('');
  const [activeTab, setActiveTab] = useState<'keywords' | 'audit' | 'backlinks'>('keywords');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    api
      .get("websites/", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        const list = res.data?.results || res.data || [];
        setWebsites(Array.isArray(list) ? list : []);
        if (list.length > 0) {
          setSelectedSiteId(list[0].id);
        }
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  const fetchSEOData = useCallback(() => {
    if (!selectedSiteId) return;
    const token = localStorage.getItem('access_token');

    api
      .get(`websites/${selectedSiteId}/seo/keywords/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        const data = res.data?.results || res.data || [];
        setKeywords(Array.isArray(data) ? data : []);
      })
      .catch(() => setKeywords([]));

    api
      .get(`websites/${selectedSiteId}/seo/audits/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        const data = res.data?.results || res.data || [];
        setAudit(Array.isArray(data) && data.length > 0 ? data[0] : null);
      })
      .catch(() => setAudit(null));

    api
      .get(`websites/${selectedSiteId}/seo/backlinks/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        const data = res.data?.results || res.data || [];
        setBacklinks(Array.isArray(data) ? data : []);
      })
      .catch(() => setBacklinks([]));
  }, [selectedSiteId]);

  useEffect(() => {
    fetchSEOData();
  }, [fetchSEOData]);

  const handleAddKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keywordInput.trim() || !selectedSiteId) return;
    const token = localStorage.getItem('access_token');
    try {
      await api.post(
        `websites/${selectedSiteId}/seo/keywords/`,
        { term: keywordInput.trim() },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      setKeywordInput('');
      setShowAddForm(false);
      setSuccess('✅ Keyword added');
      setTimeout(() => setSuccess(null), 3000);
      fetchSEOData();
    } catch {
      setError('Error adding keyword');
      setTimeout(() => setError(null), 3000);
    }
  };

  const handleRunAudit = async () => {
    if (!selectedSiteId) return;
    setScanning(true);
    const token = localStorage.getItem('access_token');
    try {
      await api.post(`websites/${selectedSiteId}/seo/audits/run/`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSuccess('✅ SEO audit launched');
      setTimeout(() => setSuccess(null), 3000);
      setTimeout(fetchSEOData, 3000);
    } catch {
      setError('Error launching audit');
      setTimeout(() => setError(null), 3000);
    } finally {
      setScanning(false);
    }
  };

  const getTrendIcon = (trend: string | null) => {
    if (!trend) return null;
    const icons = {
      up: <TrendingUp size={14} className="text-green-500" />,
      down: <TrendingDown size={14} className="text-red-500" />,
      stable: <Minus size={14} className="text-gray-400" />,
    };
    return icons[trend as keyof typeof icons] || null;
  };

  const getTrendColor = (trend: string | null) => {
    if (!trend) return '';
    const colors = {
      up: 'text-green-600',
      down: 'text-red-600',
      stable: 'text-gray-400',
    };
    return colors[trend as keyof typeof colors] || '';
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-xs text-slate-400 font-medium">Loading SEO data...</p>
      </div>
    );
  }

  if (websites.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-4 max-w-xl mx-auto">
        <div className="w-16 h-16 bg-slate-50 border border-slate-200 rounded-2xl flex items-center justify-center mx-auto text-2xl shadow-sm">
          🔍
        </div>
        <div>
          <h3 className="text-lg font-bold text-slate-900">{translations.emptyTitle}</h3>
          <p className="text-sm text-slate-500 mt-1">{translations.emptyDesc}</p>
        </div>
        <Link
          to={`/${currentLang}/app/websites`}
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-6 py-3 rounded-xl shadow-lg transition active:scale-95"
        >
          + {translations.emptyBtn}
        </Link>
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
          <AlertCircle size={18} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
            <X size={18} />
          </button>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">🔍 {translations.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{translations.subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedSiteId || ''}
            onChange={(e) => setSelectedSiteId(Number(e.target.value))}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-sm focus:outline-none"
          >
            {websites.map((w) => (
              <option key={w.id} value={w.id}>
                🌐 {w.display_name || w.domain}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunAudit}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition disabled:opacity-50"
          >
            <RefreshCw size={16} className={scanning ? 'animate-spin' : ''} />
            {scanning ? translations.scanning : translations.runAudit}
          </button>
        </div>
      </div>

      <div className="flex gap-2 border-b border-slate-200 overflow-x-auto">
        <button
          onClick={() => setActiveTab('keywords')}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${activeTab === 'keywords'
            ? 'border-indigo-600 text-indigo-600'
            : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
        >
          {translations.keywordsTab} ({keywords.length})
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${activeTab === 'audit'
            ? 'border-indigo-600 text-indigo-600'
            : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
        >
          {translations.techTab} {audit ? `(${audit.score}/100)` : ''}
        </button>
        <button
          onClick={() => setActiveTab('backlinks')}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${activeTab === 'backlinks'
            ? 'border-indigo-600 text-indigo-600'
            : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
        >
          {translations.backlinksTab} ({backlinks.length})
        </button>
      </div>

      {activeTab === 'keywords' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{translations.keywordsTab} ({keywords.length})</h3>
            <button
              onClick={() => setShowAddForm(true)}
              className="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              <Plus size={14} /> {translations.addKeyword}
            </button>
          </div>

          {showAddForm && (
            <form onSubmit={handleAddKeyword} className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider">{translations.keywordLabel}</label>
                <input
                  type="text"
                  required
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  placeholder={translations.placeholderKeyword}
                  className="mt-1 block w-full px-3 py-2 border border-slate-300 bg-white rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowAddForm(false)} className="px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-200 rounded-lg">{translations.cancel}</button>
                <button type="submit" className="px-3 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg">{translations.submit}</button>
              </div>
            </form>
          )}

          {keywords.length === 0 ? (
            <p className="text-xs text-slate-400 py-8 text-center">{translations.noKeywords}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="pb-3">Keyword</th>
                    <th className="pb-3">{translations.position}</th>
                    <th className="pb-3">{translations.trend}</th>
                    <th className="pb-3">{translations.volume}</th>
                    <th className="pb-3">{translations.difficulty}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                  {keywords.map((kw) => (
                    <tr key={kw.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 font-semibold text-slate-900">{kw.term}</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${kw.current_rank <= 3 ? 'bg-emerald-50 text-emerald-700' : kw.current_rank <= 10 ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                          #{kw.current_rank}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className={`flex items-center gap-1 ${getTrendColor(kw.trend)}`}>
                          {getTrendIcon(kw.trend)}
                          {kw.previous_rank && kw.current_rank !== kw.previous_rank && (
                            <span>{kw.previous_rank > kw.current_rank ? '+' : ''}{kw.previous_rank - kw.current_rank}</span>
                          )}
                        </span>
                      </td>
                      <td className="py-3">{kw.search_volume?.toLocaleString() || 0}</td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${kw.difficulty < 30 ? 'bg-emerald-500' : kw.difficulty < 60 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${kw.difficulty || 0}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-500">{kw.difficulty || 0}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          {audit ? (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-3xl font-bold text-indigo-600">{audit.score}/100</div>
                  <div>
                    <p className="text-sm font-medium text-slate-900">{translations.score}</p>
                    <p className="text-xs text-slate-500">{new Date(audit.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-600">
                  <span className="flex items-center gap-1">
                    <CheckCircle size={14} className="text-green-500" />
                    {audit.images_with_alt}/{audit.total_images} {translations.images}
                  </span>
                  <span className="flex items-center gap-1">
                    <FileText size={14} className="text-blue-500" />
                    H1: {audit.h1_count}, H2: {audit.h2_count}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 bg-slate-50 rounded-xl text-center">
                  <p className="text-xs text-slate-500">{translations.titleTag}</p>
                  <p className="text-sm font-medium text-slate-900 truncate">{audit.title || translations.notDefined}</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl text-center">
                  <p className="text-xs text-slate-500">{translations.metaDesc}</p>
                  <p className="text-sm font-medium text-slate-900 truncate">{audit.meta_description || translations.notDefined}</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl text-center">
                  <p className="text-xs text-slate-500">{translations.robotsTxt}</p>
                  <p className="text-sm font-medium text-slate-900">{audit.robots_txt ? translations.present : translations.missing}</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl text-center">
                  <p className="text-xs text-slate-500">{translations.sitemap}</p>
                  <p className="text-sm font-medium text-slate-900">{audit.sitemap_xml ? translations.present : translations.missing}</p>
                </div>
              </div>

              {plan?.tier === 'free' && (
                <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between">
                  <span className="text-sm text-indigo-700">{translations.proFeature}</span>
                  <Link to="/pricing" className="text-sm font-medium text-indigo-600 hover:underline">
                    {translations.upgrade}
                  </Link>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">📊</div>
              <p className="text-slate-500">{translations.noAudit}</p>
              <button
                onClick={handleRunAudit}
                disabled={scanning}
                className="mt-3 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
              >
                {scanning ? translations.scanning : translations.runAudit}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'backlinks' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{translations.backlinks} ({backlinks.length})</h3>
          {backlinks.length === 0 ? (
            <p className="text-xs text-slate-400 py-8 text-center">{translations.noBacklinks}</p>
          ) : (
            <div className="space-y-3">
              {backlinks.map((bl, index) => (
                <div key={index} className="p-3 bg-slate-50 rounded-xl flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{bl.source_url}</p>
                    <p className="text-xs text-slate-500 truncate">{bl.anchor_text || 'No anchor'}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">
                      DA: {bl.domain_authority || 0}
                    </span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${bl.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                      {bl.status === 'active' ? '✅ Active' : '⏸ Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SEOPage;
