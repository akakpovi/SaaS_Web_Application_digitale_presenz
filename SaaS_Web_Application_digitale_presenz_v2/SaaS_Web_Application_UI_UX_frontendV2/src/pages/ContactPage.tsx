import React, { useState } from "react"
import Link from "../components/LocaleLink"
import { Mail, MessageSquare, CheckCircle } from "lucide-react"
import SEO from "../components/SEO"
import { Button } from "../components/ui"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"

function PublicNav() {
  const { t } = useI18n()
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <circle
                cx="8"
                cy="8"
                r="6"
                stroke="white"
                strokeWidth="1.5"
                opacity="0.5"
              />
              <circle cx="8" cy="8" r="3" fill="white" />
              <path
                d="M8 2v2M8 12v2M2 8h2M12 8h2"
                stroke="white"
                strokeWidth="1.5"
                strokeLinecap="round"
                opacity="0.7"
              />
            </svg>
          </div>
          <span className="font-bold text-slate-900 text-sm">Presence</span>
        </Link>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link
            to="/login"
            className="hidden sm:inline text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5"
          >
            {t("common.login")}
          </Link>
        </div>
      </div>
    </header>
  )
}

export default function ContactPage() {
  const { t } = useI18n()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const e: Record<string, string> = {}
    if (!name.trim()) e.name = t("contact.errNameRequired")
    if (!email.trim()) e.email = t("contact.errEmailRequired")
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      e.email = t("contact.errEmailInvalid")
    if (!message.trim()) e.message = t("contact.errMessageRequired")
    return e
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) {
      setErrors(errs)
      return
    }
    setErrors({})
    setSubmitted(true)
  }

  return (
    <>
      <SEO
        title={t("contact.metaTitle")}
        description={t("contact.metaDescription")}
        path="/contact"
      />
      <PublicNav />
      <main className="max-w-2xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <div className="w-12 h-12 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare size={22} className="text-indigo-600" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 mb-2 hyphens-auto break-words">
            {t("contact.h1")}
          </h1>
          <p className="text-slate-500">{t("contact.lede")}</p>
        </div>

        {submitted ? (
          <div className="text-center p-8 bg-emerald-50 border border-emerald-200 rounded-2xl">
            <CheckCircle size={32} className="text-emerald-500 mx-auto mb-3" />
            <p className="font-bold text-emerald-800 mb-1">
              {t("contact.successTitle")}
            </p>
            <p className="text-emerald-700 text-sm">
              {t("contact.successBody")}
            </p>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col gap-5"
            noValidate
          >
            <div>
              <label
                htmlFor="name"
                className="block text-sm font-medium text-slate-700 mb-1.5"
              >
                {t("contact.nameLabel")}{" "}
                <span className="text-red-500" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                aria-required="true"
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? "name-error" : undefined}
                className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  errors.name ? "border-red-400 bg-red-50" : "border-slate-300"
                }`}
              />
              {errors.name && (
                <p
                  id="name-error"
                  className="text-xs text-red-600 mt-1"
                  role="alert"
                >
                  {errors.name}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-slate-700 mb-1.5"
              >
                {t("contact.emailLabel")}{" "}
                <span className="text-red-500" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-required="true"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? "email-error" : undefined}
                className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  errors.email ? "border-red-400 bg-red-50" : "border-slate-300"
                }`}
              />
              {errors.email && (
                <p
                  id="email-error"
                  className="text-xs text-red-600 mt-1"
                  role="alert"
                >
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="message"
                className="block text-sm font-medium text-slate-700 mb-1.5"
              >
                {t("contact.messageLabel")}{" "}
                <span className="text-red-500" aria-hidden="true">
                  *
                </span>
              </label>
              <textarea
                id="message"
                rows={5}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                aria-required="true"
                aria-invalid={!!errors.message}
                aria-describedby={errors.message ? "message-error" : undefined}
                placeholder={t("contact.messagePlaceholder")}
                className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none ${
                  errors.message
                    ? "border-red-400 bg-red-50"
                    : "border-slate-300"
                }`}
              />
              {errors.message && (
                <p
                  id="message-error"
                  className="text-xs text-red-600 mt-1"
                  role="alert"
                >
                  {errors.message}
                </p>
              )}
            </div>

            <Button type="submit" className="self-start gap-2">
              <Mail size={15} /> {t("contact.submit")}
            </Button>

            <p className="text-xs text-slate-400">
              {t("contact.privacyBefore")}{" "}
              <Link to="/privacy" className="underline">
                {t("contact.privacyLink")}
              </Link>
              {t("contact.privacyAfter")}
            </p>
          </form>
        )}

        <div className="mt-8 p-5 bg-slate-50 border border-slate-200 rounded-2xl text-center">
          <p className="text-sm text-slate-600">
            <span className="font-semibold">{t("contact.existingTitle")}</span>{" "}
            <Link
              to="/app/settings"
              className="text-indigo-600 hover:underline"
            >
              {t("contact.existingOpen")}
            </Link>{" "}
            {t("contact.existingOr")}{" "}
            <Link to="/faq" className="text-indigo-600 hover:underline">
              {t("contact.existingFaq")}
            </Link>
            {t("contact.existingEnd")}
          </p>
        </div>
      </main>
      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">
          © 2026 Presence ·{" "}
          <Link to="/privacy" className="hover:text-slate-600">
            {t("footer.privacy")}
          </Link>{" "}
          ·{" "}
          <Link to="/terms" className="hover:text-slate-600">
            {t("footer.terms")}
          </Link>
        </p>
      </footer>
    </>
  )
}
