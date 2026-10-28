import { useEffect, useRef, useState } from "react"
import {
  AlertTriangle,
  Bot,
  Loader2,
  Lock,
  Send,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react"

import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { isApiError } from "../api/errors"
import type { AdvisorChatResponse, OrganizationRole } from "../api/types"
import { renderMarkdown } from "../lib/markdown"
import { useT, type MessageKey } from "../i18n"
import { Badge, Button, Card } from "./ui"

type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

/** Mirrors the backend: owners, administrators and analysts may ask. */
const ADVISOR_ROLES: OrganizationRole[] = ["owner", "admin", "analyst"]

/** Mirrors `AdvisorChatRequestSerializer.message` (3..2000 characters). */
const MAX_QUESTION_CHARS = 2_000
const MIN_QUESTION_CHARS = 3

type Author = "user" | "assistant"

interface ChatMessage {
  id: string
  author: Author
  content: string
  /** Rendered as a friendly alert instead of Markdown. */
  failure?: { title: string; text: string }
}

interface FailureCopy {
  title: string
  text: string
  /** Permission/session problems disable the composer instead of inviting a retry. */
  blocking: boolean
}

/**
 * Map an HTTP failure to operator-facing copy.
 *
 * The provider's own message is deliberately not shown: it is English, aimed
 * at developers, and can change at any time. The three cases the mission cares
 * about are explicit: 503 (provider down), 403 (no role) and an expired session.
 */
function describeFailure(error: unknown, t: Translate): FailureCopy {
  const status = isApiError(error) ? error.status : 0

  if (status === 503) {
    return {
      title: t("advisor.errorUnavailableTitle"),
      text: t("advisor.errorUnavailableBody"),
      blocking: false,
    }
  }
  if (status === 403) {
    return {
      title: t("advisor.errorForbiddenTitle"),
      text: t("advisor.errorForbiddenBody"),
      blocking: true,
    }
  }
  if (status === 401) {
    return {
      title: t("advisor.errorSessionTitle"),
      text: t("advisor.errorSessionBody"),
      blocking: true,
    }
  }
  if (status === 400) {
    return {
      title: t("advisor.errorBadRequestTitle"),
      text: t("advisor.errorBadRequestBody", {
        min: MIN_QUESTION_CHARS,
        max: MAX_QUESTION_CHARS,
      }),
      blocking: false,
    }
  }
  return {
    title: t("advisor.errorGenericTitle"),
    text: t("advisor.errorGenericBody"),
    blocking: false,
  }
}

/** Sanitised Markdown block used for assistant answers. */
function AssistantContent({ source }: { source: string }) {
  return (
    <div
      className="text-sm leading-relaxed text-slate-800 [&_a]:text-indigo-600 [&_a]:underline [&_code]:rounded [&_code]:bg-slate-200/70 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.8em] [&_h3]:mb-2 [&_h3]:mt-3 [&_h3]:font-semibold [&_h4]:mb-2 [&_h4]:mt-3 [&_h4]:font-semibold [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-900 [&_pre]:p-3 [&_pre]:text-slate-100 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-5"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(source) }}
    />
  )
}

/**
 * Conversational panel for the Presence AI Security Advisor.
 *
 * Conversation history lives in component state only: the backend is
 * stateless and nothing is persisted server-side, so the transcript disappears
 * with the page (and with an organization switch, because the parent remounts
 * this component with a `key`). Answers explain findings; they never change
 * them, which the header states explicitly.
 */
