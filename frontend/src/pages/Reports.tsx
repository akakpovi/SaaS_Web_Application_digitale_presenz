import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, Button, ScoreRing } from "../components/ui";
import { Download, TrendingUp, TrendingDown } from "lucide-react";

const history = [
  { month: "August 2026", score: 82, change: +6, issues: 2 },
  { month: "July 2026", score: 76, change: +2, issues: 4 },
  { month: "June 2026", score: 74, change: -1, issues: 5 },
  { month: "May 2026", score: 75, change: +3, issues: 3 },
  { month: "April 2026", score: 72, change: +5, issues: 6 },
  { month: "March 2026", score: 67, change: +2, issues: 8 },
];

const chartData = history.slice().reverse().map(h => ({
  name: h.month.split(" ")[0].slice(0, 3),
  score: h.score,
}));

export default function Reports() {
  const current = history[0];

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
        <p className="text-slate-500 mt-1">Your monthly digital presence reports.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Current report */}
        <div className="lg:col-span-2">
          <Card className="p-6">
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Monthly Report</p>
                <h2 className="text-xl font-bold text-slate-900">{current.month}</h2>
              </div>
              <Button size="sm" variant="outline">
                <Download size={14} /> Download PDF
              </Button>
            </div>

            <div className="flex items-center gap-8 mb-6 pb-6 border-b border-slate-100">
              <ScoreRing score={current.score} size={100} />
              <div>
                <p className="text-sm text-slate-500 mb-2">Overall health</p>
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp size={16} className="text-emerald-500" />
                  <span className="text-emerald-600 font-semibold">+{current.change} points vs last month</span>
                </div>
                <p className="text-sm text-slate-500">{current.issues} issues detected this month</p>
              </div>
            </div>

            {/* Breakdown */}
            <div className="space-y-4 mb-6">
              <h3 className="font-semibold text-slate-800">Score breakdown</h3>
              {[
                { label: "Website availability", score: 20, max: 20, status: "healthy" },
                { label: "SSL certificate", score: 20, max: 20, status: "healthy" },
                { label: "DNS configuration", score: 15, max: 15, status: "healthy" },
                { label: "Email security", score: 10, max: 15, status: "warning" },
                { label: "Security headers", score: 9, max: 15, status: "warning" },
                { label: "Performance", score: 8, max: 15, status: "warning" },
              ].map(({ label, score, max, status }) => (
                <div key={label} className="flex items-center gap-4">
                  <span className="text-sm text-slate-600 w-44 flex-shrink-0">{label}</span>
                  <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${status === "healthy" ? "bg-emerald-500" : "bg-amber-500"}`}
                      style={{ width: `${(score / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold text-slate-800 tabular-nums w-10 text-right">{score}/{max}</span>
                  <span>{status === "healthy" ? "🟢" : "🟠"}</span>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
              <p className="text-sm font-semibold text-amber-800 mb-2">Recommended actions this month</p>
              <ul className="space-y-1">
                <li className="text-sm text-amber-700">• Set up DMARC to improve email protection</li>
                <li className="text-sm text-amber-700">• Add a Content Security Policy header</li>
                <li className="text-sm text-amber-700">• Optimize images to improve performance</li>
              </ul>
            </div>
          </Card>
        </div>

        {/* History sidebar */}
        <div className="flex flex-col gap-4">
          {/* Chart */}
          <Card className="p-5">
            <h3 className="font-semibold text-slate-900 mb-4">Score history</h3>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                <YAxis domain={[60, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 12 }}
                  formatter={(v) => [v as number, "Score"]}
                />
                <Bar dataKey="score" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Past reports */}
          <Card className="overflow-hidden">
            <div className="p-4 pb-0">
              <h3 className="font-semibold text-slate-900">Past reports</h3>
            </div>
            <div className="divide-y divide-slate-100">
              {history.map((report, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{report.month}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                      {report.change > 0 ? (
                        <TrendingUp size={10} className="text-emerald-500" />
                      ) : (
                        <TrendingDown size={10} className="text-red-500" />
                      )}
                      <span className={`text-xs ${report.change > 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {report.change > 0 ? "+" : ""}{report.change}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-lg font-black ${report.score >= 80 ? "text-emerald-600" : "text-amber-600"}`}>
                      {report.score}
                    </span>
                    <button className="text-slate-400 hover:text-slate-600">
                      <Download size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
