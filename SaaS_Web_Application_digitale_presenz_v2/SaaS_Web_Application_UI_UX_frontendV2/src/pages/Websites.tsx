import React, { useState } from "react"
import { Link } from "react-router-dom"
import { Globe, Plus, RefreshCw, Trash2, X } from "lucide-react"
import {
  Card,
  StatusBadge,
  ScoreRing,
  Button,
  Input,
  LoadingBlock,
  ErrorBlock,
  EmptyState,
} from "../components/ui"
import { useToast } from "../components/Toast"
import { useFormat } from "../lib/useFormat"
import { UpgradeBadge, useUpgrade } from "../components/UpgradePrompt"
import { usePlan } from "../contexts/PlanContext"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { useApiList, apiErrorMessage } from "../api/hooks/useApiResource"
import type { Website } from "../api/types"
import { healthStatusTone } from "../lib/format"

export default function Websites() {
  const { t, healthStatusLabel, relativeTime } = useFormat()
  const { showToast } = useToast()
  const { guard } = useUpgrade()
  const { refresh: refreshPlan } = usePlan()
  const [refreshKey, setRefreshKey] = useState(0)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [domain, setDomain] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [busySite, setBusySite] = useState<number | null>(null)

  const { data: websites, error, loading, refetch } = useApiList<Website>(
    endpoints.websites.list,
    refreshKey,
    // Keep progress visible while a scan is running.
    0,
  )

  const refresh = () => setRefreshKey((key) => key + 1)

  const closeDialog = () => {
    setDialogOpen(false)
    setDomain("")
  }

  const handleAdd = async (event: React.FormEvent) => {
    event.preventDefault()
    const candidate = domain.trim()
    if (!candidate) return
    // At the plan's website ceiling, sell the upgrade before the 403.
    if (!guard("websites.extra")) return

    setSubmitting(true)
    try {
      await api.post(endpoints.websites.create, { domain: candidate })
      showToast(t("websites.added", { domain: candidate }), "success")
      closeDialog()
      refresh()
      // Keep the website quota badge truthful after crossing the limit.
      refreshPlan()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setSubmitting(false)
    }
  }

  const handleScan = async (site: Website) => {
    if (!guard("scans.extra")) return
    setBusySite(site.id)
    try {
      const scan = await api.post<{ id: number }>(endpoints.websites.scan(site.id))
      showToast(
        t("websites.scanQueued", { id: scan.id, domain: site.domain }),
        "success",
      )
      refresh()
      refreshPlan()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusySite(null)
    }
  }

  const handleDelete = async (site: Website) => {
    if (
      !window.confirm(t("websites.deleteConfirm", { domain: site.domain }))
    ) {
      return
    }
    setBusySite(site.id)
    try {
      await api.delete(endpoints.websites.detail(site.id))
      showToast(t("websites.deleted", { domain: site.domain }), "success")
      refresh()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setBusySite(null)
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {t("websites.title")}
          </h1>
          <p className="text-slate-500 mt-1">{t("websites.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <UpgradeBadge feature="websites.extra" />
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={16} /> {t("websites.add")}
          </Button>
        </div>
      </div>

      {loading && !websites.length ? (
        <LoadingBlock label={t("websites.loading")} />
      ) : error && !websites.length ? (
        <ErrorBlock message={error} onRetry={refetch} />
      ) : websites.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Globe size={26} />}
            title={t("websites.emptyTitle")}
            description={t("websites.emptyBody")}
            action={
              <Button onClick={() => setDialogOpen(true)} className="gap-1.5">
                <Plus size={14} /> {t("websites.add")}
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {websites.map((site) => (
            <Card key={site.id} className="p-5 h-full flex flex-col">
              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                  <Globe size={18} className="text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/app/websites/${site.id}`}
                    className="font-semibold text-slate-900 truncate hover:text-indigo-600 transition-colors block font-mono"
                  >
                    {site.domain}
                  </Link>
                  <StatusBadge
                    status={healthStatusTone(site.health_status)}
                    label={healthStatusLabel(site.health_status)}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between mb-4 flex-1">
                {site.health_score === null ? (
                  <div className="flex flex-col items-center gap-1">
                    <div className="w-[72px] h-[72px] rounded-full border-8 border-slate-100 flex items-center justify-center">
                      <span className="text-lg font-bold text-slate-300">—</span>
                    </div>
                    <span className="text-xs font-medium text-slate-500">
                      {t("websites.healthScore")}
                    </span>
                  </div>
                ) : (
                  <ScoreRing
                    score={site.health_score}
                    size={72}
                    label={t("websites.healthScore")}
                  />
                )}
                <div className="flex flex-col gap-2 text-right">
                  <div>
                    <p className="text-xs text-slate-500">
                      {t("websites.lastScan")}
                    </p>
                    <p className="text-sm font-semibold text-slate-800">
                      {relativeTime(site.last_scan_at)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">
                      {t("websites.monitoring")}
                    </p>
                    <p className="text-sm font-semibold text-slate-800">
                      {site.is_active
                        ? t("websites.active")
                        : t("websites.paused")}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2 pt-3 border-t border-slate-100">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busySite === site.id}
                  onClick={() => handleScan(site)}
                >
                  <RefreshCw
                    size={13}
                    className={busySite === site.id ? "animate-spin" : ""}
                  />
                  {t("websites.runScan")}
                </Button>
                <div className="flex items-center gap-1">
                  <Link
                    to={`/app/websites/${site.id}`}
                    className="text-xs text-indigo-600 hover:text-indigo-700 font-medium px-2 py-1"
                  >
                    {t("websites.details")}
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busySite === site.id}
                    onClick={() => handleDelete(site)}
                    className="text-red-500 hover:text-red-600 hover:bg-red-50"
                  >
                    <Trash2 size={13} />
                  </Button>
                </div>
              </div>
            </Card>
          ))}

          {/* Add website card */}
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="border-2 border-dashed border-slate-200 rounded-2xl p-5 flex flex-col items-center justify-center text-center min-h-48 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all group"
          >
            <div className="w-12 h-12 bg-slate-100 group-hover:bg-indigo-100 rounded-xl flex items-center justify-center mb-3 transition-colors">
              <Plus
                size={20}
                className="text-slate-400 group-hover:text-indigo-600 transition-colors"
              />
            </div>
            <p className="font-medium text-slate-600 group-hover:text-indigo-700 transition-colors">
              {t("websites.add")}
            </p>
            <p className="text-sm text-slate-400 mt-1">
              {t("websites.addHint")}
            </p>
          </button>
        </div>
      )}

      {/* Add website dialog */}
      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={t("websites.add")}
        >
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="font-bold text-slate-900">
                  {t("websites.dialogTitle")}
                </h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  {t("websites.dialogSubtitle")}
                </p>
              </div>
              <button
                type="button"
                onClick={closeDialog}
                className="text-slate-400 hover:text-slate-600"
                aria-label={t("common.close")}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAdd} className="flex flex-col gap-4">
              <Input
                label={t("websites.domainLabel")}
                placeholder="example.com"
                value={domain}
                onChange={setDomain}
                helper={t("websites.domainHelper")}
              />
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={closeDialog}>
                  {t("websites.cancel")}
                </Button>
                <Button type="submit" disabled={submitting || !domain.trim()}>
                  {submitting ? t("websites.adding") : t("websites.add")}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
