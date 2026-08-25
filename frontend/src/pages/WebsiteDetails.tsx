import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, RefreshCw, Settings, ChevronDown } from "lucide-react";
import { Card, StatusBadge, ScoreRing, Button, ProgressBar } from "../components/ui";

const siteData: Record<string, { domain: string; status: "healthy" | "warning"; score: number }> = {
  "1": { domain: "example.de", status: "healthy", score: 92 },
  "2": { domain: "example.com", status: "warning", score: 82 },
  "3": { domain: "example-shop.de", status: "warning", score: 64 },
};

const sections = [
  {
    key: "website",
    title: "Website availability",
    status: "healthy" as const,
    statusLabel: "Available",
    score: 20,
    max: 20,
    summary: "Your website is accessible and responding normally.",
    action: null,
    details: "HTTP 200 OK · Response time: 230ms · Server: nginx/1.24.0",
  },
  {
    key: "ssl",
    title: "SSL certificate",
    status: "healthy" as const,
    statusLabel: "Valid",
    score: 20,
    max: 20,
    summary: "Your SSL certificate is valid and secure.",
    action: null,
    details: "Issuer: Let's Encrypt · Valid until: 14 September 2026 · Algorithm: RSA 2048",
  },
  {
    key: "dns",
    title: "DNS configuration",
    status: "healthy" as const,
    statusLabel: "Configured",
    score: 15,
    max: 15,
    summary: "Your domain configuration looks correct.",
    action: null,
    details: "A record: 185.123.45.67 · MX record: mail.example.de · TTL: 3600",
  },
  {
    key: "email",
    title: "Email protection",
    status: "warning" as const,
    statusLabel: "Needs attention",
    score: 10,
    max: 15,
    summary: "Your email protection configuration could be improved.",
    action: "We recommend setting up DMARC to prevent email spoofing.",
    details: "SPF: ✅ Configured · DKIM: ✅ Configured · DMARC: ⚠️ Policy set to 'none' — emails are not rejected",
  },
  {
    key: "headers",
    title: "Security headers",
    status: "warning" as const,
    statusLabel: "Needs attention",
    score: 9,
    max: 15,
    summary: "Some recommended security headers are missing.",
    action: "Add a Content Security Policy header to improve protection.",
    details: "X-Frame-Options: ✅ · X-Content-Type-Options: ✅ · CSP: ⚠️ Missing · HSTS: ✅ · Referrer-Policy: ⚠️ Missing",
  },
  {
    key: "performance",
    title: "Performance",
    status: "warning" as const,
    statusLabel: "Good",
    score: 8,
    max: 15,
    summary: "Your website loads in 2.3 seconds. There's room for improvement.",
    action: "Optimize your images and enable caching to improve load time.",
    details: "Time to First Byte: 230ms · First Contentful Paint: 1.1s · Largest Contentful Paint: 2.3s · Page size: 3.2MB",
  },
  {
    key: "uptime",
    title: "Uptime",
    status: "healthy" as const,
    statusLabel: "Excellent",
    score: null,
    max: null,
    summary: "Your website has been online 99.98% of the time in the last 30 days.",
    action: null,
    details: "Uptime (30d): 99.98% · Downtime: 8.6 minutes · Last incident: 3 weeks ago",
  },
  {
    key: "reviews",
    title: "Online reviews",
    status: "healthy" as const,
    statusLabel: "Good",
    score: null,
    max: null,
    summary: "Your average rating is 4.7 out of 5 stars across 248 reviews.",
    action: null,
    details: "Google: 4.8 ★ (189 reviews) · Yelp: 4.4 ★ (59 reviews) · Last review: 2 days ago",
  },
];

function SectionCard({ section }: { section: typeof sections[0] }) {
  const [open, setOpen] = useState(false);
  const [techOpen, setTechOpen] = useState(false);

  return (
    <Card>
      <button
        className="w-full flex items-center gap-4 p-5 text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="font-semibold text-slate-900">{section.title}</h3>
            <StatusBadge status={section.status} label={section.statusLabel} />
          </div>
          {!open && <p className="text-sm text-slate-500 mt-1 truncate">{section.summary}</p>}
        </div>
        {section.score !== null && (
          <div className="flex-shrink-0 text-right">
            <span className={`text-lg font-black ${section.score === section.max ? "text-emerald-600" : section.score! >= section.max! * 0.7 ? "text-amber-600" : "text-red-600"}`}>
              {section.score}
            </span>
            <span className="text-xs text-slate-400">/{section.max}</span>
          </div>
        )}
        <ChevronDown size={18} className={`text-slate-400 flex-shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-700 mb-3">{section.summary}</p>
          {section.action && (
            <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl mb-4">
              <span className="text-amber-600 text-sm flex-shrink-0 mt-0.5">💡</span>
              <p className="text-sm text-amber-800">{section.action}</p>
            </div>
          )}
          <button
            onClick={() => setTechOpen(!techOpen)}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-600 transition-colors"
          >
            <ChevronDown size={12} className={`transition-transform ${techOpen ? "rotate-180" : ""}`} />
            Technical details
          </button>
          {techOpen && (
            <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <p className="text-xs font-mono text-slate-600 leading-relaxed">{section.details}</p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function WebsiteDetails() {
  const { id } = useParams();
  const site = siteData[id || "2"] || siteData["2"];
  const [checking, setChecking] = useState(false);

  const runCheck = () => {
    setChecking(true);
    setTimeout(() => setChecking(false), 2000);
  };

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <Link to="/app/websites" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6">
        <ArrowLeft size={14} /> All websites
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900">{site.domain}</h1>
            <StatusBadge status={site.status} label={site.status === "healthy" ? "Online" : "Needs attention"} />
          </div>
          <p className="text-sm text-slate-500 mt-1">Last checked: 2 minutes ago · Checked hourly</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runCheck}>
            <RefreshCw size={14} className={checking ? "animate-spin" : ""} />
            {checking ? "Checking..." : "Run check"}
          </Button>
          <Button variant="outline" size="sm">
            <Settings size={14} /> Settings
          </Button>
        </div>
      </div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Score sidebar */}
        <div className="lg:col-span-1">
          <Card className="p-5 sticky top-6">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Health Score</p>
            <div className="flex justify-center mb-4">
              <ScoreRing score={site.score} size={100} />
            </div>
            <div className="space-y-2 mt-2">
              {[
                { label: "Website", score: 20, max: 20 },
                { label: "SSL", score: 20, max: 20 },
                { label: "DNS", score: 15, max: 15 },
                { label: "Email", score: 10, max: 15 },
                { label: "Security", score: 9, max: 15 },
                { label: "Performance", score: 8, max: 15 },
              ].map(({ label, score, max }) => (
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

        {/* Sections */}
        <div className="lg:col-span-3 flex flex-col gap-3">
          {sections.map((section) => (
            <SectionCard key={section.key} section={section} />
          ))}
        </div>
      </div>
    </div>
  );
}
