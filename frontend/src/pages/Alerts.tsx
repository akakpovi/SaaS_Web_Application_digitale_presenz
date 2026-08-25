import React, { useState } from "react";
import { Card, Button, Tabs } from "../components/ui";
import { Link } from "react-router-dom";

const allAlerts = [
  {
    id: 1, type: "critical", icon: "🔴", title: "Website unavailable",
    site: "example-shop.de", detail: "Your website is temporarily unavailable.",
    time: "12 minutes ago", resolved: false,
  },
  {
    id: 2, type: "warning", icon: "🟠", title: "SSL certificate expires soon",
    site: "example.de", detail: "Your SSL certificate expires in 12 days.",
    time: "2 hours ago", resolved: false,
  },
  {
    id: 3, type: "warning", icon: "🟡", title: "DNS configuration changed",
    site: "example.com", detail: "A change was detected in your DNS records.",
    time: "Yesterday", resolved: false,
  },
  {
    id: 4, type: "info", icon: "⚠️", title: "Email protection needs improvement",
    site: "example.com", detail: "Your DMARC policy is set to 'none' — emails are not rejected.",
    time: "2 days ago", resolved: false,
  },
  {
    id: 5, type: "resolved", icon: "✅", title: "Website back online",
    site: "example.de", detail: "Your website recovered after 4 minutes of downtime.",
    time: "Last week", resolved: true,
  },
  {
    id: 6, type: "resolved", icon: "✅", title: "SSL certificate renewed",
    site: "example.com", detail: "SSL certificate successfully renewed.",
    time: "2 weeks ago", resolved: true,
  },
];

const filterMap: Record<string, (a: typeof allAlerts[0]) => boolean> = {
  "All": () => true,
  "Critical": (a) => a.type === "critical",
  "Warning": (a) => a.type === "warning",
  "Resolved": (a) => a.resolved,
};

export default function Alerts() {
  const [filter, setFilter] = useState("All");
  const [dismissed, setDismissed] = useState<number[]>([]);

  const filtered = allAlerts.filter(filterMap[filter]).filter(a => !dismissed.includes(a.id));

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Alerts</h1>
        <p className="text-slate-500 mt-1">Stay informed about changes to your digital presence.</p>
      </div>

      <div className="mb-6">
        <Tabs tabs={["All", "Critical", "Warning", "Resolved"]} active={filter} onChange={setFilter} />
      </div>

      {filtered.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-4xl mb-4">🎉</p>
          <p className="font-semibold text-slate-900 mb-1">No alerts</p>
          <p className="text-sm text-slate-500">Your digital presence looks healthy in this category.</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((alert) => (
            <Card key={alert.id} className="p-5">
              <div className="flex items-start gap-4">
                <span className="text-2xl flex-shrink-0 mt-0.5">{alert.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                      <p className="font-semibold text-slate-900">{alert.title}</p>
                      <p className="text-sm text-indigo-600 mt-0.5">{alert.site}</p>
                    </div>
                    <span className="text-xs text-slate-400 flex-shrink-0">{alert.time}</span>
                  </div>
                  <p className="text-sm text-slate-600 mt-2">{alert.detail}</p>

                  {!alert.resolved && (
                    <div className="flex items-center gap-2 mt-4">
                      <Link to="/app/websites/2">
                        <Button size="sm">View details</Button>
                      </Link>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDismissed(prev => [...prev, alert.id])}
                      >
                        Resolve
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setDismissed(prev => [...prev, alert.id])}
                      >
                        Ignore
                      </Button>
                    </div>
                  )}
                  {alert.resolved && (
                    <span className="inline-flex items-center gap-1.5 mt-3 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-medium rounded-full border border-emerald-200">
                      ✅ Resolved
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
