import React, { useEffect, useState } from 'react';
import { useNavigate } from "react-router-dom";
import { CheckCircle, Loader } from "lucide-react";
import { Button, Input, ScoreRing } from "../components/ui";
import { useTranslation } from "react-i18next";
import SEO from "../components/SEO";
import { websiteService, scanService, CheckResult } from "../services/websiteService";

const steps = ["Your business", "Add website", "Scanning...", "Results"];

const checkLabels = [
  "Checking website availability...",
  "Checking SSL certificate...",
  "Checking DNS configuration...",
  "Checking email security...",
  "Checking security headers...",
  "Checking performance...",
  "Calculating your score...",
];

const industries = ["Restaurant / Café", "Retail", "Hotel / Hospitality", "Auto Repair", "Beauty / Hair Salon", "Freelancer", "Agency", "Real Estate", "Professional Services", "Other"];

export default function Onboarding() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [business, setBusiness] = useState({ name: "", industry: "", country: "Germany" });
  const [domain, setDomain] = useState("");
  const [checkIdx, setCheckIdx] = useState(0);
  const [scanResults, setScanResults] = useState<CheckResult[]>([]);
  const [finalScore, setFinalScore] = useState(0);
  const [scanError, setScanError] = useState('');

  useEffect(() => {
    if (step !== 2) return;

    // Animer les checks
    const timer = setInterval(() => {
      setCheckIdx(prev => {
        if (prev < checkLabels.length - 1) return prev + 1;
        clearInterval(timer);
        return prev;
      });
    }, 700);

    return () => clearInterval(timer);
  }, [step]);

  const startScan = async () => {
    setScanError('');
    setStep(2);
    setCheckIdx(0);

    try {
      // Créer le site
      const site = await websiteService.create(domain.trim());
      // Lancer le scan
      const scan = await websiteService.scan(site.id);

      // Attendre que le scan se termine (polling)
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const scans = await scanService.list(site.id);
          const latest = scans[0];
          if (latest?.status === 'completed') {
            clearInterval(poll);
            const results = await scanService.getResults(latest.id);
            setScanResults(results);
            setFinalScore(latest.health_score ?? 0);
            setTimeout(() => setStep(3), 500);
          } else if (latest?.status === 'failed' || attempts > 20) {
            clearInterval(poll);
            setFinalScore(0);
            setTimeout(() => setStep(3), 500);
          }
        } catch {
          if (attempts > 20) { clearInterval(poll); setStep(3); }
        }
      }, 2000);
    } catch (err: any) {
      const data = err?.response?.data;
      setScanError(data?.domain?.[0] ?? data?.detail ?? 'Failed to add website.');
      setStep(1);
    }
  };

  const CATEGORY_LABELS: Record<string, string> = {
    website: 'Website availability',
    ssl: 'SSL Certificate',
    dns: 'DNS',
    email_security: 'Email security',
    security_headers: 'Security headers',
    performance: 'Performance',
  };

  const CATEGORY_MAX: Record<string, number> = {
    website: 20, ssl: 20, dns: 15,
    email_security: 15, security_headers: 15, performance: 15,
  };

  return (
    <div className="min-h-full bg-slate-50 flex flex-col">
      <SEO title="Getting started" description="Set up your Presence account" noIndex path="/onboarding" />
      <header className="py-6 px-4">
        <div className="max-w-lg mx-auto">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </div>
          <div className="flex items-center gap-2">
            {steps.map((s, i) => (
              <React.Fragment key={s}>
                <div className={`flex items-center gap-2 ${i <= step ? "text-indigo-600" : "text-slate-400"}`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${
                    i < step ? "bg-indigo-600 border-indigo-600 text-white" :
                    i === step ? "border-indigo-600 text-indigo-600 bg-white" :
                    "border-slate-300 text-slate-400"
                  }`}>
                    {i < step ? <CheckCircle size={12} /> : i + 1}
                  </div>
                  <span className="text-xs font-medium hidden sm:block">{s}</span>
                </div>
                {i < steps.length - 1 && <div className={`flex-1 h-px ${i < step ? "bg-indigo-600" : "bg-slate-200"}`} />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg">
          {step === 0 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <h1 className="text-2xl font-bold text-slate-900 mb-2">Tell us about your business</h1>
              <p className="text-sm text-slate-500 mb-6">This helps us personalize your experience.</p>
              <div className="flex flex-col gap-4">
                <Input label="Business name" placeholder="Schmidt's Bakery" value={business.name} onChange={(v) => setBusiness({ ...business, name: v })} />
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">Industry</label>
                  <select value={business.industry} onChange={(e) => setBusiness({ ...business, industry: e.target.value })}
                    className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                    <option value="">Select your industry</option>
                    {industries.map(i => <option key={i}>{i}</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">Country</label>
                  <select value={business.country} onChange={(e) => setBusiness({ ...business, country: e.target.value })}
                    className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                    {["Germany", "France", "Austria", "Switzerland", "Netherlands", "Belgium", "Other"].map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <Button className="w-full mt-2" onClick={() => setStep(1)}>Continue</Button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <h1 className="text-2xl font-bold text-slate-900 mb-2">Add your website</h1>
              <p className="text-sm text-slate-500 mb-6">Enter your domain name to start monitoring.</p>
              {scanError && (
                <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{scanError}</div>
              )}
              <div className="flex flex-col gap-4">
                <Input label={t("onboarding.domain_label")} placeholder="example.com" value={domain} onChange={setDomain}
                  helper="Enter your domain without https:// — we'll handle the rest." />
                <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 text-sm text-indigo-700">
                  <p className="font-medium mb-1">What we'll check:</p>
                  <ul className="space-y-1 text-indigo-600">
                    {["Website availability", "SSL certificate", "DNS configuration", "Email security", "Security headers", "Performance"].map(c => (
                      <li key={c} className="flex items-center gap-2"><CheckCircle size={12} /> {c}</li>
                    ))}
                  </ul>
                </div>
                <Button className="w-full" onClick={startScan} disabled={!domain.trim()}>Check my website</Button>
                <button onClick={() => setStep(0)} className="text-sm text-slate-400 hover:text-slate-600 text-center">← Back</button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center">
              <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-6">
                <Loader size={24} className="text-indigo-600 animate-spin" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">Scanning your website...</h1>
              <p className="text-slate-500 text-sm mb-8">This usually takes about 10–30 seconds.</p>
              <div className="flex flex-col gap-2 text-left">
                {checkLabels.map((c, i) => (
                  <div key={c} className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all ${i < checkIdx ? "bg-emerald-50" : i === checkIdx ? "bg-indigo-50" : "opacity-40"}`}>
                    {i < checkIdx ? <CheckCircle size={16} className="text-emerald-500 flex-shrink-0" />
                      : i === checkIdx ? <Loader size={16} className="text-indigo-600 animate-spin flex-shrink-0" />
                      : <div className="w-4 h-4 rounded-full border border-slate-300 flex-shrink-0" />}
                    <span className={`text-sm ${i < checkIdx ? "text-emerald-700" : i === checkIdx ? "text-indigo-700 font-medium" : "text-slate-400"}`}>{c}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <div className="text-center mb-6">
                <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle size={24} className="text-emerald-600" />
                </div>
                <h1 className="text-2xl font-bold text-slate-900 mb-1">Your first report is ready!</h1>
                <p className="text-sm text-slate-500">Here's the digital health score for <strong>{domain}</strong></p>
              </div>
              <div className="flex justify-center mb-6">
                <ScoreRing score={finalScore} size={140} label="Digital Health Score" />
              </div>
              <div className="space-y-2 mb-6">
                {scanResults.filter(r => r.category !== 'uptime').map((r) => (
                  <div key={r.category} className="flex items-center justify-between px-4 py-2.5 bg-slate-50 rounded-xl">
                    <span className="text-sm font-medium text-slate-700">{CATEGORY_LABELS[r.category] ?? r.category}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-500">
                        {r.status === 'healthy' ? '🟢 Healthy' : r.status === 'warning' ? '🟠 Needs attention' : r.status === 'critical' ? '🔴 Critical' : '⚪ No data'}
                      </span>
                      {r.score !== null && (
                        <span className="text-sm font-semibold text-slate-800 tabular-nums">
                          {r.score}/{CATEGORY_MAX[r.category] ?? '?'}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {scanResults.length === 0 && (
                  <p className="text-center text-sm text-slate-400">Scan results will appear shortly in your dashboard.</p>
                )}
              </div>
              <Button className="w-full" onClick={() => navigate("/app/dashboard")}>Open dashboard</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
