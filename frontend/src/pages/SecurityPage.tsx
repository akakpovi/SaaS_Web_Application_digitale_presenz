import React, { useEffect, useState } from "react";
import { 
  Shield, ShieldAlert, ShieldCheck, Play, 
  AlertTriangle, Loader, Lock, Server, Bug, CheckCircle2 
} from "lucide-react";
import api from "../services/api";
import { Badge } from "../components/ui";

interface Website {
  id: number;
  domain: string;
  name: string;
}

interface Incident {
  id: string;
  incident_type: "malware" | "open_port" | "waf_missing" | "vulnerability";
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  resolved: boolean;
  detected_at: string;
}

export const SecurityPage: React.FC = () => {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<number | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

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
      const res = await api.get(`/websites/${siteId}/security/incidents/`);
      setIncidents(res.data.results || res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunScan = async () => {
    if (!selectedWebsiteId) return;
    setScanning(true);
    try {
      await api.post(`/websites/${selectedWebsiteId}/security/scan/`);
      setTimeout(() => {
        loadData(selectedWebsiteId);
        setScanning(false);
      }, 2500);
    } catch (e) {
      console.error(e);
      setScanning(false);
    }
  };

  const criticalCount = incidents.filter((i) => i.severity === "critical" && !i.resolved).length;
  const highCount = incidents.filter((i) => i.severity === "high" && !i.resolved).length;
  const resolvedCount = incidents.filter((i) => i.resolved).length;

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Surveillance & Sécurité Avancée</h1>
          <p className="text-slate-500 text-sm mt-1">
            Détection de ports exposés, contrôle malware/phishing et protection pare-feu (WAF).
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
            onClick={handleRunScan}
            disabled={scanning || !selectedWebsiteId}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors disabled:opacity-50"
          >
            {scanning ? <Loader size={16} className="animate-spin" /> : <Play size={16} />}
            {scanning ? "Scan en cours..." : "Lancer un scan de sécurité"}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-slate-900">{incidents.length}</p>
          <p className="text-xs text-slate-500 mt-1">Total vérifications</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-rose-600">{criticalCount}</p>
          <p className="text-xs text-slate-500 mt-1">Critiques</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-amber-500">{highCount}</p>
          <p className="text-xs text-slate-500 mt-1">Élevés</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-emerald-600">{resolvedCount}</p>
          <p className="text-xs text-slate-500 mt-1">Résolus / Sains</p>
        </div>
      </div>

      {/* Incidents List */}
      {isLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <Loader size={32} className="animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm text-slate-500">Vérification de la sécurité en cours...</p>
        </div>
      ) : incidents.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <div className="w-14 h-14 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShieldCheck size={28} />
          </div>
          <h3 className="font-semibold text-slate-900 mb-1">Aucune menace détectée</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
            Votre domaine est protégé. Lancez un scan régulier pour vérifier l'absence de ports non sécurisés ou de listes de blocage.
          </p>
          <button
            onClick={handleRunScan}
            disabled={scanning}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            Lancer un scan maintenant
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => (
            <div
              key={inc.id}
              className="bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-300 transition-colors shadow-sm flex items-start justify-between gap-4"
            >
              <div className="flex items-start gap-3.5">
                <div className={`p-2.5 rounded-xl ${
                  inc.severity === "critical" ? "bg-rose-50 text-rose-600" :
                  inc.severity === "high" ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-600"
                }`}>
                  {inc.incident_type === "open_port" ? <Server size={18} /> :
                   inc.incident_type === "malware" ? <Bug size={18} /> : <Lock size={18} />}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm">{inc.title || inc.incident_type}</h4>
                  <p className="text-xs text-slate-500 mt-1">{inc.description}</p>
                  <p className="text-xs text-slate-400 mt-2">
                    Détecté le {new Date(inc.detected_at).toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <Badge variant={
                  inc.severity === "critical" ? "critical" :
                  inc.severity === "high" ? "warning" : "neutral"
                }>
                  {inc.severity.toUpperCase()}
                </Badge>
                {inc.resolved && (
                  <Badge variant="success">✓ Résolu</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SecurityPage;
