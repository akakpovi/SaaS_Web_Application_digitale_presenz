import React, { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, Button, ScoreRing } from "../components/ui";
import { Download, TrendingUp, TrendingDown, RefreshCw } from "lucide-react";
import api from "../services/api";
import { useTranslation } from "react-i18next";
import { websiteService, Website } from "../services/websiteService";

interface Report {
  id: string;
  period: string;
  period_start: string;
  period_end: string;
  status: string;
  current_score: number | null;
  previous_score: number | null;
  score_change: number | null;
  score_trend: string;
  check_breakdown: Record<string, any>;
  improvements: string[];
  problems: string[];
  recommendations: string[];
  total_scans: number;
  generated_at: string;
  website: number;
}

function formatMonth(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

export default function Reports() {
  const { t } = useTranslation();
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    websiteService.list().then(sites => {
      setWebsites(sites);
      if (sites.length > 0) setSelectedSite(sites[0].id);
    }).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedSite) return;
    loadReports(selectedSite);
  }, [selectedSite]);

  const loadReports = async (siteId: number) => {
    try {
      const { data } = await api.get(`/reports/?website_id=${siteId}`);
      setReports(data.results ?? data);
    } catch { setReports([]); }
  };

  const generateReport = async () => {
    if (!selectedSite) return;
    setIsGenerating(true);
    setError('');
    try {
      const now = new Date();
      const periodStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
      await api.post('/reports/generate/', {
        website_id: selectedSite,
        period: 'monthly',
        period_start: periodStart,
      });
      setTimeout(() => {
        loadReports(selectedSite);
        setIsGenerating(false);
      }, 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to generate report.');
      setIsGenerating(false);
    }
  };

  const current = reports[0];

  const chartData = reports
    .slice(0, 6)
    .reverse()
    .map(r => ({
      name: new Date(r.period_start).toLocaleDateString('en-US', { month: 'short' }),
      score: r.current_score ?? 0,
    }));

  const CATEGORY_LABELS: Record<string, string> = {
    website: 'Website availability',
    ssl: 'SSL certificate',
    dns: 'DNS configuration',
    email_security: 'Email security',
    security_headers: 'Security headers',
    performance: 'Performance',
  };

  const CATEGORY_MAX: Record<string, number> = {
    website: 20, ssl: 20, dns: 15,
    email_security: 15, security_headers: 15, performance: 15,
  };

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
          <p className="text-slate-500 mt-1">Your monthly digital presence reports.</p>
        </div>
        <div className="flex items-center gap-3">
          {websites.length > 1 && (
            <select value={selectedSite ?? ''} onChange={e => setSelectedSite(Number(e.target.value))}
              className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
              {websites.map(w => <option key={w.id} value={w.id}>{w.domain}</option>)}
            </select>
          )}
          <Button size="sm" onClick={generateReport} disabled={isGenerating || !selectedSite}>
            <RefreshCw size={14} className={isGenerating ? 'animate-spin' : ''} />
            {isGenerating ? 'Generating...' : 'Generate report'}
          </Button>
        </div>
      </div>

      {error && <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">{error}</div>}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !current ? (
        <Card className="p-12 text-center">
          <p className="text-4xl mb-4">📊</p>
          <p className="font-semibold text-slate-900 mb-1">No reports yet</p>
          <p className="text-sm text-slate-500 mb-4">Generate your first monthly report to see insights.</p>
          <Button onClick={generateReport} disabled={isGenerating || !selectedSite}>
            {isGenerating ? 'Generating...' : 'Generate first report'}
          </Button>
        </Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Current report */}
          <div className="lg:col-span-2">
            <Card className="p-6">
              <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
                    {current.period === 'monthly' ? 'Monthly Report' : 'Weekly Report'}
                  </p>
                  <h2 className="text-xl font-bold text-slate-900">{formatMonth(current.period_start)}</h2>
                </div>
                <span className={`px-3 py-1 text-xs font-bold rounded-full ${current.status === 'generated' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                  {current.status}
                </span>
              </div>

              <div className="flex items-center gap-8 mb-6 pb-6 border-b border-slate-100">
                <ScoreRing score={current.current_score ?? 0} size={100} />
                <div>
                  <p className="text-sm text-slate-500 mb-2">Overall health</p>
                  {current.score_change !== null && (
                    <div className="flex items-center gap-2 mb-1">
                      {current.score_change >= 0
                        ? <TrendingUp size={16} className="text-emerald-500" />
                        : <TrendingDown size={16} className="text-red-500" />}
                      <span className={`font-semibold ${current.score_change >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {current.score_change >= 0 ? '+' : ''}{current.score_change} points vs last month
                      </span>
                    </div>
                  )}
                  <p className="text-sm text-slate-500">{current.total_scans} scans this period</p>
                </div>
              </div>

              {/* Score breakdown */}
              {current.check_breakdown && Object.keys(current.check_breakdown).length > 0 && (
                <div className="space-y-4 mb-6">
                  <h3 className="font-semibold text-slate-800">Score breakdown</h3>
                  {Object.entries(current.check_breakdown).map(([key, val]: [string, any]) => {
                    const max = CATEGORY_MAX[key] ?? 15;
                    const score = Math.round((val.avg_score ?? 0));
                    const isHealthy = score >= max * 0.9;
                    return (
                      <div key={key} className="flex items-center gap-4">
                        <span className="text-sm text-slate-600 w-44 flex-shrink-0">{CATEGORY_LABELS[key] ?? key}</span>
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${isHealthy ? 'bg-emerald-500' : 'bg-amber-500'}`}
                            style={{ width: `${Math.min((score / max) * 100, 100)}%` }} />
                        </div>
                        <span className="text-sm font-semibold text-slate-800 tabular-nums w-10 text-right">{score}/{max}</span>
                        <span>{isHealthy ? '🟢' : '🟠'}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Recommendations */}
              {current.recommendations && current.recommendations.length > 0 && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                  <p className="text-sm font-semibold text-amber-800 mb-2">Recommended actions</p>
                  <ul className="space-y-1">
                    {current.recommendations.slice(0, 5).map((rec, i) => (
                      <li key={i} className="text-sm text-amber-700">• {rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          </div>

          {/* Sidebar */}
          <div className="flex flex-col gap-4">
            {chartData.length > 0 && (
              <Card className="p-5">
                <h3 className="font-semibold text-slate-900 mb-4">Score history</h3>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 12 }}
                      formatter={(v) => [v as number, "Score"]} />
                    <Bar dataKey="score" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}

            <Card className="overflow-hidden">
              <div className="p-4 pb-0">
                <h3 className="font-semibold text-slate-900">Past reports</h3>
              </div>
              <div className="divide-y divide-slate-100">
                {reports.map((report) => (
                  <div key={report.id} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{formatMonth(report.period_start)}</p>
                      {report.score_change !== null && (
                        <div className="flex items-center gap-1 mt-0.5">
                          {report.score_change >= 0
                            ? <TrendingUp size={10} className="text-emerald-500" />
                            : <TrendingDown size={10} className="text-red-500" />}
                          <span className={`text-xs ${report.score_change >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {report.score_change >= 0 ? '+' : ''}{report.score_change}
                          </span>
                        </div>
                      )}
                    </div>
                    <span className={`text-lg font-black ${(report.current_score ?? 0) >= 80 ? 'text-emerald-600' : 'text-amber-600'}`}>
                      {report.current_score ?? '—'}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
