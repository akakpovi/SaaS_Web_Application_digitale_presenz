import React, { useEffect, useState } from 'react';
import { 
  Star, MessageSquare, Plus, RefreshCw, 
  Upload, Search, Loader, Globe, X 
} from "lucide-react";
import api from "../services/api";
import { Badge } from "../components/ui";

interface ReviewSource {
  id: number;
  source_type: string;
  name: string;
  url: string;
  is_active: boolean;
}

interface ReviewItem {
  id: string;
  author_name: string;
  rating: number;
  text: string;
  review_date: string;
  sentiment?: "positive" | "neutral" | "negative";
  language?: string;
  sentiment_confidence?: number;
  is_approved: boolean;
}

interface Website {
  id: string;
  domain: string;
  name: string;
}

export const Reviews: React.FC = () => {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string | null>(null);
  const [sources, setSources] = useState<ReviewSource[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryStatus, setDiscoveryStatus] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<number | null>(null);
  
  // Modales
  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [newSource, setNewSource] = useState({ source_type: "trustpilot", name: "", url: "" });
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  useEffect(() => {
    loadWebsites();
  }, []);

  useEffect(() => {
    if (selectedWebsiteId) {
      loadData(selectedWebsiteId);
    }
  }, [selectedWebsiteId]);

  const loadWebsites = async () => {
    try {
      const res = await api.get("/websites/");
      const list = res.data.results || res.data || [];
      setWebsites(list);
      if (list.length > 0) {
        setSelectedWebsiteId(list[0].id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadData = async (siteId: string) => {
    setIsLoading(true);
    try {
      const [srcRes, revRes] = await Promise.all([
        api.get(`/reviews/sources/?website_id=${siteId}`),
        api.get(`/reviews/?website_id=${siteId}`),
      ]);
      setSources(srcRes.data.results || srcRes.data || []);
      setReviews(revRes.data.results || revRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDiscover = async () => {
    if (!selectedWebsiteId) return;
    setDiscovering(true);
    setDiscoveryStatus(null);
    try {
      const res = await api.post("/reviews/discover/", { website_id: selectedWebsiteId });
      const data = res.data;
      if (data.total_new_reviews > 0) {
        const currentDomain = websites.find(w => w.id === selectedWebsiteId)?.domain || 'votre site';
      setDiscoveryStatus(`✨ ${data.total_new_reviews} avis réels trouvés et synchronisés depuis le web pour ${currentDomain} !`);
      } else {
        const currentDomain = websites.find(w => w.id === selectedWebsiteId)?.domain || 'votre site';
      setDiscoveryStatus(`Scan terminé : aucun nouvel avis public trouvé pour ${currentDomain}.`);
      }
      await loadData(selectedWebsiteId);
    } catch (err: any) {
      setDiscoveryStatus("Erreur lors de la détection des avis.");
    } finally {
      setDiscovering(false);
    }
  };

  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWebsiteId) return;
    try {
      await api.post("/reviews/sources/", { ...newSource, website: selectedWebsiteId });
      setShowAdd(false);
      setNewSource({ source_type: "trustpilot", name: "", url: "" });
      loadData(selectedWebsiteId);
    } catch (err) {
      console.error(err);
    }
  };

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile || !selectedWebsiteId) return;
    setImporting(true);
    setImportResult(null);

    const formData = new FormData();
    formData.append("file", importFile);
    formData.append("website_id", selectedWebsiteId);

    try {
      const res = await api.post("/reviews/import/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportResult(`Succès : ${res.data.created_count} avis importés.`);
      setTimeout(() => {
        setShowImport(false);
        setImportResult(null);
        setImportFile(null);
        loadData(selectedWebsiteId);
      }, 1500);
    } catch (err) {
      setImportResult("Erreur lors de l'import. Vérifiez le format (CSV ou JSON).");
    } finally {
      setImporting(false);
    }
  };

  const filteredReviews = activeSource 
    ? reviews.filter((r: any) => r.source === activeSource || r.source_id === activeSource)
    : reviews;

  const avgRating = reviews.length > 0
    ? (reviews.reduce((acc, r) => acc + Number(r.rating || 0), 0) / reviews.length).toFixed(1)
    : "—";

  const positiveCount = reviews.filter((r) => r.sentiment === "positive").length;
  const negativeCount = reviews.filter((r) => r.sentiment === "negative").length;

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Avis Clients & E-Réputation</h1>
          <p className="text-slate-500 text-sm mt-1">
            Détection automatique, synchronisation et analyse de sentiment des avis réels de votre site.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 flex-wrap">
          {websites.length > 1 && (
            <select
              value={selectedWebsiteId || ""}
              onChange={(e) => setSelectedWebsiteId(e.target.value)}
              className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {websites.map((w) => (
                <option key={w.id} value={w.id}>{w.domain}</option>
              ))}
            </select>
          )}

          <button
            onClick={handleDiscover}
            disabled={discovering || !selectedWebsiteId}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            {discovering ? <Loader size={16} className="animate-spin" /> : <Search size={16} />}
            {discovering ? "Scan en cours..." : "Détecter les avis réels"}
          </button>

          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <Upload size={16} /> Importer
          </button>

          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <Plus size={16} /> Ajouter une source
          </button>
        </div>
      </div>

      {/* Discovery Alert Notification */}
      {discoveryStatus && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl text-sm text-indigo-900 flex items-center gap-2">
          <Globe size={18} className="text-indigo-600 flex-shrink-0" />
          <span>{discoveryStatus}</span>
        </div>
      )}

      {/* KPIs Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-slate-900">{reviews.length}</p>
          <p className="text-xs text-slate-500 mt-1">Total avis</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-amber-500 flex items-center justify-center gap-1">
            {avgRating} {avgRating !== "—" && <Star size={18} fill="currentColor" />}
          </p>
          <p className="text-xs text-slate-500 mt-1">Note moyenne</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-emerald-600">{positiveCount}</p>
          <p className="text-xs text-slate-500 mt-1">Positifs 🟢</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-rose-600">{negativeCount}</p>
          <p className="text-xs text-slate-500 mt-1">Négatifs 🔴</p>
        </div>
      </div>

      {/* Sources Filter Pills */}
      {sources.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setActiveSource(null)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
              activeSource === null
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
            }`}
          >
            Tous les avis ({reviews.length})
          </button>
          {sources.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSource(s.id)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
                activeSource === s.id
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {s.name || s.source_type}
            </button>
          ))}
        </div>
      )}

      {/* Reviews List or Empty State */}
      {isLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <Loader size={32} className="animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">Chargement des avis...</p>
        </div>
      ) : filteredReviews.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare size={26} />
          </div>
          <h3 className="font-semibold text-slate-900 mb-1">Aucun avis synchronisé</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Cliquez sur <strong>« Détecter les avis réels »</strong> en haut pour aspirer automatiquement vos avis publics Trustpilot et rich snippets.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredReviews.map((rev) => (
            <div key={rev.id} className="bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-300 transition-colors shadow-sm">
              <div className="flex items-start justify-between gap-4 mb-2">
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm">{rev.author_name}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex text-amber-400">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          size={14}
                          fill={i < Math.round(rev.rating) ? "currentColor" : "none"}
                          className={i < Math.round(rev.rating) ? "text-amber-400" : "text-slate-200"}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-slate-400">
                      {rev.review_date ? new Date(rev.review_date).toLocaleDateString() : ""}
                    </span>
                  </div>
                </div>

                {rev.sentiment && (
                  <Badge variant={rev.sentiment === "positive" ? "success" : rev.sentiment === "negative" ? "critical" : "neutral"}>
                    {rev.sentiment === "positive" ? "Positif 🟢" : rev.sentiment === "negative" ? "Négatif 🔴" : "Neutre ⚪"}
                  </Badge>
                )}
              </div>

              <p className="text-sm text-slate-600 leading-relaxed mt-2">{rev.text}</p>
            </div>
          ))}
        </div>
      )}

      {/* Modal Add Source */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">Ajouter une source d'avis</h2>
              <button onClick={() => setShowAdd(false)} className="p-1 text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleAddSource} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Plateforme</label>
                <select
                  value={newSource.source_type}
                  onChange={(e) => setNewSource({ ...newSource, source_type: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                >
                  <option value="trustpilot">Trustpilot</option>
                  <option value="google">Google Business</option>
                  <option value="custom">Avis Site Direct</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Nom de la source</label>
                <input
                  type="text"
                  placeholder="Ex: Trustpilot Officiel"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">URL publique</label>
                <input
                  type="url"
                  placeholder="https://www.trustpilot.com/review/votresite.com"
                  value={newSource.url}
                  onChange={(e) => setNewSource({ ...newSource, url: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdd(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50 font-medium"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 font-medium shadow-sm"
                >
                  Enregistrer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Import */}
      {showImport && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">Importer des avis (CSV ou JSON)</h2>
              <button onClick={() => setShowImport(false)} className="p-1 text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleImport} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Fichier de données</label>
                <input
                  type="file"
                  accept=".csv, .json"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="w-full text-sm border p-2 rounded-lg"
                  required
                />
              </div>
              {importResult && (
                <p className="text-xs font-medium text-indigo-600">{importResult}</p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowImport(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50 font-medium"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 font-medium shadow-sm disabled:opacity-50"
                >
                  {importing ? "Importation..." : "Importer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Reviews;
