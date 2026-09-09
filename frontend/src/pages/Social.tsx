import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import {
  Share2,
  RefreshCw,
  Plus,
  TrendingUp,
  MessageCircle,
  ThumbsUp,
  Globe
} from 'lucide-react';
import { format } from 'date-fns';

interface Website {
  id: string;
  domain: string;
  display_name: string;
}

interface SocialProfile {
  id: string;
  provider: string;
  handle: string;
  profile_url: string;
  followers: number;
  engagement_rate: number;
  last_synced_at: string | null;
}

interface SocialMention {
  id: string;
  platform: string;
  author: string;
  content: string;
  url: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  mentioned_at: string;
}

export const Social: React.FC = () => {
  const { lang } = useParams<{ lang: string }>();
  const { t } = useTranslation();

  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>('');
  
  const [profiles, setProfiles] = useState<SocialProfile[]>([]);
  const [mentions, setMentions] = useState<SocialMention[]>([]);
  const [loadingWebsites, setLoadingWebsites] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add profile form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newProfile, setNewProfile] = useState({ provider: 'twitter', handle: '', profile_url: '' });

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
      setError(t('social.errors.load_sites', "Erreur lors du chargement des sites"));
    } finally {
      setLoadingWebsites(false);
    }
  }, []);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

  const fetchData = useCallback(async (websiteId: string) => {
    try {
      setLoadingData(true);
      setError(null);
      const [profRes, mentRes] = await Promise.all([
        api.get(`/websites/${websiteId}/social/profiles/`),
        api.get(`/websites/${websiteId}/social/mentions/`)
      ]);
      setProfiles(profRes.data.results || profRes.data);
      setMentions(mentRes.data.results || mentRes.data);
    } catch (err) {
      console.error(err);
      setError(t('social.errors.load_data', "Erreur lors du chargement des données sociales"));
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    if (selectedWebsiteId) {
      fetchData(selectedWebsiteId);
    }
  }, [selectedWebsiteId, fetchData]);

  const handleSync = async () => {
    if (!selectedWebsiteId) return;
    try {
      setSyncing(true);
      await api.post(`/websites/${selectedWebsiteId}/social/sync/`);
      alert(t('social.sync_success', "Synchronisation lancée. Cela peut prendre quelques minutes."));
      setTimeout(() => fetchData(selectedWebsiteId), 5000);
    } catch (err) {
      console.error(err);
      alert(t('social.errors.sync', "Erreur lors de la synchronisation"));
    } finally {
      setSyncing(false);
    }
  };

  const handleAddProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWebsiteId) return;
    try {
      await api.post(`/websites/${selectedWebsiteId}/social/profiles/`, newProfile);
      setShowAddForm(false);
      setNewProfile({ provider: 'twitter', handle: '', profile_url: '' });
      fetchData(selectedWebsiteId);
    } catch (err) {
      console.error(err);
      alert(t('social.errors.add_profile', "Erreur lors de l'ajout du profil"));
    }
  };

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'facebook': return <Globe className="w-5 h-5 text-blue-600" />;
      case 'twitter': return <MessageCircle className="w-5 h-5 text-sky-500" />;
      case 'instagram': return <Share2 className="w-5 h-5 text-pink-600" />;
      case 'linkedin': return <Globe className="w-5 h-5 text-blue-700" />;
      default: return <Share2 className="w-5 h-5 text-slate-500" />;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch(sentiment) {
      case 'positive': return 'text-emerald-700 bg-emerald-100 ring-emerald-600/20';
      case 'negative': return 'text-red-700 bg-red-100 ring-red-600/20';
      default: return 'text-slate-700 bg-slate-100 ring-slate-600/20';
    }
  };

  if (loadingWebsites) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (websites.length === 0) {
    return (
      <div className="text-center py-20 bg-white rounded-3xl border border-slate-200">
        <Share2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">{t('social.empty_sites.title', 'Aucun site surveillé')}</h2>
        <p className="text-slate-500 mb-6 max-w-md mx-auto">
          {t('social.empty_sites.desc', 'Vous devez d\'abord ajouter un site web pour surveiller sa réputation sur les réseaux sociaux.')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header & Website Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            <Share2 className="w-8 h-8 text-indigo-600" />
            {t('social.title', 'Réseaux Sociaux')}
          </h1>
          <p className="text-slate-500 mt-1">{t('social.desc', 'Surveillez votre image de marque et vos mentions.')}</p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedWebsiteId}
            onChange={(e) => setSelectedWebsiteId(e.target.value)}
            className="block w-48 rounded-xl border-0 py-2 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6 bg-white shadow-sm"
          >
            {websites.map(site => (
              <option key={site.id} value={site.id}>
                {site.display_name || site.domain}
              </option>
            ))}
          </select>
          
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-4 py-2 rounded-xl font-bold text-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw size={16} className={syncing ? "animate-spin" : ""} />
            {syncing ? t('social.syncing', 'Synchro...') : t('social.sync', 'Synchroniser')}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-xl text-sm border border-red-100">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Profiles */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Globe className="w-5 h-5 text-slate-400" />
                {t('social.profiles.title', 'Vos Profils')}
              </h2>
              <button 
                onClick={() => setShowAddForm(!showAddForm)}
                className="p-2 bg-slate-50 hover:bg-slate-100 rounded-lg text-slate-600 transition-colors"
              >
                <Plus size={18} />
              </button>
            </div>

            {showAddForm && (
              <form onSubmit={handleAddProfile} className="mb-6 p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">{t('social.form.platform', 'Plateforme')}</label>
                  <select 
                    value={newProfile.provider}
                    onChange={e => setNewProfile({...newProfile, provider: e.target.value})}
                    className="w-full rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="twitter">Twitter/X</option>
                    <option value="facebook">Facebook</option>
                    <option value="instagram">Instagram</option>
                    <option value="linkedin">LinkedIn</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">{t('social.form.handle', 'Handle (ex: @presence)')}</label>
                  <input 
                    type="text" 
                    required
                    value={newProfile.handle}
                    onChange={e => setNewProfile({...newProfile, handle: e.target.value})}
                    className="w-full rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">{t('social.form.url', 'URL Profil (optionnel)')}</label>
                  <input 
                    type="url"
                    value={newProfile.profile_url}
                    onChange={e => setNewProfile({...newProfile, profile_url: e.target.value})}
                    className="w-full rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setShowAddForm(false)} className="px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200 rounded-lg">{t('social.form.cancel', 'Annuler')}</button>
                  <button type="submit" className="px-3 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg">{t('social.form.submit', 'Ajouter')}</button>
                </div>
              </form>
            )}

            {loadingData ? (
              <div className="text-center py-8 text-slate-400"><RefreshCw className="animate-spin mx-auto" /></div>
            ) : profiles.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                {t('social.profiles.empty', 'Aucun profil connecté.')}
              </div>
            ) : (
              <div className="space-y-4">
                {profiles.map(p => (
                  <div key={p.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="flex items-center gap-3">
                      {getProviderIcon(p.provider)}
                      <div>
                        <div className="font-bold text-sm text-slate-900">{p.handle}</div>
                        <div className="text-xs text-slate-500 capitalize">{p.provider}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-sm text-slate-900">{p.followers.toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{t('social.profiles.followers', 'Abonnés')}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Mentions */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-indigo-500" />
                {t('social.mentions.title', 'Dernières Mentions')}
              </h2>
            </div>
            
            {loadingData ? (
              <div className="text-center py-12 text-slate-400"><RefreshCw className="animate-spin mx-auto" /></div>
            ) : mentions.length === 0 ? (
              <div className="text-center py-16 px-4">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <MessageCircle className="w-8 h-8 text-slate-300" />
                </div>
                <h3 className="text-slate-900 font-bold mb-1">{t('social.mentions.empty', 'Aucune mention détectée')}</h3>
                <p className="text-slate-500 text-sm max-w-sm mx-auto">
                  {t('social.mentions.empty_desc', 'Nous n\'avons pas encore trouvé de mentions de votre marque. Ajoutez vos profils et lancez une synchronisation.')}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {mentions.map(m => (
                  <div key={m.id} className="p-6 hover:bg-slate-50 transition-colors">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">{m.author}</span>
                        <span className="text-xs text-slate-400 px-2 py-0.5 rounded bg-slate-100 uppercase">{m.platform}</span>
                      </div>
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getSentimentColor(m.sentiment)}`}>
                        {m.sentiment}
                      </span>
                    </div>
                    <p className="text-slate-700 text-sm mb-3 line-clamp-3">
                      {m.content}
                    </p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">{format(new Date(m.mentioned_at), 'dd MMM yyyy à HH:mm')}</span>
                      {m.url && (
                        <a href={m.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800 font-bold">
                          {t('social.mentions.view_source', 'Voir la source')} &rarr;
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Social;
