import React, { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, Tabs } from "../components/ui";

const periods: Record<string, { label: string; data: { time: string; value: number }[] }> = {
  "24H": {
    label: "24 hours",
    data: [
      { time: "00:00", value: 100 }, { time: "04:00", value: 100 },
      { time: "08:00", value: 100 }, { time: "09:00", value: 100 },
      { time: "10:00", value: 100 }, { time: "11:00", value: 0 },
      { time: "11:04", value: 100 }, { time: "12:00", value: 100 },
      { time: "16:00", value: 100 }, { time: "20:00", value: 100 },
      { time: "23:59", value: 100 },
    ],
  },
  "7D": {
    label: "7 days",
    data: Array.from({ length: 7 }, (_, i) => ({
      time: `Day ${i + 1}`,
      value: i === 3 ? 98.5 : 100,
    })),
  },
  "30D": {
    label: "30 days",
    data: Array.from({ length: 30 }, (_, i) => ({
      time: `${i + 1}`,
      value: [11, 22].includes(i) ? 97 + Math.random() : 99 + Math.random() * 0.9,
    })),
  },
  "90D": {
    label: "90 days",
    data: Array.from({ length: 12 }, (_, i) => ({
      time: `W${i + 1}`,
      value: 98.5 + Math.random() * 1.4,
    })),
  },
};

const timeline = [
  { time: "Today, 11:04", event: "✅ Website back online", detail: "Downtime: 4 minutes", type: "recovery" },
  { time: "Today, 11:00", event: "🔴 Website unavailable", detail: "Detected automatically", type: "incident" },
  { time: "Yesterday, 09:00", event: "✅ DNS check passed", detail: "All records verified", type: "check" },
  { time: "3 days ago", event: "✅ SSL certificate valid", detail: "Expires 14 Sep 2026", type: "check" },
  { time: "Last week", event: "🟠 SSL certificate warning", detail: "Expires in 30 days — alert sent", type: "warning" },
];

export default function Monitoring() {
  const [period, setPeriod] = useState("24H");

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Monitoring</h1>
        <p className="text-slate-500 mt-1">Automatic monitoring is active for all your websites.</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Monitoring status", value: "Active", sub: "All websites", icon: "🟢" },
          { label: "Check frequency", value: "Every hour", sub: "Pro plan", icon: "⏱" },
          { label: "Websites monitored", value: "3", sub: "2 healthy, 1 warning", icon: "🌐" },
          { label: "Uptime (30d)", value: "99.98%", sub: "8.6 min downtime", icon: "📈" },
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
            <h2 className="font-bold text-slate-900">Uptime chart</h2>
            <p className="text-sm text-slate-500">example.de · {periods[period].label}</p>
          </div>
          <div className="sm:ml-auto">
            <Tabs tabs={["24H", "7D", "30D", "90D"]} active={period} onChange={setPeriod} />
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={periods[period].data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
            <defs>
              <linearGradient id="uptimeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.07)" }}
              formatter={(v) => [`${(v as number).toFixed(2)}%`, "Uptime"]}
            />
            <Area
              type="stepAfter"
              dataKey="value"
              stroke="#4f46e5"
              strokeWidth={2}
              fill="url(#uptimeGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      {/* Event timeline */}
      <Card className="p-5">
        <h2 className="font-bold text-slate-900 mb-5">Event timeline</h2>
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-slate-200" />
          <div className="space-y-4">
            {timeline.map((event, i) => (
              <div key={i} className="relative flex items-start gap-4 pl-10">
                <div className={`absolute left-2.5 top-2 w-3 h-3 rounded-full border-2 ${
                  event.type === "incident" ? "bg-red-100 border-red-500" :
                  event.type === "recovery" ? "bg-emerald-100 border-emerald-500" :
                  event.type === "warning" ? "bg-amber-100 border-amber-500" :
                  "bg-slate-100 border-slate-300"
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
      </Card>
    </div>
  );
}
