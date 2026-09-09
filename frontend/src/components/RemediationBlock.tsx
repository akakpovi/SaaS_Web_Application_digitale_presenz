import type { RemediationGuide } from "../types/remediation";

interface RemediationBlockProps {
  guide: RemediationGuide;
}

export function RemediationBlock({ guide }: RemediationBlockProps) {
  if (!guide || !guide.steps || guide.steps.length === 0) {
    return (
      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-center text-sm text-slate-500">
        Guide de correction à venir.
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white p-4">
      <h4 className="text-sm font-bold text-slate-800">{guide.title}</h4>
      <p className="mt-1 text-xs text-slate-500">{guide.explanation}</p>
      <ol className="mt-3 space-y-2">
        {guide.steps.map((step) => (
          <li key={step.order} className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
              {step.order}
            </span>
            <div className="flex-1">
              <p className="text-xs text-slate-700">{step.description}</p>
              {step.codeSnippet && (
                <pre className="mt-1 overflow-x-auto rounded bg-slate-900 px-3 py-1.5 text-xs text-emerald-300">
                  <code>{step.codeSnippet}</code>
                </pre>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
