import { useModalQueue } from '../context/ModalQueueContext';
import React, { useState, useEffect } from "react";
import { Card, Button, Tabs } from "../components/ui";
import { Link } from "react-router-dom";
import { alertService, Alert } from "../services/alertService";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

function severityIcon(severity: string) {
  if (severity === 'critical') return '🔴';
  if (severity === 'warning') return '🟠';
  return '🔵';
}
function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function Alerts() {
  const { t } = useTranslation();
  const { triggerPWAPrompt } = useModalQueue();
  const [filter, setFilter] = useState("All");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    try { const data = await alertService.list(); setAlerts(data); }
    catch { } finally { setIsLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const handleAcknowledge = async (id: string) => {
    setActionLoading(id);
    try { const u = await alertService.acknowledge(id); setAlerts(prev => prev.map(a => a.id === id ? u : a)); }
    finally { setActionLoading(null); }
  };
  const handleResolve = async (id: string) => {
    setActionLoading(id);
    try { const u = await alertService.resolve(id); setAlerts(prev => prev.map(a => a.id === id ? u : a)); }
    finally { setActionLoading(null); }
  };

  const filtered = alerts.filter(a => {
    if (filter === 'All') return true;
    if (filter === 'Critical') return a.severity === 'critical';
    if (filter === 'Warning') return a.severity === 'warning';
    if (filter === 'Resolved') return a.status === 'resolved';
    return true;
  });

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("alerts.title")}</h1>
          <p className="text-slate-500 mt-1">{t("alerts.subtitle")}</p>
        </div>
        <button onClick={load} disabled={isLoading} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
          <RefreshCw size={16} className={`text-slate-500 ${isLoading ? 'animate-spin' : ''}`}/>
        </button>
      </div>

      <div className="mb-6">
        <Tabs tabs={["All","Critical","Warning","Resolved"]} active={filter} onChange={setFilter}/>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"/>
        </div>
      ) : filtered.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-4xl mb-4">🎉</p>
          <p className="font-semibold text-slate-900 mb-1">{t("alerts.no_alerts")}</p>
          <p className="text-sm text-slate-500">{t("alerts.all_clear")}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((alert) => (
            <Card key={alert.id} className="p-5">
              <div className="flex items-start gap-4">
                <span className="text-2xl flex-shrink-0 mt-0.5">
                  {alert.status === 'resolved' ? '✅' : severityIcon(alert.severity)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                      <p className="font-semibold text-slate-900">{alert.title}</p>
                      {alert.website_domain && <p className="text-sm text-indigo-600 mt-0.5">{alert.website_domain}</p>}
                    </div>
                    <span className="text-xs text-slate-400 flex-shrink-0">{timeAgo(alert.created_at)}</span>
                  </div>
                  <p className="text-sm text-slate-600 mt-2">{alert.message}</p>
                  {alert.status === 'firing' && (
                    <div className="flex items-center gap-2 mt-4">
                      <Link to={`/app/websites/${alert.website_id}`}>
                        <Button size="sm">{t("alerts.view")}</Button>
                      </Link>
                      <Button size="sm" variant="outline" onClick={() => handleAcknowledge(alert.id)} disabled={actionLoading === alert.id}>
                        {t("alerts.acknowledge")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleResolve(alert.id)} disabled={actionLoading === alert.id}>
                        {t("alerts.resolve")}
                      </Button>
                    </div>
                  )}
                  {alert.status === 'acknowledged' && (
                    <div className="flex items-center gap-2 mt-4">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-200">👁 Acknowledged</span>
                      <Button size="sm" variant="ghost" onClick={() => handleResolve(alert.id)} disabled={actionLoading === alert.id}>
                        {t("alerts.resolve")}
                      </Button>
                    </div>
                  )}
                  {alert.status === 'resolved' && (
                    <span className="inline-flex items-center gap-1.5 mt-3 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full border border-emerald-200">
                      ✅ {t("alerts.resolve")}d
                    </span>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
