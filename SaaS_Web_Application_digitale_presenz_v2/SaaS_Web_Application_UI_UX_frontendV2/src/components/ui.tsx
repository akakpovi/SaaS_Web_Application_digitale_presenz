import React from "react"
import { CheckCircle, AlertTriangle, XCircle, MinusCircle } from "lucide-react"
import { useI18n, type MessageKey } from "../i18n"

type Severity = "critical" | "high" | "medium" | "low" | "warning" | "info"

/** Severity value → catalogue key (typed, so a rename cannot silently drop a label). */
const SEVERITY_KEYS: Record<Severity, MessageKey> = {
  critical: "severity.critical",
  high: "severity.high",
  medium: "severity.medium",
  low: "severity.low",
  warning: "severity.warning",
  info: "severity.info",
}

export function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: React.ReactNode
  variant?: "default" | "success" | "warning" | "critical" | "neutral" | "info"
  className?: string
}) {
  const styles: Record<string, string> = {
    default: "bg-indigo-50 text-indigo-700 border border-indigo-200",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    warning: "bg-amber-50 text-amber-700 border border-amber-200",
    critical: "bg-red-50 text-red-700 border border-red-200",
    neutral: "bg-slate-100 text-slate-600 border border-slate-200",
    info: "bg-blue-50 text-blue-700 border border-blue-200",
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[variant]} ${className}`}
    >
      {children}
    </span>
  )
}

export function StatusDot({
  status,
}: {
  status: "healthy" | "warning" | "critical" | "neutral"
}) {
  const colors = {
    healthy: "bg-emerald-500",
    warning: "bg-amber-500",
    critical: "bg-red-500",
    neutral: "bg-slate-400",
  }
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${colors[status]}`}
    />
  )
}

export function StatusBadge({
  status,
  label,
}: {
  status: "healthy" | "warning" | "critical" | "neutral"
  label: string
}) {
  const map = {
    healthy: { variant: "success" as const, Icon: CheckCircle },
    warning: { variant: "warning" as const, Icon: AlertTriangle },
    critical: { variant: "critical" as const, Icon: XCircle },
    neutral: { variant: "neutral" as const, Icon: MinusCircle },
  }
  const { variant, Icon } = map[status]
  return (
    <Badge variant={variant}>
      <Icon size={10} aria-hidden="true" /> {label}
    </Badge>
  )
}

