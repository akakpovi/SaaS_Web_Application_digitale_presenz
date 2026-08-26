import React, { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Card } from "../components/ui";
import { websiteService, scanService, Website, Scan } from "../services/websiteService";
import { RefreshCw, Settings, Check, Loader2, Bell, BellOff } from "lucide-react";
import api from "../services/api";
import { useLang } from "../context/LangContext";

// ─── Types ───────────────────────────────────────────────────────────────────

interface MonitoringConfig {
  id: number;
  website_id: number;
  website_domain: string;
  enabled: boolean;
  interval: string;
  last_scan_at: string | null;
  next_scan_at: string | null;
  consecutive_failures: number;
  escalation_level: number;
}

const INTERVALS = [
  { value: "5m",  label: "Every 5 minutes",  plan: "Business" },
  { value: "15m", label: "Every 15 minutes", plan: "Business" },
  { value: "30m", label: "Every 30 minutes", plan: "Pro" },
  { value: "1h",  label: "Every hour",       plan: "Pro" },
  { value: "6h",  label: "Every 6 hours",    plan: "Free" },
  { value: "24h", label: "Every 24 hours",   plan: "Free" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(d: string) {
  return new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function formatDateTime(d: string) {
  return new Date(d).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
function timeAgo(d: string) {
  const diff = Date.now() - new Date(d).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "Just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
function timeUntil(d: string) {
  const diff = new Date(d).getTime() - Date.now();
  if (diff <= 0) return "Soon";
  const m = Math.floor(diff / 60000);
  if (m < 60) return `in ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `in ${h}h`;
  return `in ${Math.floor(h / 24)}d`;
}

// ─── Composant config panel ───────────────────────────────────────────────────

function MonitoringConfigPanel({
  config,
  onSaved,
}: {
  config: MonitoringConfig;
  onSaved: (updated: MonitoringConfig) => void;
}) {
  const [enabled, setEnabled] = useState(config.enabled);
  const [interval, setInterval] = useState(config.interval);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  // Sync si le site change
  useEffect(() => {
    setEnabled(config.enabled);
    setInterval(config.interval);
    setSaved(false);
    setError("");
  }, [config.id]);

  const isDirty = enabled !== config.enabled || interval !== config.interval;

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const { data } = await api.patch<MonitoringConfig>(
        `/monitoring/websites/${config.website_id}/`,
        { enabled, interval },
      );
      onSaved(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: any) {
      const detail = err?.response?.data?.detail
        ?? err?.response?.data?.interval?.[0]
        ?? "Failed to save configuration.";
      setError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerScan = async () => {
    try {
      await api.post(`/monitoring/websites/${config.website_id}/scan/`);
    } catch {
      // Ignore — le scan sera lancé en arrière-plan
    }
  };

  return (
    <Card className="p-5 mb-6">
      <div className="flex items-center gap-2 mb-5">
        <Settings size={16} className="text-slate-400" />
        <h2 className="font-bold text-slate-900">Monitoring configuration</h2>
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        {/* Enable / Disable */}
        <div>
          <p className="text-sm font-medium text-slate-700 mb-3">Monitoring status</p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setEnabled(!enabled)}
              className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
                enabled ? "bg-indigo-600" : "bg-slate-200"
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
                  enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span className={`text-sm font-medium ${enabled ? "text-emerald-600" : "text-slate-400"}`}>
              {enabled ? (
                <span className="flex items-center gap-1"><Bell size={14} /> Active</span>
              ) : (
                <span className="flex items-center gap-1"><BellOff size={14} /> Paused</span>
              )}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            {enabled
              ? "Automatic scans are running."
              : "No automatic scans while paused."}
          </p>
        </div>

        {/* Interval */}
        <div>
          <p className="text-sm font-medium text-slate-700 mb-3">Scan interval</p>
          <select
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {INTERVALS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label} ({opt.plan})
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-400 mt-2">
            Available intervals depend on your plan.
          </p>
        </div>
      </div>

      {/* Stats ligne */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-5 border-t border-slate-100">
        {[
          {
            label: "Last scan",
            value: config.last_scan_at ? timeAgo(config.last_scan_at) : "Never",
          },
          {
            label: "Next scan",
            value: config.next_scan_at ? timeUntil(config.next_scan_at) : "—",
          },
          {
            label: "Consecutive failures",
            value: String(config.consecutive_failures),
          },
          {
            label: "Escalation level",
            value: config.escalation_level === 0
              ? "✅ Normal"
              : config.escalation_level === 1
              ? "🟠 Warning"
              : "🔴 Critical",
          },
        ].map((s) => (
          <div key={s.label} className="bg-slate-50 rounded-xl p-3">
            <p className="text-xs text-slate-500 mb-1">{s.label}</p>
            <p className="text-sm font-semibold text-slate-800">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 mt-5 flex-wrap">
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
            isDirty
              ? "bg-indigo-600 text-white hover:bg-indigo-700"
              : "bg-slate-100 text-slate-400 cursor-not-allowed"
          }`}
        >
          {saving ? (
            <Loader2 size={14} className="animate-spin" />
          ) : saved ? (
            <Check size={14} />
          ) : null}
          {saving ? "Saving…" : saved ? "Saved" : "Save configuration"}
        </button>

        <button
          onClick={handleTriggerScan}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
        >
          <RefreshCw size={14} />
          Trigger scan now
        </button>

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
      </div>
    </Card>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────

export default function Monitoring() {
  const { t } = useLang();
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Chargement initial
  useEffect(() => {
    websiteService.list().then((sites) => {
      setWebsites(sites);
      if (sites.length > 0) setSelectedSite(sites[0].id);
      setIsLoading(false);
    }).catch(() => setIsLoading(false));
  }, []);

  // Chargement scans + config quand le site change
  const loadSiteData = useCallback(async (siteId: number) => {
    setIsRefreshing(true);
    try {
      const [scansData, configData] = await Promise.all([
        scanService.list(siteId),
        api.get<MonitoringConfig>(`/monitoring/websites/${siteId}/`).then((r) => r.data),
      ]);
      setScans(scansData);
      setConfig(configData);
    } catch {
      // Config peut ne pas exister encore
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedSite) return;
    loadSiteData(selectedSite);
  }, [selectedSite, loadSiteData]);

  // Données graphique
  const chartData = scans
    .filter((s) => s.completed_at)
    .slice(0, 48)
    .reverse()
    .map((s) => ({
      time: formatDate(s.completed_at!),
      score: s.health_score ?? 0,
      status: s.health_status === "critical" ? 0 : 100,
    }));

  const completedScans = scans.filter((s) => s.status === "completed");
  const uptimePct =
    completedScans.length > 0
      ? (
          (completedScans.filter((s) => s.health_status !== "critical").length /
            completedScans.length) *
          100
        ).toFixed(2)
      : "—";

  const lastScan = scans[0];
  const currentStatus = lastScan?.health_status ?? "neutral";
  const statusIcon =
    currentStatus === "healthy" ? "🟢"
    : currentStatus === "warning" ? "🟠"
    : currentStatus === "critical" ? "🔴"
    : "⚪";

  // Timeline
  const timeline = scans.slice(0, 15).map((s) => ({
    time: s.completed_at
      ? formatDateTime(s.completed_at)
      : formatDateTime(s.created_at),
    event:
      s.status === "completed"
        ? s.health_status === "critical"
          ? "🔴 Issue detected"
          : s.health_status === "warning"
          ? "🟠 Warning detected"
          : "✅ Scan completed"
        : s.status === "failed"
        ? "❌ Scan failed"
        : "⏳ Scan queued",
    detail:
      s.status === "completed"
        ? `Health score: ${s.health_score ?? "—"}/100`
        : s.status === "failed"
        ? "Scan could not complete"
        : "Waiting for worker",
    type:
      s.health_status === "critical"
        ? "incident"
        : s.health_status === "warning"
        ? "warning"
        : s.status === "failed"
        ? "incident"
        : "check",
  }));

  const selectedWebsite = websites.find((w) => w.id === selectedSite);

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Monitoring</h1>
          <p className="text-slate-500 mt-1">
            Configure and track automatic monitoring for your websites.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {websites.length > 1 && (
            <select
              value={selectedSite ?? ""}
              onChange={(e) => setSelectedSite(Number(e.target.value))}
              className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
              {websites.map((w) => (
                <option key={w.id} value={w.id}>{w.domain}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => selectedSite && loadSiteData(selectedSite)}
            disabled={isRefreshing}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw
              size={16}
              className={`text-slate-500 ${isRefreshing ? "animate-spin" : ""}`}
            />
          </button>
        </div>
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
          {/* Configuration panel */}
          {config && (
            <MonitoringConfigPanel
              config={config}
              onSaved={(updated) => setConfig(updated)}
            />
          )}

          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[
              {
                label: t("monitoring.title"),
                value: config?.enabled ? "Active" : "Paused",
                sub: config
                  ? `Every ${INTERVALS.find((i) => i.value === config.interval)?.label.toLowerCase().replace("every ", "") ?? config.interval}`
                  : "—",
                icon: config?.enabled ? "🟢" : "⏸️",
              },
              {
                label: "Current status",
                value:
                  currentStatus === "healthy"
                    ? "Online"
                    : currentStatus === "critical"
                    ? "Offline"
                    : currentStatus === "warning"
                    ? "Warning"
                    : "Unknown",
                sub: lastScan?.completed_at
                  ? timeAgo(lastScan.completed_at)
                  : "No scan yet",
                icon: statusIcon,
              },
              {
                label: "Total scans",
                value: String(scans.length),
                sub: `${completedScans.length} completed`,
                icon: "📊",
              },
              {
                label: "Uptime rate",
                value: uptimePct === "—" ? "—" : `${uptimePct}%`,
                sub: "Based on scan history",
                icon: "📈",
              },
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

          {/* Graphique */}
          <Card className="p-5 mb-6">
            <div className="mb-4">
              <h2 className="font-bold text-slate-900">Status history</h2>
              <p className="text-sm text-slate-500">
                {selectedWebsite?.domain} · Health score over time
              </p>
            </div>
            {chartData.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
                No scan data yet — run a scan to see the chart.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart
                  data={chartData}
                  margin={{ top: 5, right: 5, bottom: 5, left: -10 }}
                >
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0" }}
                    formatter={(v) => [`${v}/100`, "Score"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    fill="url(#scoreGrad)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Timeline */}
          <Card className="p-5">
            <h2 className="font-bold text-slate-900 mb-5">Scan timeline</h2>
            {timeline.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-4">
                No scan history yet.
              </p>
            ) : (
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-px bg-slate-200" />
                <div className="space-y-3">
                  {timeline.map((event, i) => (
                    <div key={i} className="relative flex items-start gap-4 pl-10">
                      <div
                        className={`absolute left-2.5 top-2 w-3 h-3 rounded-full border-2 ${
                          event.type === "incident"
                            ? "bg-red-100 border-red-500"
                            : event.type === "warning"
                            ? "bg-amber-100 border-amber-500"
                            : "bg-slate-100 border-slate-300"
                        }`}
                      />
                      <div className="flex-1 bg-slate-50 rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between gap-4 flex-wrap">
                          <p className="text-sm font-medium text-slate-900">
                            {event.event}
                          </p>
                          <span className="text-xs text-slate-400 flex-shrink-0">
                            {event.time}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {event.detail}
                        </p>
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
