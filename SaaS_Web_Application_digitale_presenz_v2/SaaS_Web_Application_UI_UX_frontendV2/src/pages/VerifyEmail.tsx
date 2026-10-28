import React, { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { AlertCircle, CheckCircle, Loader2, Mail } from "lucide-react"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { apiErrorMessage } from "../api/errors"
import { useAuth } from "../api/hooks/useAuth"
import SEO from "../components/SEO"
import { useFormat } from "../lib/useFormat"
import { useI18n } from "../i18n"

/**
 * Landing page for the verification link sent by `send_verification_email`
 * (`/verify-email?uid=<uidb64>&token=<token>`).
 *
 * The link is single-use in practice: the backend validates the token on POST
 * and marks the account verified. Opening the page always performs the call
 * once, so a refresh after success surfaces the "already verified" branch
 * instead of silently doing nothing.
 */

type VerifyState = "verifying" | "success" | "error" | "missing"

function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useFormat()
  return (
    <div className="min-h-full bg-slate-50 flex flex-col">
      <SEO
        title={t("verifyEmail.seoTitle")}
        description={t("verifyEmail.seoDescription")}
        noIndex
        path="/verify-email"
      />
      <header className="p-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle
                cx="8"
                cy="8"
                r="6"
                stroke="white"
                strokeWidth="1.5"
                opacity="0.5"
              />
              <circle cx="8" cy="8" r="3" fill="white" />
            </svg>
          </div>
          <span className="font-bold text-slate-900">Presence</span>
        </Link>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-sm">
          <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function VerifyEmail() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const { user, refreshUser } = useAuth()
  const [state, setState] = useState<VerifyState>("verifying")
  const [message, setMessage] = useState("")
  const [resending, setResending] = useState(false)
  const [resendNotice, setResendNotice] = useState("")
  const started = useRef(false)

  const uidb64 = searchParams.get("uid")
  const token = searchParams.get("token")

  useEffect(() => {
    // React StrictMode mounts effects twice in development: the token is
    // single-use, so only the first invocation may hit the endpoint.
    if (started.current) return
    started.current = true

    if (!uidb64 || !token) {
      setState("missing")
      return
    }

    const verify = async () => {
      try {
        await api.post(endpoints.auth.emailVerify, { uidb64, token })
        setState("success")
        // Signed-in visitors are almost always redirected from the signup
        // banner: refresh so `is_email_verified` is no longer stale.
        await refreshUser()
      } catch (error) {
        setState("error")
        setMessage(
          apiErrorMessage(error, t("verifyEmail.invalidLink")),
        )
      }
    }

    void verify()
  }, [uidb64, token, refreshUser])

  const resend = async () => {
    setResending(true)
    setResendNotice("")
    try {
      await api.post(endpoints.auth.emailVerifyResend)
      setResendNotice(t("verifyEmail.resendSent"))
    } catch (error) {
      setResendNotice(apiErrorMessage(error, t("verifyEmail.resendFailed")))
    } finally {
      setResending(false)
    }
  }

  if (state === "verifying") {
    return (
      <Shell>
        <div className="w-12 h-12 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-4">
          <Loader2 size={22} className="text-indigo-600 animate-spin" />
        </div>
        <p className="font-semibold text-slate-900 mb-2">
          {t("verifyEmail.verifyingTitle")}
        </p>
        <p className="text-sm text-slate-500">{t("verifyEmail.verifyingHint")}</p>
      </Shell>
    )
  }

  if (state === "success") {
    return (
      <Shell>
        <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle size={24} className="text-emerald-600" />
        </div>
        <p className="font-semibold text-slate-900 mb-2">
          {t("verifyEmail.successTitle")}
        </p>
        <p className="text-sm text-slate-500 mb-6">
          {t("verifyEmail.successHint")}
        </p>
        <Link
          to={user ? "/app/dashboard" : "/login"}
          className="inline-flex w-full items-center justify-center px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
        >
          {user ? t("verifyEmail.goToDashboard") : t("auth.signIn")}
        </Link>
        {!user && (
          <p className="text-xs text-slate-400 mt-4">
            {t("verifyEmail.noAccountYet")}{" "}
            <Link
              to="/register"
              className="text-indigo-600 font-medium hover:text-indigo-700"
            >
              {t("verifyEmail.createFree")}
            </Link>
          </p>
        )}
      </Shell>
    )
  }

  const isMissing = state === "missing"

  return (
    <Shell>
      <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <AlertCircle size={24} className="text-red-600" />
      </div>
      <p className="font-semibold text-slate-900 mb-2">
        {isMissing
          ? t("verifyEmail.incompleteLink")
          : t("verifyEmail.verificationFailed")}
      </p>
      <p className="text-sm text-slate-500 mb-6">
        {isMissing ? t("verifyEmail.incompleteLinkHint") : message}
      </p>

      {user ? (
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => void resend()}
            disabled={resending}
            className="inline-flex w-full items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            <Mail size={14} />
            {resending ? t("verifyEmail.sending") : t("verifyEmail.sendNewLink")}
          </button>
          {resendNotice && (
            <p className="text-xs text-slate-500" role="status">
              {resendNotice}
            </p>
          )}
          <Link
            to="/app/dashboard"
            className="text-sm text-indigo-600 font-medium hover:text-indigo-700 mt-2"
          >
            {t("verifyEmail.backToDashboard")}
          </Link>
        </div>
      ) : (
        <>
          <Link
            to="/login"
            className="inline-flex w-full items-center justify-center px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
          >
            {t("auth.signIn")}
          </Link>
          <p className="text-xs text-slate-400 mt-4">
            {t("verifyEmail.signInToRequest")}{" "}
            <Link
              to="/register"
              className="text-indigo-600 font-medium hover:text-indigo-700"
            >
              {t("verifyEmail.createAccount")}
            </Link>
            .
          </p>
        </>
      )}
    </Shell>
  )
}
