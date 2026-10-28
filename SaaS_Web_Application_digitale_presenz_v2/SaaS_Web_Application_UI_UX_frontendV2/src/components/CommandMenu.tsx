import React, { useState, useEffect, useMemo, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useT, type MessageKey } from "../i18n"
import {
  Search,
  LayoutDashboard,
  Globe,
  ScanSearch,
  Activity,
  Bell,
  FileText,
  Settings,
  CreditCard,
  HelpCircle,
  ArrowRight,
  Zap,
} from "lucide-react"

type CommandItem = {
  id: string
  labelKey: MessageKey
  descriptionKey?: MessageKey
  icon: React.FC<{ size?: number; className?: string }>
  path: string
  categoryKey: MessageKey
}

/** Navigation entries; every visible string is a catalogue key. */
const commands: CommandItem[] = [
  {
    id: "dashboard",
    labelKey: "app.navOverview",
    descriptionKey: "commandMenu.dashboard",
    icon: LayoutDashboard,
    path: "/app/dashboard",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "websites",
    labelKey: "app.navWebsites",
    descriptionKey: "commandMenu.websites",
    icon: Globe,
    path: "/app/websites",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "scans",
    labelKey: "app.navScans",
    descriptionKey: "commandMenu.scans",
    icon: ScanSearch,
    path: "/app/scans",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "monitoring",
    labelKey: "app.navMonitoring",
    descriptionKey: "commandMenu.monitoring",
    icon: Activity,
    path: "/app/monitoring",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "alerts",
    labelKey: "app.navAlerts",
    descriptionKey: "commandMenu.alerts",
    icon: Bell,
    path: "/app/alerts",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "reports",
    labelKey: "app.navReports",
    descriptionKey: "commandMenu.reports",
    icon: FileText,
    path: "/app/reports",
    categoryKey: "commandMenu.categoryNavigation",
  },
  {
    id: "settings",
    labelKey: "app.navSettings",
    descriptionKey: "commandMenu.settings",
    icon: Settings,
    path: "/app/settings",
    categoryKey: "commandMenu.categorySettings",
  },
  {
    id: "billing",
    labelKey: "app.navBilling",
    descriptionKey: "commandMenu.billing",
    icon: CreditCard,
    path: "/app/billing",
    categoryKey: "commandMenu.categorySettings",
  },
  {
    id: "help",
    labelKey: "commandMenu.help",
    descriptionKey: "commandMenu.helpDescription",
    icon: HelpCircle,
    path: "/app/settings",
    categoryKey: "commandMenu.categorySettings",
  },
  {
    id: "scan-new",
    labelKey: "dashboard.runScan",
    descriptionKey: "commandMenu.scanNew",
    icon: Zap,
    path: "/app/websites",
    categoryKey: "commandMenu.categoryActions",
  },
]

export default function CommandMenu({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const t = useT()

  // Search runs against the translated labels, so a German user can type
  // "Überwachung" as well as "Monitoring".
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return commands
    return commands.filter((command) => {
      const label = t(command.labelKey).toLowerCase()
      const description = command.descriptionKey
        ? t(command.descriptionKey).toLowerCase()
        : ""
      return label.includes(needle) || description.includes(needle)
    })
  }, [query, t])

  useEffect(() => {
    if (open) {
      setQuery("")
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    setSelected(0)
  }, [query])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
        return
      }
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelected((i) => Math.min(i + 1, filtered.length - 1))
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelected((i) => Math.max(i - 1, 0))
      }
      if (e.key === "Enter") {
        e.preventDefault()
        const item = filtered[selected]
        if (item) {
          navigate(item.path)
          onClose()
        }
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, filtered, selected, navigate, onClose])

  if (!open) return null

  const grouped = filtered.reduce<Record<string, CommandItem[]>>((acc, cmd) => {
    if (!acc[cmd.categoryKey]) acc[cmd.categoryKey] = []
    acc[cmd.categoryKey].push(cmd)
    return acc
  }, {})

  let flatIndex = 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t("app.commandMenu")}
    >
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
          <Search size={16} className="text-slate-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder={t("app.commandMenuSearch")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 text-sm text-slate-900 placeholder:text-slate-400 outline-none bg-transparent"
            aria-label={t("app.commandMenuSearch")}
          />
          <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 text-xs border border-slate-200 rounded text-slate-400 font-mono">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto py-2">
          {filtered.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-400 text-center">
              {t("commandMenu.noResults", { query })}
            </p>
          ) : (
            Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <p className="px-4 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                  {t(category as MessageKey)}
                </p>
                {items.map((item) => {
                  const idx = flatIndex++
                  const isSelected = idx === selected
                  return (
                    <button
                      key={item.id}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                        isSelected ? "bg-indigo-50" : "hover:bg-slate-50"
                      }`}
                      onMouseEnter={() => setSelected(idx)}
                      onClick={() => {
                        navigate(item.path)
                        onClose()
                      }}
                    >
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          isSelected ? "bg-indigo-100" : "bg-slate-100"
                        }`}
                      >
                        <item.icon
                          size={15}
                          className={
                            isSelected ? "text-indigo-600" : "text-slate-500"
                          }
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-sm font-medium ${
                            isSelected ? "text-indigo-700" : "text-slate-800"
                          }`}
                        >
                          {t(item.labelKey)}
                        </p>
                        {item.descriptionKey && (
                          <p className="text-xs text-slate-400 truncate">
                            {t(item.descriptionKey)}
                          </p>
                        )}
                      </div>
                      {isSelected && (
                        <ArrowRight
                          size={14}
                          className="text-indigo-400 flex-shrink-0"
                        />
                      )}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-slate-100 text-[10px] text-slate-400">
          <span>
            <kbd className="font-mono">↑↓</kbd> {t("commandMenu.navigate")}
          </span>
          <span>
            <kbd className="font-mono">↵</kbd> {t("app.commandMenuOpen")}
          </span>
          <span>
            <kbd className="font-mono">esc</kbd> {t("app.commandMenuClose")}
          </span>
        </div>
      </div>
    </div>
  )
}
