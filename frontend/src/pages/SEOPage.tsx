import React, { useEffect, useState } from "react";
import { 
  Search, Globe, Play, CheckCircle2, AlertTriangle, 
  XCircle, Plus, Loader, RefreshCw, BarChart2, FileText, Smartphone 
} from "lucide-react";
import api from "../services/api";
import { Badge } from "../components/ui";

interface Website {
  id: number;
  domain: string;
  name: string;
}

interface SEOAudit {
  id: string;
  overall_score: number;
  technical_score: number;
  content_score: number;
  mobile_score: number;
  meta_tags: Record<string, any>;
  robots_txt: string;
  sitemap: string;
  issues: Array<{ type: string; message: string; severity?: string }>;
  created_at: string;
}

interface Keyword {
  id: number;
  term: string;
  country: string;
  position: number | null;
  previous_position: number | null;
  search_volume: number | null;
  updated_at: string;
}

export const SEOPage: React.FC = () => {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<number | null>(null);
  const [audit, setAudit] = useState<SEOAudit | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "keywords">("overview");

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

  const loadData = async (siteId: number) => {
    setIsLoading(true);
    try {
      const [auditsRes, kwRes] = await Promise.all([
        api.get(`/websites/${siteId}/seo/audits/`),
        api.get(`/websites/${siteId}/seo/keywords/`),
      ]);
      const auditList = auditsRes.data.results || auditsRes.data || [];
      setAudit(auditList[0] || null);
      setKeywords(kwRes.data.results || kwRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunAudit = async () => {
    if (!selectedWebsiteId) return;
    setRunning(true);
    try {
      await api.post(`/websites/${selectedWebsiteId}/seo/audits/run/`);
      // Pause courte pour laisser le temps au scan de finir
      setTimeout(() => {
        loadData(selectedWebsiteId);
        setRunning(false);
      }, 2500);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
  };

  const handleAddKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyword.trim() || !selectedWebsiteId) return;
    try {
      await api.post(`/websites/${selectedWebsiteId}/seo/keywords/`, {
        term: newKeyword.trim(),
        country: "FR",
      });
      setNewKeyword("");
      loadData(selectedWebsiteId);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Audit & Optimisation SEO</h1>
          <p className="text-slate-500 text-sm mt-1">
            Analyse technique, suivi des mots-clés, conformité mobile et balisage méta.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {websites.length > 1 && (
            <select
              value={selectedWebsiteId || ""}
              onChange={(e) => setSelectedWebsiteId(Number(e.target.value))}
              className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {websites.map((w) => (
                <option key={w.id} value={w.id}>{w.domain}</option>
              ))}
            </select>
          )}

          <button
            onClick={handleRunAudit}
            disabled={running || !selectedWebsiteId}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            {running ? <Loader size={16} className="animate-spin" /> : <Play size={16} />}
            {running ? "Audit en cours..." : "Lancer un audit SEO"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "overview"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Vue générale & Technique
        </button>
        <button
          onClick={() => setActiveTab("keywords")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "keywords"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Mots-clés suivis ({keywords.length})
        </button>
      </div>

      {isLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <Loader size={32} className="animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">Chargement des données SEO...</p>
        </div>
      ) : activeTab === "overview" ? (
        !audit ? (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
            <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Search size={26} />
            </div>
            <h3 className="font-semibold text-slate-900 mb-1">Aucun audit SEO enregistré</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
              Lancez votre premier audit pour analyser l'état de santé technique, la conformité mobile et le balisage de votre site.
            </p>
            <button
              onClick={handleRunAudit}
              disabled={running}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
            >
              Lancer l'audit maintenant
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Score Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
                <p className="text-3xl font-black text-indigo-600">{audit.overall_score}/100</p>
                <p className="text-xs text-slate-500 mt-1">Score Global</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
                <p className="text-3xl font-black text-slate-900">{audit.technical_score}/100</p>
                <p className="text-xs text-slate-500 mt-1">Technique</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
                <p className="text-3xl font-black text-slate-900">{audit.content_score}/100</p>
                <p className="text-xs text-slate-500 mt-1">Contenu / Méta</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
                <p className="text-3xl font-black text-slate-900">{audit.mobile_score}/100</p>
                <p className="text-xs text-slate-500 mt-1">Mobile & Vitesse</p>
              </div>
            </div>

            {/* Technical checklist */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900 text-sm mb-3 flex items-center gap-2">
                  <FileText size={16} className="text-indigo-600" /> Fichiers d'indexation
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-600">Robots.txt</span>
                    <Badge variant={audit.robots_txt === "valid" ? "success" : "warning"}>
                      {audit.robots_txt}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-slate-600">Sitemap XML</span>
                    <Badge variant={audit.sitemap === "valid" ? "success" : "warning"}>
                      {audit.sitemap}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900 text-sm mb-3 flex items-center gap-2">
                  <Smartphone size={16} className="text-indigo-600" /> Balises Méta
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-600">Balise Title</span>
                    <span className="font-medium text-slate-900 truncate max-w-[200px]">
                      {audit.meta_tags?.title || "Non définie"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-slate-600">Meta Description</span>
                    <span className="font-medium text-slate-900 truncate max-w-[200px]">
                      {audit.meta_tags?.description || "Non définie"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Issues */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-slate-900 text-sm mb-3">Recommandations & Problèmes détectés</h3>
              {audit.issues && audit.issues.length > 0 ? (
                <div className="space-y-2">
                  {audit.issues.map((issue, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                      <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
                      <div className="text-sm">
                        <p className="font-medium text-slate-800">{issue.type || "Avertissement"}</p>
                        <p className="text-slate-500 text-xs mt-0.5">{issue.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-emerald-600 text-sm py-2">
                  <CheckCircle2 size={16} />
                  <span>Aucun problème critique détecté sur ce domaine !</span>
                </div>
              )}
            </div>
          </div>
        )
      ) : (
        /* Keywords Tab */
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <form onSubmit={handleAddKeyword} className="flex gap-2">
              <input
                type="text"
                placeholder="Ajouter un mot-clé à suivre (ex: présence digitale saas)"
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                className="flex-1 px-3 py-2 border rounded-lg text-sm"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 font-medium flex items-center gap-2 shadow-sm"
              >
                <Plus size={16} /> Suivre
              </button>
            </form>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            {keywords.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                Aucun mot-clé suivi pour l'instant. Ajoutez votre premier mot-clé ci-dessus.
              </div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-100 text-xs font-semibold text-slate-600">
                  <tr>
                    <th className="p-3.5">Mot-clé</th>
                    <th className="p-3.5">Pays</th>
                    <th className="p-3.5 text-center">Position Google</th>
                    <th className="p-3.5 text-right">Dernière mise à jour</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {keywords.map((kw) => (
                    <tr key={kw.id} className="hover:bg-slate-50">
                      <td className="p-3.5 font-medium text-slate-900">{kw.term}</td>
                      <td className="p-3.5 text-slate-500">{kw.country}</td>
                      <td className="p-3.5 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded font-bold text-indigo-700 bg-indigo-50">
                          #{kw.position ?? "—"}
                        </span>
                      </td>
                      <td className="p-3.5 text-right text-xs text-slate-400">
                        {new Date(kw.updated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SEOPage;