export default function SecurityAdvisorChat({
  organizationId,
  orgName,
  role,
  assetId = null,
  assetDomain = null,
}: {
  organizationId: string
  orgName: string
  role: OrganizationRole | null
  /** Optional per-asset focus chosen on the asset page. */
  assetId?: number | null
  assetDomain?: string | null
}) {
  const t = useT()
  const canAsk = role ? ADVISOR_ROLES.includes(role) : false

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState("")
  const [sending, setSending] = useState(false)
  const [blocked, setBlocked] = useState<FailureCopy | null>(null)

  const transcriptRef = useRef<HTMLDivElement | null>(null)
  const idRef = useRef(0)
  const nextId = () => {
    idRef.current += 1
    return `m${idRef.current}`
  }

  useEffect(() => {
    const node = transcriptRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages, sending])

  const append = (message: ChatMessage) =>
    setMessages((previous) => [...previous, message])

  const ask = async () => {
    const question = draft.trim()
    if (!canAsk || sending || blocked) return
    if (question.length < MIN_QUESTION_CHARS) return

    append({ id: nextId(), author: "user", content: question })
    setDraft("")
    setSending(true)

    try {
      const answer = await api.post<AdvisorChatResponse>(
        endpoints.advisory.chat(organizationId),
        // The asset is a hint: the backend resolves it inside this
        // organization and ignores another tenant's id.
        assetId ? { message: question, asset_id: assetId } : { message: question },
      )
      append({ id: nextId(), author: "assistant", content: answer.reply })
    } catch (error) {
      const failure = describeFailure(error, t)
      append({
        id: nextId(),
        author: "assistant",
        content: failure.text,
        failure: { title: failure.title, text: failure.text },
      })
      if (failure.blocking) setBlocked(failure)
    } finally {
      setSending(false)
    }
  }

  const clearConversation = () => {
    setMessages([])
    setDraft("")
  }

  if (!canAsk) {
    return (
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-amber-50">
            <Lock size={18} className="text-amber-600" aria-hidden="true" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-900">
              {t("advisorChat.restrictedTitle")}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {t("advisorChat.restrictedBody", { organization: orgName })}
            </p>
            <Badge variant="neutral" className="mt-3">
              {t("advisorChat.yourRole", {
                role: role ?? t("advisorChat.noMembership"),
              })}
            </Badge>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card className="flex flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50">
            <Bot size={19} className="text-indigo-600" aria-hidden="true" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-900">
              {t("advisor.chatTitle")}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {assetDomain
                ? t("advisor.chatSubtitleAsset", {
                    domain: assetDomain,
                    org: orgName,
                  })
                : t("advisor.chatSubtitle", { org: orgName })}
            </p>
          </div>
        </div>
        {messages.length > 0 && !sending && (
          <Button variant="ghost" size="sm" onClick={clearConversation}>
            <Trash2 size={14} aria-hidden="true" />
            {t("advisorChat.clear")}
          </Button>
        )}
      </div>

      <div
        ref={transcriptRef}
        role="log"
        aria-live="polite"
        aria-busy={sending}
        aria-label={`Conversation with the security advisor for ${orgName}`}
        className="flex max-h-[30rem] min-h-[16rem] flex-col gap-3 overflow-y-auto p-5"
      >
        {messages.length === 0 && !sending ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100">
              <ShieldCheck
                size={22}
                className="text-slate-400"
                aria-hidden="true"
              />
            </div>
            <p className="text-sm font-medium text-slate-700">
              {t("advisorChat.askAbout", { target: assetDomain ?? orgName })}
            </p>
            <p className="max-w-sm text-xs text-slate-500">
              {t("advisorChat.examples")}
            </p>
          </div>
        ) : null}

        {messages.map((message) =>
          message.author === "user" ? (
            <div
              key={message.id}
              className="ml-auto flex max-w-[85%] items-start gap-2"
            >
              <div className="rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm text-white">
                <span className="sr-only">{t("advisor.youSaid")}</span>
                <p className="whitespace-pre-wrap break-words">
                  {message.content}
                </p>
              </div>
              <div className="mt-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100">
                <UserRound
                  size={13}
                  className="text-indigo-700"
                  aria-hidden="true"
                />
              </div>
            </div>
          ) : message.failure ? (
            <div
              key={message.id}
              role="alert"
              className="mr-auto flex max-w-[90%] items-start gap-2"
            >
              <div className="mt-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-amber-100">
                <AlertTriangle
                  size={13}
                  className="text-amber-700"
                  aria-hidden="true"
                />
              </div>
              <div className="rounded-2xl rounded-bl-sm border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-sm font-semibold text-amber-900">
                  {message.failure.title}
                </p>
                <p className="mt-1 text-sm text-amber-800">
                  {message.failure.text}
                </p>
              </div>
            </div>
          ) : (
            <div
              key={message.id}
              className="mr-auto flex max-w-[90%] items-start gap-2"
            >
              <div className="mt-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-100">
                <Bot size={13} className="text-slate-600" aria-hidden="true" />
              </div>
              <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="sr-only">{t("advisor.advisorSaid")}</span>
                <AssistantContent source={message.content} />
              </div>
            </div>
          ),
        )}

        {sending && (
          <div className="mr-auto flex items-center gap-2">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-100">
              <Bot size={13} className="text-slate-600" aria-hidden="true" />
            </div>
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              <Loader2
                size={14}
                className="animate-spin text-indigo-600"
                aria-hidden="true"
              />
              {t("advisorChat.reading")}
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-100 p-4">
        {blocked ? (
          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <Lock
              size={15}
              className="mt-0.5 flex-shrink-0"
              aria-hidden="true"
            />
            <p>{blocked.text}</p>
          </div>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void ask()
            }}
          >
            <label htmlFor="advisor-question" className="sr-only">
              {t("advisorChat.askLabel")}
            </label>
            <textarea
              id="advisor-question"
              value={draft}
              rows={3}
              maxLength={MAX_QUESTION_CHARS}
              disabled={sending}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  void ask()
                }
              }}
              placeholder={t("advisor.placeholder")}
              className="w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] text-slate-400">
                {t("advisor.composerHint")}
                {draft.length > MAX_QUESTION_CHARS - 200 && (
                  <span className="ml-1 font-medium text-slate-500">
                    {draft.length}/{MAX_QUESTION_CHARS}
                  </span>
                )}
              </p>
              <Button
                type="submit"
                size="sm"
                disabled={
                  sending || draft.trim().length < MIN_QUESTION_CHARS
                }
              >
                {sending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Send size={14} aria-hidden="true" />
                )}
                {sending ? "Sending…" : "Send"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </Card>
  )
}