export function SeverityBadge({
  severity,
}: {
  severity: "critical" | "high" | "medium" | "low" | "warning" | "info"
}) {
  const { t } = useI18n()
  const styles: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border border-red-200",
    high: "bg-orange-100 text-orange-700 border border-orange-200",
    medium: "bg-amber-100 text-amber-700 border border-amber-200",
    low: "bg-yellow-100 text-yellow-700 border border-yellow-200",
    warning: "bg-amber-100 text-amber-700 border border-amber-200",
    info: "bg-blue-100 text-blue-700 border border-blue-200",
  }
  // The badge shows the translated severity; the value itself stays the
  // backend's machine key and is never rewritten.
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${styles[severity]}`}
    >
      {t(SEVERITY_KEYS[severity])}
    </span>
  )
}

export function Sparkline({
  data,
  color = "#4f46e5",
  height = 32,
  width = 80,
}: {
  data: number[]
  color?: string
  height?: number
  width?: number
}) {
  if (!data.length) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const step = width / (data.length - 1)
  const points = data
    .map((v, i) => {
      const x = i * step
      const y = height - ((v - min) / range) * (height - 4) - 2
      return `${x},${y}`
    })
    .join(" ")

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      aria-hidden="true"
    >
      <polyline
        points={points}
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        opacity="0.8"
      />
      <polyline
        points={`0,${height} ${points} ${width},${height}`}
        stroke="none"
        fill={color}
        opacity="0.1"
      />
    </svg>
  )
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  onClick,
  disabled,
  type = "button",
  "aria-label": ariaLabel,
}: {
  children: React.ReactNode
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline"
  size?: "sm" | "md" | "lg"
  className?: string
  onClick?: () => void
  disabled?: boolean
  type?: "button" | "submit"
  "aria-label"?: string
}) {
  const variants = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm",
    secondary: "bg-slate-100 text-slate-700 hover:bg-slate-200",
    ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
    danger: "bg-red-600 text-white hover:bg-red-700",
    outline: "border border-slate-300 text-slate-700 hover:bg-slate-50",
  }
  const sizes = {
    sm: "px-3 py-1.5 text-sm rounded-lg",
    md: "px-4 py-2 text-sm rounded-lg",
    lg: "px-6 py-3 text-base rounded-xl",
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={`inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 focus-visible:outline-2 focus-visible:outline-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  className = "",
  onClick,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-slate-200 rounded-2xl shadow-sm ${
        onClick
          ? "cursor-pointer hover:border-indigo-200 hover:shadow-md transition-all duration-200"
          : ""
      } ${className}`}
    >
      {children}
    </div>
  )
}

export function Input({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  prefix,
  helper,
  error,
  disabled,
  className = "",
}: {
  label?: string
  placeholder?: string
  value?: string
  onChange?: (v: string) => void
  type?: string
  prefix?: string
  helper?: string
  /** Server-side or client-side validation message shown under the field. */
  error?: string
  disabled?: boolean
  className?: string
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-slate-700">{label}</label>
      )}
      <div className="flex">
        {prefix && (
          <span className="inline-flex items-center px-3 text-sm text-slate-500 bg-slate-50 border border-r-0 border-slate-300 rounded-l-lg">
            {prefix}
          </span>
        )}
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          onChange={(e) => onChange?.(e.target.value)}
          className={`flex-1 px-3 py-2 text-sm border bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
            error
              ? "border-red-400 focus:ring-red-400"
              : "border-slate-300 focus:ring-indigo-500"
          } ${prefix ? "rounded-r-lg" : "rounded-lg"} ${className}`}
        />
      </div>
      {error ? (
        <p className="text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : (
        helper && <p className="text-xs text-slate-500">{helper}</p>
      )}
    </div>
  )
}

export function ScoreRing({
  score,
  size = 120,
  label,
}: {
  score: number
  size?: number
  label?: string
}) {
  const r = (size - 16) / 2
  const circumference = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, score))
  const offset = circumference - (pct / 100) * circumference
  const color = score >= 80 ? "#059669" : score >= 60 ? "#d97706" : "#dc2626"

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth="8"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x={size / 2}
          y={size / 2 - 4}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.22}
          fontWeight="700"
          fill={color}
          fontFamily="Inter, system-ui, sans-serif"
        >
          {score}
        </text>
        <text
          x={size / 2}
          y={size / 2 + size * 0.14}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.1}
          fill="#64748b"
          fontFamily="Inter, system-ui, sans-serif"
        >
          / 100
        </text>
      </svg>
      {label && (
        <span className="text-xs font-medium text-slate-500">{label}</span>
      )}
    </div>
  )
}

export function ProgressBar({
  value,
  max,
  color = "indigo",
}: {
  value: number
  max: number
  color?: string
}) {
  const pct = (value / max) * 100
  const bg =
    value === max
      ? "bg-emerald-500"
      : value >= max * 0.7
        ? "bg-amber-500"
        : "bg-red-500"
  return (
    <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${bg} transition-all duration-500`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: string[]
  active: string
  onChange: (t: string) => void
}) {
  return (
    <div className="flex gap-1 p-1 bg-slate-100 rounded-xl">
      {tabs.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-150 ${
            active === t
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
      <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-400 text-3xl">
        {icon}
      </div>
      <div className="flex flex-col gap-1">
        <p className="font-semibold text-slate-900">{title}</p>
        <p className="text-sm text-slate-500 max-w-xs">{description}</p>
      </div>
      {action}
    </div>
  )
}

export function LoadingBlock({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <div
      className="flex items-center justify-center gap-3 py-14 text-slate-500"
      role="status"
      aria-live="polite"
    >
      <span className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      <span className="text-sm">{label ?? t("common.loading")}</span>
    </div>
  )
}

export function ErrorBlock({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  const { t } = useI18n()
  return (
    <div
      className="flex flex-col items-center gap-3 py-12 text-center"
      role="alert"
    >
      <AlertTriangle size={28} className="text-amber-500" aria-hidden="true" />
      <p className="text-sm font-semibold text-slate-800">
        {t("errors.couldNotLoad")}
      </p>
      <p className="text-sm text-slate-500 max-w-sm">{message}</p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      )}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
}) {
  // A real switch, not a clickable div: it keeps keyboard support and lets
  // assistive tech read the state of every preference toggle.
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-6 rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 ${
          checked ? "bg-indigo-600" : "bg-slate-200"
        }`}
      >
        <span
          className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
            checked ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </button>
      {label && <span className="text-sm text-slate-700">{label}</span>}
    </div>
  )
}
