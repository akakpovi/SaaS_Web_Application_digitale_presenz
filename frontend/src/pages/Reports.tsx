import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { WhiteLabelReport } from '../components/WhiteLabelReport';
import { FileText, Calendar, Clock, Download, Settings, RefreshCw } from 'lucide-react';
import { api } from '../services/api';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function Reports() {
  const { lang } = useParams<{ lang?: string }>();
  const { t, i18n } = useTranslation();
  const { plan } = useAuth();
  const currentLang = (lang || i18n.language || 'fr').split('-')[0].toLowerCase();

  const [websites, setWebsites] = useState<any[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<'history' | 'generate'>('history');

  const fetchReports = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await api.get('/reports/', { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      setReports(res.data?.results || res.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    const fetchInit = async () => {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      try {
        const res = await api.get('/websites/', { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        const list = res.data?.results || res.data || [];
        setWebsites(list);
        if (list.length > 0) setSelectedSiteId(list[0].id);
        await fetchReports();
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchInit();
  }, []);

  const handleGenerateNow = async () => {
    if (!selectedSiteId) return;
    setGenerating(true);
    try {
      const token = localStorage.getItem('access_token');
      await api.post('/reports/generate/', { website_id: selectedSiteId }, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      await fetchReports();
      setActiveTab('history');
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="h-64 flex items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" /></div>;

  if (websites.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center max-w-xl mx-auto space-y-4">
        <div className="w-16 h-16 bg-slate-50 border border-slate-200 rounded-2xl flex items-center justify-center mx-auto text-2xl shadow-sm">📄</div>
        <h3 className="text-lg font-bold text-slate-900">{t('reports.empty.title', 'Aucun rapport disponible')}</h3>
        <p className="text-sm text-slate-500">{t('reports.empty.desc', 'Ajoutez un site web pour générer des rapports PDF marque blanche.')}</p>
        <Link to={`/${currentLang}/app/websites`} className="inline-block bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-6 py-3 rounded-xl shadow-lg">
          + {t('monitoring.add_first_site', 'Ajouter mon premier site')}
        </Link>
      </div>
    );
  }

  const activeSite = websites.find(w => w.id === selectedSiteId) || websites[0];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <FileText className="text-indigo-600" />
            {t('reports.title', 'Rapports & Historique')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">{t('reports.desc', 'Consultez l\'historique de vos audits et générez de nouveaux rapports PDF.')}</p>
        </div>

        <select
          value={selectedSiteId || ''}
          onChange={(e) => setSelectedSiteId(Number(e.target.value))}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
        >
          {websites.map((w) => (
            <option key={w.id} value={w.id}>
              🌐 {w.display_name || w.domain}
            </option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'history' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
        >
          {t('reports.tabs.history', 'Historique')}
        </button>
        <button
          onClick={() => setActiveTab('generate')}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'generate' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
        >
          {t('reports.tabs.generate', 'Générer / Planifier')}
        </button>
      </div>

      {activeTab === 'history' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Clock size={18} className="text-slate-500" /> {t('reports.history.title', 'Historique des rapports')}
            </h2>
            <button onClick={fetchReports} className="p-1.5 text-slate-500 hover:text-indigo-600 transition rounded-lg hover:bg-white border border-transparent hover:border-slate-200">
              <RefreshCw size={16} />
            </button>
          </div>
          {reports.length === 0 ? (
            <div className="p-8 text-center text-slate-500">{t('reports.history.empty', 'Aucun rapport généré pour le moment.')}</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {reports.map((report) => (
                <div key={report.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition">
                  <div>
                    <div className="font-semibold text-slate-900">{report.domain} - Rapport d'audit</div>
                    <div className="text-xs text-slate-500 mt-1">
                      {t('reports.history.generated_at', 'Généré le :')} {new Date(report.created_at).toLocaleString('fr-FR')} • {t('reports.history.score', 'Score :')} {report.score !== null ? `${report.score}/100` : 'N/A'}
                    </div>
                  </div>
                  <button onClick={() => window.open(`${API_BASE}/reports/pdf/${report.scan_id}/?lang=${currentLang}&token=${localStorage.getItem('access_token')}`, '_blank')} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-indigo-600 hover:bg-indigo-50 transition shadow-sm">
                    <Download size={14} /> PDF
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'generate' && activeSite && (
        <div className="space-y-6">
          {plan?.tier === 'free' ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center max-w-2xl mx-auto">
              <div className="w-16 h-16 bg-amber-50 text-amber-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText size={32} />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-2">{t('reports.pro.title', 'Rapports Marque Blanche')}</h3>
              <p className="text-slate-500 mb-6">{t('reports.pro.desc', 'La génération de rapports PDF détaillés et personnalisés avec votre logo est une fonctionnalité exclusive au plan Pro.')}</p>
              <Link to={`/${currentLang}/pricing`} className="inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-xl shadow-lg transition">
                {t('reports.pro.cta', 'Découvrir le plan Pro →')}
              </Link>
            </div>
          ) : (
            <>
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
                  <Settings size={18} className="text-indigo-600" /> {t('reports.generate.quick_action', 'Action Rapide')}
                </h2>
                <p className="text-sm text-slate-600 mb-4">{t('reports.generate.quick_action_desc', 'Déclenchez manuellement la génération d\'un rapport avec les dernières données d\'audit.')}</p>
                <button
                  onClick={handleGenerateNow}
                  disabled={generating}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold text-sm hover:bg-indigo-700 transition disabled:opacity-50"
                >
                  {generating ? <RefreshCw size={16} className="animate-spin" /> : <Calendar size={16} />}
                  {generating ? t('reports.generate.generating', 'Génération en cours...') : t('reports.generate.btn', 'Générer un rapport maintenant')}
                </button>
              </div>
              <WhiteLabelReport scanId={String(activeSite.id)} domain={activeSite.domain} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default Reports;
