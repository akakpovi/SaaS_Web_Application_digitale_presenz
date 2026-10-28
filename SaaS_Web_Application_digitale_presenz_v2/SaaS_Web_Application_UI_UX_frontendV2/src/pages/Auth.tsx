import React, { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import {
  ArrowLeft,
  Eye,
  EyeOff,
  Mail,
  Lock,
  AlertCircle,
} from "lucide-react"
import { Button, Input } from "../components/ui"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"
import { useAuth } from "../api/hooks/useAuth"
import {
  apiErrorMessage,
  apiFieldErrors,
  type FieldErrors,
} from "../api/errors"
import { useToast } from "../components/Toast"

function AuthShell({
  children,
  title,
  subtitle,
}: {
  children: React.ReactNode
  title: string
  subtitle?: string
}) {
  return (
    <div className="min-h-full bg-slate-50 flex flex-col">
      <SEO
        title={title}
        description={subtitle || title}
        noIndex
        path="/login"
      />
      {/* Header */}
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
        <LanguageSwitcher />
      </header>

      {/* Card */}
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-sm">
          <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
              {subtitle && (
                <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
              )}
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

export function Login() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const { login } = useAuth()
  const { showToast } = useToast()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setFieldErrors({})
    setIsSubmitting(true)
    try {
      await login({ email, password })
      showToast(t("auth.welcomeBackToast"), "success")
      navigate("/app/dashboard", { replace: true })
    } catch (err: unknown) {
      // DRF answers a rejected credential with `detail`; surface its wording
      // instead of a generic fallback (and never the refresh "Session expired").
      const fields = apiFieldErrors(err)
      const message = apiErrorMessage(err, t("auth.errSignin"))
      setFieldErrors(fields)
      setError(message)
      showToast(message, "error")
    } finally {
      setIsSubmitting(false)
    }
  }

  const errorShownOnField = Boolean(fieldErrors.email || fieldErrors.password)

  return (
    <AuthShell title={t("auth.loginTitle")} subtitle={t("auth.loginSubtitle")}>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <Input
          label={t("auth.emailAddress")}
          type="email"
          placeholder={t("auth.emailPlaceholder")}
          value={email}
          onChange={setEmail}
          error={fieldErrors.email?.[0]}
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">
            {t("common.password")}
          </label>
          <div className="relative">
            <input
              type={showPass ? "text" : "password"}
              placeholder={t("auth.passwordPlaceholder")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={fieldErrors.password ? true : undefined}
              className={`w-full px-3 py-2 pr-10 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent ${
                fieldErrors.password
                  ? "border-red-400 focus:ring-red-400"
                  : "border-slate-300 focus:ring-indigo-500"
              }`}
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              disabled={isSubmitting}
            >
              {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          {fieldErrors.password?.[0] && (
            <p className="text-xs text-red-600" role="alert">
              {fieldErrors.password[0]}
            </p>
          )}
          <div className="text-right">
            <Link
              to="/forgot-password"
              className="text-xs text-indigo-600 hover:text-indigo-700"
            >
              {t("auth.forgotPassword")}
            </Link>
          </div>
        </div>

        {error && !errorShownOnField && (
          <div
            className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3"
            role="alert"
          >
            {error}
          </div>
        )}

        <Button type="submit" className="w-full mt-2" disabled={isSubmitting}>
          {isSubmitting ? t("auth.signingIn") : t("auth.signIn")}
        </Button>

        <div className="relative flex items-center gap-3 my-2">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400">{t("auth.or")}</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <button
          type="button"
          disabled
          className="w-full flex items-center justify-center gap-3 border border-slate-300 rounded-lg py-2.5 text-sm font-medium text-slate-500 bg-slate-50 cursor-not-allowed"
          title={t("auth.googleUnavailable")}
        >
          <svg width="16" height="16" viewBox="0 0 18 18">
            <path
              fill="#4285F4"
              d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"
            />
            <path
              fill="#34A853"
              d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"
            />
            <path
              fill="#FBBC05"
              d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"
            />
            <path
              fill="#EA4335"
              d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"
            />
          </svg>
          {t("auth.googleUnavailable")}
        </button>

        <p className="text-center text-sm text-slate-500">
          {t("auth.noAccount")}{" "}
          <Link
            to="/register"
            className="text-indigo-600 font-medium hover:text-indigo-700"
          >
            {t("auth.signUpLink")}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}

export function Register() {
  const navigate = useNavigate()
  const { t, locale } = useI18n()
  const { register } = useAuth()
  const { showToast } = useToast()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setFieldErrors({})
    setIsSubmitting(true)
    try {
      // The API field is `full_name`; sending `name` silently dropped the name.
      // The UI language travels with the sign-up so the verification e-mail is
      // sent in German for the German first launch, not in English.
      await register({ full_name: name, email, password, language: locale })
      showToast(t("auth.accountCreatedToast"), "success")
      navigate("/login?registered=true", { replace: true })
    } catch (err: unknown) {
      // A duplicate address arrives as `{email: [...]}`, a weak password as
      // `{password: [...]}`; each one is attached to its own input below.
      const fields = apiFieldErrors(err)
      const message = apiErrorMessage(err, t("auth.errRegister"))
      setFieldErrors(fields)
      setError(message)
      showToast(message, "error")
    } finally {
      setIsSubmitting(false)
    }
  }

  const errorShownOnField = Boolean(
    fieldErrors.full_name || fieldErrors.email || fieldErrors.password,
  )

  return (
    <AuthShell title={t("auth.registerTitle")} subtitle={t("auth.registerSubtitle")}>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <Input
          label={t("auth.fullName")}
          placeholder="Maria Schmidt"
          value={name}
          onChange={setName}
          disabled={isSubmitting}
          error={fieldErrors.full_name?.[0]}
        />
        <Input
          label={t("auth.emailAddress")}
          type="email"
          placeholder={t("auth.emailPlaceholder")}
          value={email}
          onChange={setEmail}
          disabled={isSubmitting}
          error={fieldErrors.email?.[0]}
        />
        <Input
          label={t("common.password")}
          type="password"
          placeholder={t("auth.minChars")}
          value={password}
          onChange={setPassword}
          disabled={isSubmitting}
          error={fieldErrors.password?.[0]}
        />

        <div className="flex items-start gap-2 mt-1">
          <input
            type="checkbox"
            id="agree"
            className="mt-0.5"
            disabled={isSubmitting}
          />
          {/* The consent text must link to the real documents: a sign-up form
              pointing at "#" does not give access to the terms it references. */}
          <label htmlFor="agree" className="text-xs text-slate-500">
            {t("auth.agreeBefore")}{" "}
            <Link to="/terms" className="text-indigo-600">
              {t("auth.termsOfService")}
            </Link>{" "}
            {t("auth.andWord")}{" "}
            <Link to="/privacy" className="text-indigo-600">
              {t("auth.privacyPolicy")}
            </Link>
          </label>
        </div>

        {error && !errorShownOnField && (
          <div
            className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3"
            role="alert"
          >
            {error}
          </div>
        )}

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? t("auth.creatingAccount") : t("auth.createAccount")}
        </Button>

        <div className="relative flex items-center gap-3 my-2">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400">{t("auth.or")}</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <button
          type="button"
          disabled
          className="w-full flex items-center justify-center gap-3 border border-slate-300 rounded-lg py-2.5 text-sm font-medium text-slate-500 bg-slate-50 cursor-not-allowed"
          title={t("auth.googleNotConfigured")}
        >
          <svg width="16" height="16" viewBox="0 0 18 18">
            <path
              fill="#4285F4"
              d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"
            />
            <path
              fill="#34A853"
              d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"
            />
            <path
              fill="#FBBC05"
              d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"
            />
            <path
              fill="#EA4335"
              d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"
            />
          </svg>
          {t("auth.googleUnavailable")}
        </button>

        <p className="text-center text-sm text-slate-500">
          {t("auth.haveAccount")}{" "}
          <Link
            to="/login"
            className="text-indigo-600 font-medium hover:text-indigo-700"
          >
            {t("auth.signIn")}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}

export function ForgotPassword() {
  const { t } = useI18n()
  const { requestPasswordReset } = useAuth()
  const { showToast } = useToast()
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setFieldErrors({})
    setIsSubmitting(true)
    try {
      await requestPasswordReset({ email })
      setSent(true)
      showToast(t("auth.resetSent"), "success")
    } catch (err: unknown) {
      setFieldErrors(apiFieldErrors(err))
      const message = apiErrorMessage(err, t("auth.errResetLink"))
      setError(message)
      showToast(message, "error")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell title={t("auth.forgotTitle")} subtitle={t("auth.forgotSubtitle")}>
      <Link
        to="/login"
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-4"
      >
        <ArrowLeft size={14} /> {t("auth.backToSignIn")}
      </Link>
      {sent ? (
        <div className="text-center py-4">
          <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Mail size={24} className="text-emerald-600" />
          </div>
          <p className="font-semibold text-slate-900 mb-2">
            {t("auth.checkEmailTitle")}
          </p>
          <p className="text-sm text-slate-500">
            {t("auth.resetLinkSentBody")}
          </p>
          <p className="text-xs text-slate-400 mt-2">
            {t("auth.linkExpires24h")}
          </p>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="relative">
            <Mail
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              size={16}
            />
            <Input
              label={t("auth.emailAddress")}
              type="email"
              placeholder={t("auth.emailPlaceholder")}
              value={email}
              onChange={setEmail}
              disabled={isSubmitting}
              className="pl-10"
              error={fieldErrors.email?.[0]}
            />
          </div>
          {error && !fieldErrors.email && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
              <AlertCircle size={14} />
              {error}
            </div>
          )}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? t("auth.sending") : t("auth.sendResetLink")}
          </Button>
        </form>
      )}
    </AuthShell>
  )
}

export function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { t } = useI18n()
  const { resetPassword } = useAuth()
  const { showToast } = useToast()
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const uidb64 = searchParams.get("uid")
  const token = searchParams.get("token")

  const isValidToken = Boolean(uidb64 && token)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setFieldErrors({})

    if (!isValidToken) {
      setError(t("auth.invalidOrMissingToken"))
      return
    }

    if (password !== confirmPassword) {
      setError(t("auth.passwordsDoNotMatch"))
      return
    }

    if (password.length < 12) {
      setError(t("auth.passwordTooShort"))
      return
    }

    setIsSubmitting(true)
    try {
      await resetPassword({
        uidb64: uidb64!,
        token: token!,
        new_password: password,
      })
      setSuccess(true)
      showToast(t("auth.resetSuccessToast"), "success")
    } catch (err: unknown) {
      setFieldErrors(apiFieldErrors(err))
      const message = apiErrorMessage(err, t("auth.errResetPassword"))
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isValidToken && !success) {
    return (
      <AuthShell
        title={t("auth.resetPassword")}
        subtitle={t("auth.invalidOrMissingToken")}
      >
        <div className="text-center py-4">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle size={24} className="text-red-600" />
          </div>
          <p className="font-semibold text-slate-900 mb-2">
            {t("auth.invalidResetLink")}
          </p>
          <p className="text-sm text-slate-500 mb-4">
            {t("auth.invalidResetLinkBody")}
          </p>
          <Link
            to="/forgot-password"
            className="text-indigo-600 font-medium hover:text-indigo-700"
          >
            {t("auth.requestNewLink")}
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title={t("auth.createNewPassword")}
      subtitle={t("auth.createNewPasswordSubtitle")}
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div className="relative">
          <Lock
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            size={16}
          />
          <Input
            label={t("auth.newPassword")}
            type={showPass ? "text" : "password"}
            placeholder={t("auth.minChars")}
            value={password}
            onChange={setPassword}
            disabled={isSubmitting}
            className="pl-10"
            error={fieldErrors.new_password?.[0]}
          />
          <button
            type="button"
            onClick={() => setShowPass(!showPass)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            disabled={isSubmitting}
          >
            {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <div className="relative">
          <Lock
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            size={16}
          />
          <Input
            label={t("auth.confirmPassword")}
            type={showPass ? "text" : "password"}
            placeholder={t("auth.confirmPasswordPlaceholder")}
            value={confirmPassword}
            onChange={setConfirmPassword}
            disabled={isSubmitting}
            className="pl-10"
          />
        </div>

        {error && !fieldErrors.new_password && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2" role="alert">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? t("auth.resetting") : t("auth.resetPassword")}
        </Button>

        <p className="text-center text-sm text-slate-500">
          <Link
            to="/login"
            className="text-indigo-600 font-medium hover:text-indigo-700"
          >
            {t("auth.backToSignIn")}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
