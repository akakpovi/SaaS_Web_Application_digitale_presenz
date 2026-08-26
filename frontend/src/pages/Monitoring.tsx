import React, { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, Tabs } from "../components/ui";
import { websiteService, scanService, Website, Scan } from "../services/websiteService";
import { RefreshCw } from "lucide-react";

function formatDate(d: string) {
  return new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(d: string) {
  return new Date(d).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function timeAgo(d: string) {
  const diff = Date.now() - new Date(d).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function Monitoring() {
  const [period, setPeriod] = useState("24H");
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    websiteService.list().then(sites => {
      setWebsites(sites);
      if (sites.length > 0) setSelectedSite(sites[0].id);
      setIsLoading(false);
    }).catch(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedSite) return;
    scanService.list(selectedSite).then(setScans).catch(() => {});
  }, [selectedSite]);

  // Construire les données du graphique uptime à partir des scans réels
  const chartData = scans
    .filter(s => s.completed_at)
    .slice(0, 48)
    .reverse()
    .map(s => ({
      time: formatDate(s.completed_at!),
      value: s.health_status === 'critical' ? 0 : 100,
    }));

  const completedScans = scans.filter(s => s.status === 'completed');
  const uptimePct = completedScans.length > 0
    ? ((completedScans.filter(s => s.health_status !== 'critical').length / completedScans.length) * 100).toFixed(2)
    : '—';

  const lastScan = scans[0];
  const currentStatus = lastScan?.health_status ?? 'neutral';

  const statusIcon = currentStatus === 'healthy' ? '🟢'
    : currentStatus === 'warning' ? '🟠'
    : currentStatus === 'critical' ? '🔴' : '⚪';

  // Timeline des scans récents
  const timeline = scans.slice(0, 10).map(s => ({
    time: s.completed_at ? formatDateTime(s.completed_at) : formatDateTime(s.created_at),
    event: s.status === 'completed'
      ? (s.health_status === 'critical' ? '🔴 Issue detected' : s.health_status === 'warning' ? '🟠 Warning detected' : '✅ Scan completed')
      : s.status === 'failed' ? '❌ Scan failed' : '⏳ Scan queued',
    detail: s.status === 'completed'
      ? `Health score: ${s.health_score ?? '—'}/100`
      : s.status === 'failed' ? 'Scan could not complete' : 'Waiting for worker',
    type: s.health_status === 'critical' ? 'incident'
      : s.health_status === 'warning' ? 'warning'
      : s.status === 'failed' ? 'incident' : 'check',
  }));

  const selectedWebsite = websites.find(w => w.id === selectedSite);

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Monitoring</h1>
          <p className="text-slate-500 mt-1">Automatic monitoring is active for all your websites.</p>
        </div>
        {websites.length > 1 && (
          <select
            value={selectedSite ?? ''}
            onChange={e => setSelectedSite(Number(e.target.value))}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {websites.map(w => <option key={w.id} value={w.id}>{w.domain}</option>)}
          </select>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : websites.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-4xl mb-4">🌐</p>
          <p className="font-semibold text-slate-900 mb-1">No websites yet</p>
          <p className="text-sm text-slate-500">Add a website to start monitoring.</p>
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {[
              { label: "Monitoring status", value: "Active", sub: `${websites.length} website${websites.length > 1 ? 's' : ''}`, icon: "🟢" },
              { label: "Current status", value: currentStatus === 'healthy' ? 'Online' : currentStatus === 'critical' ? 'Offline' : 'Warning', sub: lastScan?.completed_at ? timeAgo(lastScan.completed_at) : 'No scan yet', icon: statusIcon },
              { label: "Total scans", value: String(scans.length), sub: `${completedScans.length} completed`, icon: "📊" },
              { label: "Uptime rate", value: uptimePct === '—' ? '—' : `${uptimePct}%`, sub: "Based on scan history", icon: "📈" },
            ].map((s) => (
              <Card key={s.label} className="p-4">
                <p className="text-xs text-slate-500 mb-1">{s.label}</p>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{s.icon}</span>
                  <span className="font-bold text-slate-900">{s.value}</span>
                </div>
                <p className="text-xs text-slate-400 mt-1">{s.sub}</p>
              </Card>
            ))}
          </div>

          {/* Uptime chart */}
          <Card className="p-5 mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
              <div>
                <h2 className="font-bold text-slate-900">Status history</h2>
                <p className="text-sm text-slate-500">{selectedWebsite?.domain} · Based on scan results</p>
              </div>
            </div>
            {chartData.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
                No scan data yet — run a scan to see the chart.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                  <defs>
                    <linearGradient id="uptimeGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0" }}
                    formatter={(v) => [`${(v as number).toFixed(0)}%`, "Status"]}
                  />
                  <Area type="stepAfter" dataKey="value" stroke="#4f46e5" strokeWidth={2} fill="url(#uptimeGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Timeline */}
          <Card className="p-5">
            <h2 className="font-bold text-slate-900 mb-5">Scan timeline</h2>
            {timeline.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-4">No scan history yet.</p>
            ) : (
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-px bg-slate-200" />
                <div className="space-y-4">
                  {timeline.map((event, i) => (
                    <div key={i} className="relative flex items-start gap-4 pl-10">
                      <div className={`absolute left-2.5 top-2 w-3 h-3 rounded-full border-2 ${
                        event.type === 'incident' ? 'bg-red-100 border-red-500' :
                        event.type === 'recovery' ? 'bg-emerald-100 border-emerald-500' :
                        event.type === 'warning' ? 'bg-amber-100 border-amber-500' :
                        'bg-slate-100 border-slate-300'
                      }`} />
                      <div className="flex-1 bg-slate-50 rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between gap-4 flex-wrap">
                          <p className="text-sm font-medium text-slate-900">{event.event}</p>
                          <span className="text-xs text-slate-400 flex-shrink-0">{event.time}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{event.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
