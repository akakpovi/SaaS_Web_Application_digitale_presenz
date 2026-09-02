import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface ScanData {
  scan_id: string;
  domain: string;
  score: number;
  status: string;
  summary: { critical: number; warnings: number; passed: number };
  checks: Record<string, { status: string; score: number; message: string }>;
}

export function PublicScanResult() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const [scan, setScan] = useState<ScanData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!scanId) return;
    axios
      .get(`${API_BASE}/public/scan/${scanId}/status/`)
      .then((r) => setScan(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [scanId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-500">Scan introuvable.</p>
      </div>
    );
  }

  const scoreColor = scan.score >= 80 ? 'text-emerald-600' : scan.score >= 50 ? 'text-amber-600' : 'text-red-600';
  const ringColor = scan.score >= 80 ? 'ring-emerald-500' : scan.score >= 50 ? 'ring-amber-500' : 'ring-red-500';

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4">
      <div className="mx-auto max-w-2xl">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900">Rapport de présence — {scan.domain}</h1>
          <div className="mt-6 inline-flex">
            <div className={`flex h-28 w-28 items-center justify-center rounded-full bg-white shadow-md ring-4 ${ringColor}`}>
              <span className={`text-4xl font-extrabold ${scoreColor}`}>{scan.score}</span>
            </div>
          </div>
          <p className="mt-2 text-sm text-slate-500">Score de santé globale / 100</p>
        </div>

        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">Vulnérabilités détectées</h2>
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg bg-red-50 p-3">
              <span className="text-2xl font-bold text-red-600">{scan.summary.critical}</span>
              <p className="text-xs text-red-600">Critiques</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-3">
              <span className="text-2xl font-bold text-amber-600">{scan.summary.warnings}</span>
              <p className="text-xs text-amber-600">Avertissements</p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-3">
              <span className="text-2xl font-bold text-emerald-600">{scan.summary.passed}</span>
              <p className="text-xs text-emerald-600">Conformes</p>
            </div>
          </div>

          <div className="mt-6 space-y-2 select-none">
            {Object.entries(scan.checks).map(([key, check]) => (
              <div key={key} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 p-3">
                <span className="text-sm font-medium capitalize text-slate-700">{key.replace(/_/g, ' ')}</span>
                <span className="text-xs text-slate-400 blur-sm">{check.message}</span>
              </div>
            ))}
          </div>
        </div>

        {/* PAYWALL TECHNIQUE REVISITÉ */}
        <div className="relative mt-8 overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 p-8 text-center text-white shadow-xl">
          <div className="pointer-events-none absolute -top-16 left-1/2 h-48 w-48 -translate-x-1/2 rounded-full bg-blue-400/25 blur-3xl" />
          
          <div className="relative mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-white/10 ring-2 ring-white/20 backdrop-blur-sm">
            <svg className="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>

          <h3 className="relative text-xl font-bold">Débloquez les guides de remédiation</h3>
          <p className="relative mt-2 text-sm text-blue-100 max-w-md mx-auto">
            Débloquez le diagnostic détaillé et les instructions pas-à-pas pour corriger ces vulnérabilités.
          </p>

          <button
            type="button"
            onClick={() => navigate(`/register?scan_id=${scan.scan_id}&url=https://${scan.domain}`)}
            className="relative mt-6 inline-flex items-center gap-2 rounded-xl bg-white px-8 py-3.5 text-sm font-bold text-blue-700 shadow-lg transition hover:bg-blue-50 hover:shadow-blue-500/25 active:scale-95"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
            </svg>
            Créer mon compte gratuit
          </button>
          
          <p className="relative mt-3 text-xs text-blue-200">100% gratuit · Zéro carte requise</p>
        </div>
      </div>
    </div>
  );
}

export default PublicScanResult;
