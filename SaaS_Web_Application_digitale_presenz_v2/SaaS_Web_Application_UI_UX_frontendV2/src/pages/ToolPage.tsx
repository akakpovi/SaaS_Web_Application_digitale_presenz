import React, { useEffect, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import Link from "../components/LocaleLink"
import {
  ArrowRight,
  CheckCircle,
  Loader,
  ChevronDown,
  Globe,
} from "lucide-react"
import SEO, {
  faqSchema,
  breadcrumbSchema,
  softwareAppSchema,
} from "../components/SEO"
import Breadcrumb from "../components/Breadcrumb"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { apiErrorMessage } from "../api/errors"
import { useI18n, type ListKey, type MessageKey } from "../i18n"

type ToolId =
  | "websiteChecker"
  | "sslChecker"
  | "dnsChecker"
  | "emailSecurityChecker"

interface ToolConfig {
  id: ToolId
  slug: string
  relatedTool?: { label: MessageKey; path: string }
  featurePath: string
}

/**
 * Structural configuration only: icons, paths and slugs stay in code, every
 * string comes from the catalogue. The keys are spelled out (rather than built
 * with a template literal) so `t()` keeps checking them at compile time.
 */
const STRINGS: Record<
  ToolId,
  {
    metaTitle: MessageKey
    metaDescription: MessageKey
    h1: MessageKey
    intro: MessageKey
    inputLabel: MessageKey
    buttonLabel: MessageKey
    checks: ListKey
    faqQuestions: ListKey
    faqAnswers: ListKey
    howItWorks: ListKey
  }
> = {
  websiteChecker: {
    metaTitle: "tools.websiteChecker.metaTitle",
    metaDescription: "tools.websiteChecker.metaDescription",
    h1: "tools.websiteChecker.h1",
    intro: "tools.websiteChecker.intro",
    inputLabel: "tools.websiteChecker.inputLabel",
    buttonLabel: "tools.websiteChecker.buttonLabel",
    checks: "tools.websiteChecker.checks",
    faqQuestions: "tools.websiteChecker.faqQuestions",
    faqAnswers: "tools.websiteChecker.faqAnswers",
    howItWorks: "tools.websiteChecker.howItWorks",
  },
  sslChecker: {
    metaTitle: "tools.sslChecker.metaTitle",
    metaDescription: "tools.sslChecker.metaDescription",
    h1: "tools.sslChecker.h1",
    intro: "tools.sslChecker.intro",
    inputLabel: "tools.sslChecker.inputLabel",
    buttonLabel: "tools.sslChecker.buttonLabel",
    checks: "tools.sslChecker.checks",
    faqQuestions: "tools.sslChecker.faqQuestions",
    faqAnswers: "tools.sslChecker.faqAnswers",
    howItWorks: "tools.sslChecker.howItWorks",
  },
  dnsChecker: {
    metaTitle: "tools.dnsChecker.metaTitle",
    metaDescription: "tools.dnsChecker.metaDescription",
    h1: "tools.dnsChecker.h1",
    intro: "tools.dnsChecker.intro",
    inputLabel: "tools.dnsChecker.inputLabel",
    buttonLabel: "tools.dnsChecker.buttonLabel",
    checks: "tools.dnsChecker.checks",
    faqQuestions: "tools.dnsChecker.faqQuestions",
    faqAnswers: "tools.dnsChecker.faqAnswers",
    howItWorks: "tools.dnsChecker.howItWorks",
  },
  emailSecurityChecker: {
    metaTitle: "tools.emailSecurityChecker.metaTitle",
    metaDescription: "tools.emailSecurityChecker.metaDescription",
    h1: "tools.emailSecurityChecker.h1",
    intro: "tools.emailSecurityChecker.intro",
    inputLabel: "tools.emailSecurityChecker.inputLabel",
    buttonLabel: "tools.emailSecurityChecker.buttonLabel",
    checks: "tools.emailSecurityChecker.checks",
    faqQuestions: "tools.emailSecurityChecker.faqQuestions",
    faqAnswers: "tools.emailSecurityChecker.faqAnswers",
    howItWorks: "tools.emailSecurityChecker.howItWorks",
  },
}

const toolConfigs: Record<string, ToolConfig> = {
  "website-checker": {
    id: "websiteChecker",
    slug: "website-checker",
    relatedTool: {
      label: "tools.websiteChecker.relatedLabel",
      path: "/tools/ssl-checker",
    },
    featurePath: "/features/website-monitoring",
  },
  "ssl-checker": {
    id: "sslChecker",
    slug: "ssl-checker",
    relatedTool: {
      label: "tools.sslChecker.relatedLabel",
      path: "/tools/website-checker",
    },
    featurePath: "/features/ssl-monitoring",
  },
  "dns-checker": {
    id: "dnsChecker",
    slug: "dns-checker",
    relatedTool: {
      label: "tools.dnsChecker.relatedLabel",
      path: "/tools/email-security-checker",
    },
    featurePath: "/features/dns-monitoring",
  },
  "email-security-checker": {
    id: "emailSecurityChecker",
    slug: "email-security-checker",
    relatedTool: {
      label: "tools.emailSecurityChecker.relatedLabel",
      path: "/tools/dns-checker",
    },
    featurePath: "/features/email-security",
  },
}

function ToolContent({ config }: { config: ToolConfig }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { t, tList } = useI18n()
  const strings = STRINGS[config.id]
  const initialDomain = searchParams.get("domain")?.trim() ?? ""
  const [domain, setDomain] = useState(initialDomain)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState("")
  const [activeFaq, setActiveFaq] = useState<number | null>(null)
  const autoStarted = useRef(false)

  const h1 = t(strings.h1)
  const checks = tList(strings.checks)
  const faqQuestions = tList(strings.faqQuestions)
  const faqAnswers = tList(strings.faqAnswers)
  const howItWorks = tList(strings.howItWorks)
  const faqItems = faqQuestions.map((q, index) => ({
    q,
    a: faqAnswers[index] ?? "",
  }))

  // Runs the real public scan (`POST /public/scan/`) and hands over to the
  // report page, which polls the scan until it settles. No sample results.
  const runCheck = async (value: string = domain) => {
    const target = value.trim()
    if (!target || scanning) return
    setScanning(true)
    setError("")
    try {
      const created = await api.post<{ scan_id: string }>(
        endpoints.publicScan.start,
        { domain: target },
      )
      navigate(`/scan/${created.scan_id}`)
    } catch (err) {
      setError(apiErrorMessage(err, t("tools.shared.errorStart")))
      setScanning(false)
    }
  }

  // The landing-page hero forwards its input here (`?domain=…`): start the
  // real check immediately rather than asking for the same domain twice.
  // The ref guard keeps React StrictMode's double effect from scanning twice.
  useEffect(() => {
    if (!initialDomain || autoStarted.current) return
    autoStarted.current = true
    void runCheck(initialDomain)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialDomain])

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t(strings.metaTitle)}
        description={t(strings.metaDescription)}
        path={`/tools/${config.slug}`}
        structuredData={[
          {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            name: h1,
            url: `${import.meta.env.VITE_BASE_URL as string | undefined ?? ""}/tools/${config.slug}`,
            applicationCategory: "BusinessApplication",
            offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
          },
          faqSchema(faqItems),
          breadcrumbSchema([
            { name: t("tools.shared.home"), url: "/" },
            { name: t("tools.shared.freeTools"), url: "/tools/website-checker" },
            { name: h1, url: `/tools/${config.slug}` },
          ]),
        ]}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/tools/website-checker" className="hover:text-slate-900">
              {t("tools.shared.freeChecker")}
            </Link>
            <Link to="/#features" className="hover:text-slate-900">
              {t("nav.features")}
            </Link>
            <Link to="/pricing" className="hover:text-slate-900">
              {t("nav.pricing")}
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link
              to="/login"
              className="hidden sm:inline text-sm text-slate-600 hover:text-slate-900"
            >
              {t("common.login")}
            </Link>
            <Link to="/register">
              <button className="px-3 sm:px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 whitespace-nowrap">
                {t("common.signup")}
              </button>
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero + tool */}
        <section className="pt-14 pb-20 px-4 bg-gradient-to-b from-indigo-50/40 to-white">
          <div className="max-w-2xl mx-auto">
            <Breadcrumb
              items={[
                { label: t("tools.shared.home"), path: "/" },
                {
                  label: t("tools.shared.freeTools"),
                  path: "/tools/website-checker",
                },
                { label: h1, path: `/tools/${config.slug}` },
              ]}
            />
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-slate-900 mb-4 hyphens-auto break-words">
              {h1}
            </h1>
            <p className="text-lg text-slate-500 mb-8">{t(strings.intro)}</p>

            {/* Tool input */}
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
              <label
                htmlFor="domain-input"
                className="block text-sm font-medium text-slate-700 mb-2"
              >
                {t(strings.inputLabel)}
              </label>
              <div className="flex gap-3 flex-col sm:flex-row">
                <div className="flex-1 flex items-center border border-slate-300 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent bg-white">
                  <div className="pl-3 text-slate-400">
                    <Globe size={16} />
                  </div>
                  <input
                    id="domain-input"
                    type="text"
                    placeholder="example.com"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void runCheck()
                    }}
                    className="flex-1 px-3 py-3 text-sm bg-transparent focus:outline-none placeholder:text-slate-400"
                    aria-label={t(strings.inputLabel)}
                  />
                </div>
                <button
                  onClick={() => void runCheck()}
                  disabled={scanning || !domain.trim()}
                  className="px-5 py-3 bg-indigo-600 text-white font-semibold text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-60 transition-colors flex items-center gap-2 whitespace-nowrap"
                >
                  {scanning && <Loader size={14} className="animate-spin" />}
                  {t(strings.buttonLabel)}
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {t("tools.shared.noAccountNote")}
              </p>

              {/* Scanning state */}
              {scanning && (
                <div className="mt-5 pt-5 border-t border-slate-100">
                  <div className="flex items-center gap-3 text-slate-600">
                    <Loader
                      size={16}
                      className="animate-spin text-indigo-600"
                    />
                    <span className="text-sm font-medium">
                      {t("tools.shared.checking", { domain })}
                    </span>
                  </div>
                  <div className="mt-3 space-y-1.5">
                    {checks.map((c, i) => (
                      <div
                        key={`scanning-${i}`}
                        className="flex items-center gap-2 text-xs text-slate-400"
                      >
                        <div
                          className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"
                          style={{ animationDelay: `${i * 0.15}s` }}
                        />
                        {c}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <div
                  className="mt-5 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700"
                  role="alert"
                >
                  <span className="font-semibold">
                    {t("tools.shared.checkFailed")}
                  </span>{" "}
                  {error}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* What we check */}
        <section className="py-16 px-4 bg-slate-50 border-y border-slate-100">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("tools.shared.whatThisToolChecks")}
            </h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {checks.map((c, i) => (
                <div
                  key={`check-${i}`}
                  className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3"
                >
                  <CheckCircle
                    size={15}
                    className="text-emerald-500 flex-shrink-0"
                  />
                  <span className="text-sm text-slate-700">{c}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="py-16 px-4">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("tools.shared.howItWorks")}
            </h2>
            <ol className="space-y-4">
              {howItWorks.map((step, i) => (
                <li key={i} className="flex items-start gap-4">
                  <span className="w-7 h-7 bg-indigo-600 text-white text-sm font-bold rounded-full flex items-center justify-center flex-shrink-0">
                    {i + 1}
                  </span>
                  <p className="text-slate-700 pt-0.5">{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 px-4 bg-slate-50">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("tools.shared.faqTitle")}
            </h2>
            <div className="space-y-3">
              {faqItems.map((faq, i) => (
                <div
                  key={i}
                  className="bg-white border border-slate-200 rounded-xl overflow-hidden"
                >
                  <button
                    className="w-full flex items-center justify-between px-5 py-4 text-left"
                    onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                    aria-expanded={activeFaq === i}
                  >
                    <span className="font-medium text-slate-900 text-sm">
                      {faq.q}
                    </span>
                    <ChevronDown
                      size={15}
                      className={`text-slate-400 flex-shrink-0 transition-transform ${
                        activeFaq === i ? "rotate-180" : ""
                      }`}
                    />
                  </button>
                  {/* Rendered unconditionally for the SSG output; `hidden`
                      keeps the accordion collapsed until the user opens it. */}
                  <div
                    hidden={activeFaq !== i}
                    className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3"
                  >
                    {faq.a}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Related tools + feature link */}
        <section className="py-12 px-4">
          <div className="max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 p-6 bg-indigo-50 border border-indigo-100 rounded-2xl">
            <div>
              <p className="font-semibold text-indigo-900">
                {t("tools.shared.automaticTitle")}
              </p>
              <p className="text-sm text-indigo-700 mt-1">
                {t("tools.shared.automaticBody")}
              </p>
            </div>
            <div className="flex gap-3 flex-shrink-0">
              {config.relatedTool && (
                <Link to={config.relatedTool.path}>
                  <button className="px-4 py-2.5 border border-indigo-300 text-indigo-700 text-sm font-semibold rounded-xl hover:bg-indigo-100 transition-colors">
                    {t(config.relatedTool.label)}
                  </button>
                </Link>
              )}
              <Link to="/register">
                <button className="px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-1.5">
                  {t("common.startFree")} <ArrowRight size={14} />
                </button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">
          © 2026 Presence —{" "}
          <Link to="/" className="hover:text-slate-600">
            {t("tools.shared.home")}
          </Link>{" "}
          ·{" "}
          <Link to="/pricing" className="hover:text-slate-600">
            {t("nav.pricing")}
          </Link>{" "}
          ·{" "}
          <Link to="/faq" className="hover:text-slate-600">
            {t("nav.faq")}
          </Link>
        </p>
      </footer>
    </div>
  )
}

export default function ToolPage({ tool }: { tool: string }) {
  const { t } = useI18n()
  const config = toolConfigs[tool]
  if (!config)
    return (
      <div className="p-8 text-center text-slate-500">
        {t("tools.shared.notFound")}
      </div>
    )
  return <ToolContent config={config} />
}
