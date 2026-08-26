import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, RefreshCw, Settings, ChevronDown } from "lucide-react";
import { Card, StatusBadge, ScoreRing, Button } from "../components/ui";
import { websiteService, scanService, Website, Scan, CheckResult } from "../services/websiteService";

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${pct === 100 ? "bg-emerald-500" : pct >= 70 ? "bg-amber-500" : pct > 0 ? "bg-red-500" : "bg-slate-200"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

const CATEGORY_META: Record<string, { title: string; max: number | null }> = {
  website:          { title: "Website availability", max: 20 },
  ssl:              { title: "SSL certificate",       max: 20 },
  dns:              { title: "DNS configuration",     max: 15 },
  email_security:   { title: "Email security",        max: 15 },
  security_headers: { title: "Security headers",      max: 15 },
  performance:      { title: "Performance",           max: 15 },
  uptime:           { title: "Uptime",                max: null },
};

function SectionCard({ result }: { result: CheckResult }) {
  const [open, setOpen] = useState(false);
  const [techOpen, setTechOpen] = useState(false);
  const meta = CATEGORY_META[result.category] ?? { title: result.category, max: null };

  return (
    <Card>
      <button className="w-full flex items-center gap-4 p-5 text-left" onClick={() => setOpen(!open)}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="font-semibold text-slate-900">{meta.title}</h3>
            <StatusBadge status={result.status} label={result.status.charAt(0).toUpperCase() + result.status.slice(1)} />
          </div>
          {!open && <p className="text-sm text-slate-500 mt-1 truncate">{result.summary}</p>}
        </div>
        {result.score !== null && meta.max && (
          <div className="flex-shrink-0 text-right">
            <span className={`text-lg font-black ${result.score === meta.max ? "text-emerald-600" : result.score >= meta.max * 0.7 ? "text-amber-600" : "text-red-600"}`}>
              {result.score}
            </span>
            <span className="text-xs text-slate-400">/{meta.max}</span>
          </div>
        )}
        <ChevronDown size={18} className={`text-slate-400 flex-shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-700 mb-3">{result.summary}</p>
          {result.recommendation && (
            <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl mb-4">
              <span className="text-amber-600 text-sm flex-shrink-0 mt-0.5">💡</span>
              <p className="text-sm text-amber-800">{result.recommendation}</p>
            </div>
          )}
          {result.technical_details && (
            <>
              <button onClick={() => setTechOpen(!techOpen)} className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-600 transition-colors">
                <ChevronDown size={12} className={`transition-transform ${techOpen ? "rotate-180" : ""}`} />
                Technical details
              </button>
              {techOpen && (
                <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <pre className="text-xs font-mono text-slate-600 leading-relaxed whitespace-pre-wrap">
                    {JSON.stringify(result.technical_details, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Card>
  );
}

export default function WebsiteDetails() {
  const { id } = useParams<{ id: string }>();
  const [site, setSite] = useState<Website | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [results, setResults] = useState<CheckResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    if (!id) return;
    setIsLoading(true);
    setError('');
    try {
      const [siteData, scans] = await Promise.all([
        websiteService.get(Number(id)),
        scanService.list(Number(id)),
      ]);
      setSite(siteData);
      const lastScan = scans[0] ?? null;
      setScan(lastScan);
      if (lastScan?.status === 'completed') {
        const r = await scanService.getResults(lastScan.id);
        setResults(r);
      }
    } catch {
      setError('Failed to load website details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const runScan = async () => {
    if (!id) return;
    setIsScanning(true);
    try {
      await websiteService.scan(Number(id));
      setTimeout(load, 5000);
    } catch {
      setError('Failed to start scan.');
    } finally {
      setTimeout(() => setIsScanning(false), 5000);
    }
  };

  const scoreBreakdown = Object.entries(CATEGORY_META)
    .filter(([, m]) => m.max !== null)
    .map(([key, m]) => {
      const r = results.find(r => r.category === key);
      return { label: m.title, score: r?.score ?? 0, max: m.max as number };
    });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !site) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <Link to="/app/websites" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6">
          <ArrowLeft size={14} /> All websites
        </Link>
        <div className="p-8 text-center text-red-500">{error || 'Website not found.'}</div>
      </div>
    );
  }

  const status = (scan?.health_status ?? 'neutral') as 'healthy' | 'warning' | 'critical' | 'neutral';

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <Link to="/app/websites" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6">
        <ArrowLeft size={14} /> All websites
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900">{site.domain}</h1>
            <StatusBadge status={status} label={status === 'healthy' ? 'Online' : status === 'critical' ? 'Offline' : status === 'warning' ? 'Needs attention' : 'No data'} />
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {scan?.completed_at ? `Last checked: ${new Date(scan.completed_at).toLocaleString()}` : 'Not yet scanned'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runScan} disabled={isScanning}>
            <RefreshCw size={14} className={isScanning ? "animate-spin" : ""} />
            {isScanning ? "Scanning..." : "Run check"}
          </Button>
        </div>
      </div>

      {!scan && (
        <div className="p-8 text-center bg-white border border-slate-200 rounded-2xl mb-6">
          <p className="text-slate-500 mb-4">No scan yet for this website.</p>
          <Button onClick={runScan} disabled={isScanning}>
            {isScanning ? "Scanning..." : "Run first scan"}
          </Button>
        </div>
      )}

      {scan && (
        <div className="grid lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1">
            <Card className="p-5 sticky top-6">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Health Score</p>
              <div className="flex justify-center mb-4">
                <ScoreRing score={scan.health_score ?? 0} size={100} />
              </div>
              <div className="space-y-2 mt-2">
                {scoreBreakdown.map(({ label, score, max }) => (
                  <div key={label}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-500">{label}</span>
                      <span className="font-semibold text-slate-700">{score}/{max}</span>
                    </div>
                    <ProgressBar value={score} max={max} />
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="lg:col-span-3 flex flex-col gap-3">
            {results.length === 0 ? (
              <Card className="p-8 text-center text-slate-400">
                {scan.status === 'running' || scan.status === 'queued'
                  ? 'Scan in progress...'
                  : 'No results available.'}
              </Card>
            ) : (
              results.map((result) => (
                <SectionCard key={result.category} result={result} />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
