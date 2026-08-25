import React from "react";
import { Link } from "react-router-dom";
import { Globe, Plus, ArrowRight } from "lucide-react";
import { Card, StatusBadge, ScoreRing, Button } from "../components/ui";

const websites = [
  { id: "1", domain: "example.de", status: "healthy" as const, statusLabel: "Online", score: 92, uptime: "99.99%", ssl: "Valid", sslStatus: "healthy" as const, lastCheck: "2 min ago", issues: 0 },
  { id: "2", domain: "example.com", status: "healthy" as const, statusLabel: "Online", score: 82, uptime: "99.98%", ssl: "Valid", sslStatus: "healthy" as const, lastCheck: "5 min ago", issues: 1 },
  { id: "3", domain: "example-shop.de", status: "warning" as const, statusLabel: "Needs attention", score: 64, uptime: "98.91%", ssl: "Expires soon", sslStatus: "warning" as const, lastCheck: "3 min ago", issues: 2 },
];

export default function Websites() {
  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Websites</h1>
          <p className="text-slate-500 mt-1">Manage and monitor all your websites from one place.</p>
        </div>
        <Button>
          <Plus size={16} /> Add website
        </Button>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
        {websites.map((site) => (
          <Link to={`/app/websites/${site.id}`} key={site.id}>
            <Card className="p-5 h-full">
              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                  <Globe size={18} className="text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{site.domain}</p>
                  <StatusBadge status={site.status} label={site.statusLabel} />
                </div>
              </div>

              <div className="flex items-center justify-between mb-4">
                <ScoreRing score={site.score} size={72} label="Health score" />
                <div className="flex flex-col gap-2 text-right">
                  <div>
                    <p className="text-xs text-slate-500">Uptime</p>
                    <p className="text-sm font-semibold text-slate-800">{site.uptime}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">SSL</p>
                    <StatusBadge status={site.sslStatus} label={site.ssl} />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <p className="text-xs text-slate-400">Last check: {site.lastCheck}</p>
                {site.issues > 0 && (
                  <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full border border-amber-200 font-medium">
                    {site.issues} issue{site.issues > 1 ? "s" : ""}
                  </span>
                )}
                {site.issues === 0 && (
                  <span className="text-xs text-emerald-600 font-medium">✓ All good</span>
                )}
              </div>
            </Card>
          </Link>
        ))}

        {/* Add website card */}
        <div className="border-2 border-dashed border-slate-200 rounded-2xl p-5 flex flex-col items-center justify-center text-center min-h-48 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all cursor-pointer group">
          <div className="w-12 h-12 bg-slate-100 group-hover:bg-indigo-100 rounded-xl flex items-center justify-center mb-3 transition-colors">
            <Plus size={20} className="text-slate-400 group-hover:text-indigo-600 transition-colors" />
          </div>
          <p className="font-medium text-slate-600 group-hover:text-indigo-700 transition-colors">Add website</p>
          <p className="text-sm text-slate-400 mt-1">Monitor a new domain</p>
        </div>
      </div>
    </div>
  );
}
