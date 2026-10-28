import React, { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertTriangle,
  CheckCircle,
  Copy,
  FileUp,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  X,
} from "lucide-react"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  LoadingBlock,
} from "../components/ui"
import { endpoints } from "../api/endpoints"
import { api } from "../api/client"
import {
  apiErrorMessage,
  useApiList,
  useApiResource,
} from "../api/hooks/useApiResource"
import type {
  ResponseDraft,
  Review,
  ReviewImportJob,
  ReviewSource,
  ReviewSummary,
  Website,
} from "../api/types"
import { useFormat } from "../lib/useFormat"
import { useToast } from "../components/Toast"
import type { MessageKey } from "../i18n"

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5" aria-label={`${rating} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={14}
          className={
            i < Math.round(rating)
              ? "text-amber-400 fill-amber-400"
              : "text-slate-200 fill-slate-200"
          }
        />
      ))}
    </div>
  )
}

function sentimentVariant(
  sentiment: Review["sentiment"],
): "success" | "neutral" | "critical" {
  if (sentiment === "positive") return "success"
  if (sentiment === "negative") return "critical"
  return "neutral"
}

function ResponseAssistant({
  review,
  onClose,
  onSaved,
}: {
  review: Review
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useFormat()
  const [draft, setDraft] = useState<ResponseDraft | null>(
    review.has_response && review.response_draft_id !== null
      ? {
          id: review.response_draft_id,
          review: review.id,
          content: review.response_draft_content,
          status: (review.response_status ?? "draft") as ResponseDraft["status"],
          sent_at: null,
          created_at: review.created_at,
          updated_at: review.updated_at,
        }
      : null,
  )
  const [content, setContent] = useState(review.response_draft_content)
  const [loading, setLoading] = useState(!review.has_response)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await api.post<ResponseDraft>(
        endpoints.reviews.draftResponse(review.id),
      )
      setDraft(next)
      setContent(next.content)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Only generate when the review has no saved draft — opening an existing
  // draft must never overwrite the text a user already edited.
  useEffect(() => {
    if (!review.has_response) void generate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review.id, review.has_response])

  const save = async () => {
    if (!draft || !content.trim()) return
    setSaving(true)
    setError(null)
    try {
      const updated = await api.patch<ResponseDraft>(endpoints.reviews.draft(draft.id), {
        content,
      })
      setDraft(updated)
      onSaved()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto"
        role="dialog"
        aria-modal="true"
        aria-label={t("reviews.assistantAria")}
      >
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-bold text-slate-900">
            {t("reviews.assistantTitle")}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-xl leading-none"
            aria-label={t("common.close")}
          >
            ×
          </button>
        </div>

        <div className="p-5">
          <div className="p-4 bg-slate-50 rounded-xl mb-4">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              {review.rating !== null && <Stars rating={Number(review.rating)} />}
              <span className="text-xs text-slate-500">
                {review.author_name || t("reviews.anonymous")} ·{" "}
                {review.source_name || review.source_provider}
              </span>
            </div>
            <p className="text-sm text-slate-700">
              {review.text
                ? `“${review.text}”`
                : t("reviews.noReviewText")}
            </p>
          </div>

          {loading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-slate-500">
              <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              <span className="text-sm">{t("reviews.composing")}</span>
            </div>
          ) : (
            <>
              <label
                htmlFor="response-draft"
                className="text-xs font-semibold text-slate-500 uppercase tracking-wide"
              >
                {t("reviews.suggestedDraft")}
              </label>
              <textarea
                id="response-draft"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={6}
                className="mt-2 w-full px-3 py-2 text-sm border border-indigo-200 bg-indigo-50/40 rounded-xl text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y"
              />
              <p className="text-xs text-slate-400 mt-2">
                {t("reviews.draftHint")}
              </p>
            </>
          )}

          {error && (
            <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-2 flex-wrap mt-4">
            <Button size="sm" variant="outline" onClick={() => void generate()} disabled={loading}>
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              {t("reviews.regenerate")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!content}
              onClick={() => {
                void navigator.clipboard.writeText(content)
                setCopied(true)
                window.setTimeout(() => setCopied(false), 1500)
              }}
            >
              <Copy size={12} />{" "}
              {copied ? t("reviews.copied") : t("reviews.copy")}
            </Button>
            <Button
              size="sm"
              className="ml-auto"
              disabled={!draft || saving || !content.trim()}
              onClick={() => void save()}
            >
              {saving ? t("reviews.saving") : t("reviews.saveDraft")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * `Manual import` is a word and follows the interface language; Google,
 * Trustpilot and TripAdvisor are brand names and stay verbatim.
 */
const PROVIDERS: {
  value: ReviewSource["provider"]
  label?: string
  labelKey?: MessageKey
}[] = [
  { value: "manual", labelKey: "reviews.providerManual" },
  { value: "google", label: "Google" },
  { value: "trustpilot", label: "Trustpilot" },
  { value: "tripadvisor", label: "TripAdvisor" },
]

/** Import jobs reuse the scan status wording (pending/running/done/failed). */
const JOB_STATUS_KEYS: Record<string, MessageKey> = {
  pending: "status.pending",
  processing: "status.running",
  completed: "status.completed",
  failed: "status.failed",
}

function ReviewImportModal({
  onClose,
  onImported,
}: {
  onClose: () => void
  onImported: () => void
}) {
  const { t } = useFormat()
  const sources = useApiList<ReviewSource>(endpoints.reviews.sources)
  const websites = useApiList<Website>(endpoints.websites.list)
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [websiteId, setWebsiteId] = useState<number | null>(null)
  const [provider, setProvider] =
    useState<ReviewSource["provider"]>("manual")
  const [sourceName, setSourceName] = useState("")
  const [creatingSource, setCreatingSource] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [job, setJob] = useState<ReviewImportJob | null>(null)
  const [error, setError] = useState<string | null>(null)

  const effectiveSourceId = sourceId ?? sources.data[0]?.id ?? null
  const effectiveWebsiteId = websiteId ?? websites.data[0]?.id ?? null
  const jobId = job?.id ?? null
  const jobStatus = job?.status ?? null

  // The import runs in Celery; poll the job until it settles, then refresh the
  // review list so the imported rows appear without a manual reload.
  useEffect(() => {
    if (!jobId || (jobStatus !== "pending" && jobStatus !== "processing"))
      return
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const next = await api.get<ReviewImportJob>(
            endpoints.reviews.importJob(jobId),
          )
          setJob(next)
          if (next.status === "completed") onImported()
          if (next.status === "completed" || next.status === "failed") {
            window.clearInterval(timer)
          }
        } catch {
          // A transient poll failure must not kill the job view.
        }
      })()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [jobId, jobStatus, onImported])

  const createSource = async () => {
    if (!effectiveWebsiteId) {
      setError("Add a website before creating a review source.")
      return
    }
    setCreatingSource(true)
    setError(null)
    try {
      const created = await api.post<ReviewSource>(endpoints.reviews.sources, {
        website: effectiveWebsiteId,
        provider,
        name: sourceName.trim() || `${provider} import`,
        config: {},
      })
      sources.refetch()
      setSourceId(created.id)
      setSourceName("")
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setCreatingSource(false)
    }
  }

  const upload = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!effectiveSourceId || !file) {
      setError("Choose a review source and a CSV or JSON file.")
      return
    }
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append("source_id", String(effectiveSourceId))
      form.append(
        "file_type",
        file.name.toLowerCase().endsWith(".json") ? "json" : "csv",
      )
      form.append("file", file)
      const created = await api.upload<ReviewImportJob>(
        endpoints.reviews.import,
        form,
      )
      setJob(created)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 id="import-title" className="font-bold text-slate-900">
              {t("reviews.importTitle")}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {t("reviews.importSubtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label={t("reviews.closeImportAria")}
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5">
          {sources.loading || websites.loading ? (
            <LoadingBlock label={t("reviews.loadingSources")} />
          ) : (
            <>
              {sources.data.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-4">
                  <p className="text-sm font-semibold text-slate-800 mb-1">
                    {t("reviews.noSourceTitle")}
                  </p>
                  <p className="text-xs text-slate-500 mb-3">
                    {t("reviews.noSourceHint")}
                  </p>
                  <div className="grid sm:grid-cols-2 gap-2">
                    <select
                      aria-label={t("reviews.sourceWebsiteAria")}
                      value={effectiveWebsiteId ?? ""}
                      onChange={(event) =>
                        setWebsiteId(Number(event.target.value))
                      }
                      className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                    >
                      {websites.data.map((site) => (
                        <option key={site.id} value={site.id}>
                          {site.domain}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label={t("reviews.sourceProviderAria")}
                      value={provider}
                      onChange={(event) =>
                        setProvider(event.target.value as ReviewSource["provider"])
                      }
                      className="px-2 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                    >
                      {PROVIDERS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.labelKey ? t(item.labelKey) : item.label}
                        </option>
                      ))}
                    </select>
                    <input
                      value={sourceName}
                      onChange={(event) => setSourceName(event.target.value)}
                      placeholder={t("reviews.sourceName")}
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg sm:col-span-2"
                    />
                  </div>
                  <Button
                    size="sm"
                    className="mt-3"
                    disabled={creatingSource || !effectiveWebsiteId}
                    onClick={() => void createSource()}
                  >
                    {creatingSource ? "Creating…" : "Create source"}
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-2 mb-4">
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {t("reviews.sourceLabel")}
                  </label>
                  <select
                    aria-label={t("reviews.sourceLabel")}
                    value={effectiveSourceId ?? ""}
                    onChange={(event) => setSourceId(Number(event.target.value))}
                    className="px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                  >
                    {sources.data.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name} · {source.provider}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {sources.data.length > 0 && (
                <form onSubmit={upload} className="flex flex-col gap-3">
                  <label className="flex flex-col gap-1 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {t("reviews.file")}
                    <input
                      type="file"
                      accept=".csv,.json,text/csv,application/json"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                      className="mt-1 text-sm font-normal normal-case text-slate-700"
                    />
                  </label>
                  {/* Column names are the import contract: they stay verbatim
                      in both languages, only the sentence around them is translated. */}
                  <p className="text-xs text-slate-500 leading-relaxed">
                    {t("reviews.csvHint")}
                  </p>
                  <Button type="submit" disabled={uploading || !file}>
                    <FileUp size={14} />
                    {uploading
                      ? t("reviews.importing")
                      : t("reviews.startImport")}
                  </Button>
                </form>
              )}

              {job && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                  <p className="font-semibold text-slate-800">
                    {t("reviews.importStatus", {
                      status: JOB_STATUS_KEYS[job.status]
                        ? t(JOB_STATUS_KEYS[job.status])
                        : job.status,
                    })}
                    {job.status === "processing" || job.status === "pending"
                      ? "…"
                      : ""}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    {t("reviews.importSummary", {
                      imported: job.imported_count,
                      failed: job.failed_count,
                      rows: job.total_rows,
                    })}
                  </p>
                  {job.errors.length > 0 && (
                    <ul className="mt-2 text-xs text-red-600 list-disc pl-4">
                      {job.errors.slice(0, 4).map((entry) => (
                        <li key={entry}>{entry}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {error && (
                <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2" role="alert">
                  {error}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Reviews() {
  const { t, relativeTime } = useFormat()
  const { showToast } = useToast()
  const reviews = useApiList<Review>(endpoints.reviews.list)
  const summary = useApiResource<ReviewSummary>(endpoints.reviews.summary)
  const [activeReview, setActiveReview] = useState<Review | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [approvingId, setApprovingId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeError, setNoticeError] = useState(false)

  const analyzeSentiment = async (review: Review) => {
    setAnalyzingId(review.id)
    try {
      await api.post(endpoints.reviews.analyzeSentiment(review.id))
      showToast("Sentiment analysis queued.", "success")
      // The Celery task writes the new sentiment shortly after the 202.
      window.setTimeout(() => {
        reviews.refetch()
        summary.refetch()
      }, 2500)
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setAnalyzingId(null)
    }
  }

  const approveReview = async (review: Review) => {
    setApprovingId(review.id)
    try {
      await api.post(endpoints.reviews.approve(review.id))
      showToast("Review approved.", "success")
      reviews.refetch()
      summary.refetch()
    } catch (err) {
      showToast(apiErrorMessage(err), "error")
    } finally {
      setApprovingId(null)
    }
  }

  const discover = async () => {
    setDiscovering(true)
    setNotice(null)
    setNoticeError(false)
    try {
      const result = await api.post<{ total_discovered?: number }>(
        endpoints.reviews.discover,
        {},
      )
      const found = result.total_discovered ?? 0
      setNotice(
        found > 0
          ? t(found === 1 ? "reviews.discoveryFoundOne" : "reviews.discoveryFound", {
              count: found,
            })
          : t("reviews.discoveryFoundNone"),
      )
      reviews.refetch()
      summary.refetch()
    } catch (err) {
      setNoticeError(true)
      setNotice(apiErrorMessage(err))
    } finally {
      setDiscovering(false)
    }
  }

  if (reviews.loading && !reviews.data.length && !reviews.error) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <LoadingBlock label={t("reviews.loading")} />
      </div>
    )
  }

  if (reviews.error && !reviews.data.length) {
    return (
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <ErrorBlock message={reviews.error} onRetry={() => reviews.refetch()} />
      </div>
    )
  }

  const stats = summary.data
  const average = stats?.average_rating ?? null

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      {importOpen && (
        <ReviewImportModal
          onClose={() => setImportOpen(false)}
          onImported={() => {
            reviews.refetch()
            summary.refetch()
          }}
        />
      )}

      {activeReview && (
        <ResponseAssistant
          review={activeReview}
          onClose={() => setActiveReview(null)}
          onSaved={() => {
            reviews.refetch()
            summary.refetch()
          }}
        />
      )}

      <div className="flex flex-col sm:flex-row sm:items-start gap-4 mb-8">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">
            {t("reviews.title")}
          </h1>
          <p className="text-slate-500 mt-1">{t("reviews.subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2 self-start">
          <Button
            variant="outline"
            onClick={() => setImportOpen(true)}
            className="gap-2"
          >
            <FileUp size={14} /> {t("reviews.importCsv")}
          </Button>
          <Button
            variant="outline"
            onClick={() => void discover()}
            disabled={discovering}
          >
            <Search
              size={14}
              className={discovering ? "animate-pulse" : ""}
              aria-hidden="true"
            />
            {discovering
              ? t("reviews.discovering")
              : t("reviews.discoverReviews")}
          </Button>
        </div>
      </div>

      {notice && (
        <p
          className={`mb-6 text-sm rounded-lg px-3 py-2 border ${
            noticeError
              ? "text-red-700 bg-red-50 border-red-200"
              : "text-slate-700 bg-slate-50 border-slate-200"
          }`}
        >
          {notice}
        </p>
      )}

      {reviews.error && reviews.data.length > 0 && (
        <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {t("reviews.refreshFailed")} {reviews.error}
        </p>
      )}

      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">
            {t("reviews.averageRating")}
          </p>
          <div className="text-4xl font-black text-slate-900 mb-1">
            {average === null ? "—" : `${average.toFixed(1)} ★`}
          </div>
          <div className="flex justify-center">
            {average !== null && <Stars rating={average} />}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            {t(
              (stats?.total ?? 0) === 1
                ? "reviews.acrossOne"
                : "reviews.acrossMany",
              { count: stats?.total ?? 0 },
            )}
          </p>
        </Card>

        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">
            {t("reviews.totalReviews")}
          </p>
          <div className="text-4xl font-black text-slate-900 mb-1">
            {stats?.total ?? 0}
          </div>
          <p className="text-xs text-slate-400">
            {Object.entries(stats?.by_platform ?? {})
              .map(([platform, count]) => `${platform}: ${count}`)
              .join(" · ") || t("reviews.noPlatform")}
          </p>
        </Card>

        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">
            {t("reviews.newThisMonth")}
          </p>
          <div className="text-4xl font-black text-slate-900 mb-1">
            {stats?.new_this_month ?? 0}
          </div>
          <p className="text-xs text-slate-400">
            {t("reviews.awaitingResponse", {
              count: stats?.needs_response ?? 0,
            })}
          </p>
        </Card>
      </div>

      {reviews.data.length === 0 ? (
        <Card>
          <EmptyState
            icon={<MessageSquareText size={26} />}
            title={t("reviews.emptyTitle")}
            description={t("reviews.emptyHint")}
            action={
              <div className="flex flex-col items-center gap-3">
                <Button size="sm" onClick={() => void discover()} disabled={discovering}>
                  <Search size={13} /> {t("reviews.discoverPublic")}
                </Button>
                <p className="text-xs text-slate-400">
                  {stats?.sources
                    ? t("reviews.sourcesConnected", { count: stats.sources })
                    : t("reviews.noSourceConnected")}{" "}
                  {t("reviews.discoveryTargets")}
                </p>
                <Link
                  to="/app/websites"
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
                >
                  {t("reviews.manageWebsites")}
                </Link>
              </div>
            }
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {reviews.data.map((review) => (
            <Card
              key={review.id}
              className={`p-5 ${
                review.needs_response ? "border-amber-200 bg-amber-50/30" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap mb-2">
                    {review.rating !== null && (
                      <Stars rating={Number(review.rating)} />
                    )}
                    <span className="text-sm font-semibold text-slate-900">
                      {review.author_name || t("reviews.anonymous")}
                    </span>
                    <span className="text-xs text-slate-400">
                      {review.source_name || review.source_provider} ·{" "}
                      {relativeTime(review.review_date || review.created_at)}
                    </span>
                    <Badge variant={sentimentVariant(review.sentiment)}>
                      {review.sentiment}
                    </Badge>
                    {review.is_approved && (
                      <Badge variant="success">{t("reviews.approved")}</Badge>
                    )}
                    {review.needs_response && (
                      <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full border border-amber-200">
                        {t("reviews.needsResponse")}
                      </span>
                    )}
                    {review.response_status && (
                      <Badge variant="info">
                        {t("reviews.responseStatus", {
                          status: review.response_status,
                        })}
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {review.text ? `“${review.text}”` : t("reviews.noComment")}
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-100 flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  variant={review.needs_response ? "primary" : "outline"}
                  onClick={() => setActiveReview(review)}
                >
                  <MessageSquareText size={13} />
                  {review.has_response
                    ? t("reviews.openDraft")
                    : t("reviews.draftResponse")}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={analyzingId === review.id}
                  onClick={() => void analyzeSentiment(review)}
                >
                  <Sparkles size={13} />
                  {analyzingId === review.id
                    ? t("reviews.analyzing")
                    : t("reviews.reanalyze")}
                </Button>
                {!review.is_approved && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={approvingId === review.id}
                    onClick={() => void approveReview(review)}
                  >
                    <CheckCircle size={13} />
                    {approvingId === review.id
                      ? t("reviews.approving")
                      : t("reviews.approve")}
                  </Button>
                )}
                {review.needs_response && (
                  <span className="text-xs text-amber-700 flex items-center gap-1">
                    <AlertTriangle size={11} aria-hidden="true" />
                    {t("reviews.negativeLegend")}
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
