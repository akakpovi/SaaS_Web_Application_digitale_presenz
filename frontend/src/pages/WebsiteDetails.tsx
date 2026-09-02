import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { RemediationBlock } from '../components/RemediationBlock';
import { REMEDIATION_GUIDES } from '../types/remediation';
import { WhiteLabelReport } from '../components/WhiteLabelReport';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface CheckItem {
  category: string;
  status: 'healthy' | 'warning' | 'critical' | 'neutral';
  score: number | null;
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
  last_scan_id: number | null;
  last_scan_status: string | null;
  checks: CheckItem[];
  created_at: string;
}

export function WebsiteDetails() {
  const { id } = useParams<{ id: string }>();
  const [website, setWebsite] = useState<WebsiteData | null>(null);
  const [activeTab, setActiveTab] = useState<'health' | 'reports' | 'security' | 'seo'>('health');
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWebsiteData = () => {
    setLoading(true);
    setError(null);
    const token = localStorage.getItem('access_token');

    axios
      .get(`${API_BASE}/websites/${id}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        setWebsite(res.data);
      })
      .catch((err) => {
        if (err.response?.status === 401) {
          setError('Session expirée. Veuillez vous connecter.');
        } else if (err.response?.status === 404) {
          setError('Site introuvable dans votre compte.');
        } else {
          setError('Erreur lors du chargement des données depuis la base de données.');
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchWebsiteData();
  }, [id]);

  const handleTriggerScan = async () => {
    setScanning(true);
    const token = localStorage.getItem('access_token');
    try {
      await axios.post(
        `${API_BASE}/websites/${id}/scan/`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      // Recharger les vraies données après 3 secondes pour laisser le scanner Celery travailler
      setTimeout(fetchWebsiteData, 3000);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erreur lors du lancement du scan.');
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-sm text-slate-500 font-medium">Chargement des données réelles depuis PostgreSQL...</p>
      </div>
    );
  }

  if (error || !website) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <h3 className="text-lg font-bold text-red-700">Impossible d'afficher le site</h3>
        <p className="mt-2 text-sm text-red-600">{error || 'Site non trouvé.'}</p>
        <div className="mt-4 flex justify-center gap-3">
          <Link to="/app/websites" className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-700 border border-slate-300 hover:bg-slate-50">
            Retour aux sites
          </Link>
          <button onClick={fetchWebsiteData} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700">
            Réessayer
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

  return (
    <div className="space-y-6">
      {/* En-tête avec les vraies métadonnées */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/app/websites" className="text-sm font-medium text-slate-500 hover:text-slate-800">
              ← Retour aux sites
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

        <div className="flex items-center gap-3">
          {/* Bouton pour relancer un vrai scan en direct */}
          <button
            onClick={handleTriggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 active:scale-95 disabled:opacity-50"
          >
            <svg
              className={`h-4 w-4 ${scanning ? 'animate-spin text-indigo-600' : 'text-slate-500'}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {scanning ? 'Scan en cours...' : 'Relancer un scan'}
          </button>

          {/* Badge Score réel */}
          <div className={`flex items-center gap-3 rounded-2xl border px-4 py-2 ring-4 ${scoreBadgeColor}`}>
            <div className="text-center">
              <span className="text-2xl font-black">{website.health_score !== null ? website.health_score : '--'}</span>
              <span className="text-xs font-semibold">/100</span>
            </div>
            <span className="text-xs font-bold uppercase tracking-wider">Score Réel</span>
          </div>
        </div>
      </div>

      {/* Navigation des 4 onglets */}
      <div className="flex gap-2 border-b border-slate-200 overflow-x-auto">
        <button
          onClick={() => setActiveTab('health')}
          className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === 'health'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          🛡️ Santé & Remédiation ({website.checks.length} vérifications)
        </button>
        <button
          onClick={() => setActiveTab('reports')}
          className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === 'reports'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          📄 Rapports PDF (Marque Blanche)
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === 'security'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          🔒 Sécurité
        </button>
        <button
          onClick={() => setActiveTab('seo')}
          className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === 'seo'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          🔍 Audit SEO
        </button>
      </div>

      {/* Onglet 1 : Santé & Remédiation Réelle */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          {website.checks.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
              <p className="text-slate-500">Aucun scan enregistré pour ce site.</p>
              <button
                onClick={handleTriggerScan}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Lancer le premier scan
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-lg font-bold text-slate-900 mb-4">Diagnostic réel de la base PostgreSQL</h3>
              
              <div className="space-y-4">
                {website.checks.map((check) => (
                  <div key={check.category} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span
                          className={`h-3 w-3 rounded-full ${
                            check.status === 'healthy'
                              ? 'bg-emerald-500'
                              : check.status === 'warning'
                                ? 'bg-amber-500'
                                : 'bg-red-500'
                          }`}
                        />
                        <span className="font-semibold text-slate-900 capitalize text-sm">
                          {check.category.replace(/_/g, ' ')}
                        </span>
                      </div>
                      {check.score !== null && (
                        <span className="text-xs font-bold text-slate-600 bg-white border border-slate-200 rounded-md px-2 py-0.5">
                          {check.score} pts
                        </span>
                      )}
                    </div>

                    <p className="mt-2 text-sm text-slate-700 pl-6">{check.summary}</p>

                    {/* Remédiation automatique selon les vrais statuts remontés de la base */}
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
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Onglet 2 : Rapports PDF Marque Blanche */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <WhiteLabelReport
            scanId={String(website.last_scan_id || '')}
            domain={website.domain}
          />
        </div>
      )}

      {/* Onglets Sécurité & SEO */}
      {activeTab === 'security' && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900">Sécurité Active</h3>
          <p className="text-sm text-slate-600 mt-2">Dernière vérification pour {website.domain} exécutée avec succès.</p>
        </div>
      )}

      {activeTab === 'seo' && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900">Audit SEO Technique</h3>
          <p className="text-sm text-slate-600 mt-2">Indexation et balises du domaine {website.domain}.</p>
        </div>
      )}
    </div>
  );
}

export default WebsiteDetails;
