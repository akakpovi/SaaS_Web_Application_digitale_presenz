import { useState, useCallback } from "react";
import type { RemediationGuide } from "../types/remediation";

interface RemediationBlockProps {
  guide: RemediationGuide;
}

const severityConfig = {
  critical: {
    border: "border-red-200",
    bg: "bg-red-50",
    badge: "bg-red-100 text-red-700",
    iconColor: "text-red-500",
    label: "Critique",
  },
  warning: {
    border: "border-amber-200",
    bg: "bg-amber-50",
    badge: "bg-amber-100 text-amber-700",
    iconColor: "text-amber-500",
    label: "Avertissement",
  },
  info: {
    border: "border-blue-200",
    bg: "bg-blue-50",
    badge: "bg-blue-100 text-blue-700",
    iconColor: "text-blue-500",
    label: "Information",
  },
};

export function RemediationBlock({ guide }: RemediationBlockProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const cfg = severityConfig[guide.severity];

  const handleCopy = useCallback(async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    }
  }, []);

  return (
    <div className={`mt-4 overflow-hidden rounded-xl border ${cfg.border} bg-white shadow-sm`}>
      <div className={`flex items-center justify-between px-4 py-3 ${cfg.bg}`}>
        <div className="flex items-center gap-2">
          <svg className={`h-5 w-5 ${cfg.iconColor}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="font-semibold text-slate-900 text-sm">{guide.title}</span>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${cfg.badge}`}>
          {cfg.label}
        </span>
      </div>

      <div className="p-4">
        <p className="text-sm text-slate-600 leading-relaxed mb-4">{guide.explanation}</p>
        
        <h5 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
          Plan d'action recommandé
        </h5>

        <ol className="space-y-3">
          {guide.steps.map((step, idx) => (
            <li key={step.order} className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">
                {step.order}
              </span>
              <div className="flex-1">
                <p className="text-sm text-slate-700">{step.description}</p>
                {step.codeSnippet && (
                  <div className="group relative mt-2 rounded-lg bg-slate-900 p-3">
                    <button
                      type="button"
                      onClick={() => handleCopy(step.codeSnippet!, idx)}
                      className="absolute right-2 top-2 rounded bg-slate-700 px-2 py-1 text-xs font-medium text-slate-200 transition hover:bg-slate-600 hover:text-white"
                    >
                      {copiedIdx === idx ? "✓ Copié !" : "Copier"}
                    </button>
                    <pre className="overflow-x-auto text-xs text-emerald-400 font-mono pr-16">
                      <code>{step.codeSnippet}</code>
                    </pre>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
