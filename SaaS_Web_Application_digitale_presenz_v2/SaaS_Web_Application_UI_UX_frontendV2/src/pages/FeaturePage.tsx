import React, { useState } from "react"
import Link from "../components/LocaleLink"
import { CheckCircle, ChevronDown, ArrowRight } from "lucide-react"
import SEO, { faqSchema, breadcrumbSchema, softwareAppSchema } from "../components/SEO"
import Breadcrumb from "../components/Breadcrumb"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n, type ListKey, type MessageKey } from "../i18n"

type FeatureId =
  | "websiteMonitoring"
  | "sslMonitoring"
  | "dnsMonitoring"
  | "emailSecurity"
  | "uptimeMonitoring"
  | "websitePerformance"
  | "securityHeaders"
  | "reviewMonitoring"

interface FeatureStrings {
  title: MessageKey
  metaTitle: MessageKey
  metaDescription: MessageKey
  h1: MessageKey
  intro: MessageKey
  problem: MessageKey
  solution: MessageKey
  ctaLabel: MessageKey
  benefits: ListKey
  howItWorksSteps: ListKey
  howItWorksDescriptions: ListKey
  faqQuestions: ListKey
  faqAnswers: ListKey
  checkpoints: ListKey
}

interface FeatureConfig {
  slug: string
  /** Unknown slugs fall through to the "not found" state. */
  strings: FeatureStrings
  related: { label: MessageKey; path: string }[]
}

/**
 * Structural configuration only: routes and translations keys stay in code.
 * Every visible string lives in `src/i18n/{de,en}.json`, so the German and
 * English pages are the same component with the same layout.
 */
const configs: Record<string, FeatureConfig> = {
  "website-monitoring": {
    slug: "website-monitoring",
    strings: {
      title: "features.websiteMonitoring.title",
      metaTitle: "features.websiteMonitoring.metaTitle",
      metaDescription: "features.websiteMonitoring.metaDescription",
      h1: "features.websiteMonitoring.h1",
      intro: "features.websiteMonitoring.intro",
      problem: "features.websiteMonitoring.problem",
      solution: "features.websiteMonitoring.solution",
      ctaLabel: "features.websiteMonitoring.ctaLabel",
      benefits: "features.websiteMonitoring.benefits",
      howItWorksSteps: "features.websiteMonitoring.howItWorksSteps",
      howItWorksDescriptions:
        "features.websiteMonitoring.howItWorksDescriptions",
      faqQuestions: "features.websiteMonitoring.faqQuestions",
      faqAnswers: "features.websiteMonitoring.faqAnswers",
      checkpoints: "features.websiteMonitoring.checkpoints",
    },
    related: [
      {
        label: "features.websiteMonitoring.related.uptimeMonitoring",
        path: "/features/uptime-monitoring",
      },
      {
        label: "features.websiteMonitoring.related.websitePerformance",
        path: "/features/website-performance",
      },
      {
        label: "features.websiteMonitoring.related.sslMonitoring",
        path: "/features/ssl-monitoring",
      },
    ],
  },

  "ssl-monitoring": {
    slug: "ssl-monitoring",
    strings: {
      title: "features.sslMonitoring.title",
      metaTitle: "features.sslMonitoring.metaTitle",
      metaDescription: "features.sslMonitoring.metaDescription",
      h1: "features.sslMonitoring.h1",
      intro: "features.sslMonitoring.intro",
      problem: "features.sslMonitoring.problem",
      solution: "features.sslMonitoring.solution",
      ctaLabel: "features.sslMonitoring.ctaLabel",
      benefits: "features.sslMonitoring.benefits",
      howItWorksSteps: "features.sslMonitoring.howItWorksSteps",
      howItWorksDescriptions: "features.sslMonitoring.howItWorksDescriptions",
      faqQuestions: "features.sslMonitoring.faqQuestions",
      faqAnswers: "features.sslMonitoring.faqAnswers",
      checkpoints: "features.sslMonitoring.checkpoints",
    },
    related: [
      {
        label: "features.sslMonitoring.related.websiteMonitoring",
        path: "/features/website-monitoring",
      },
      {
        label: "features.sslMonitoring.related.dnsMonitoring",
        path: "/features/dns-monitoring",
      },
      { label: "features.sslMonitoring.related.sslChecker", path: "/tools/ssl-checker" },
    ],
  },

  "dns-monitoring": {
    slug: "dns-monitoring",
    strings: {
      title: "features.dnsMonitoring.title",
      metaTitle: "features.dnsMonitoring.metaTitle",
      metaDescription: "features.dnsMonitoring.metaDescription",
      h1: "features.dnsMonitoring.h1",
      intro: "features.dnsMonitoring.intro",
      problem: "features.dnsMonitoring.problem",
      solution: "features.dnsMonitoring.solution",
      ctaLabel: "features.dnsMonitoring.ctaLabel",
      benefits: "features.dnsMonitoring.benefits",
      howItWorksSteps: "features.dnsMonitoring.howItWorksSteps",
      howItWorksDescriptions: "features.dnsMonitoring.howItWorksDescriptions",
      faqQuestions: "features.dnsMonitoring.faqQuestions",
      faqAnswers: "features.dnsMonitoring.faqAnswers",
      checkpoints: "features.dnsMonitoring.checkpoints",
    },
    related: [
      {
        label: "features.dnsMonitoring.related.websiteMonitoring",
        path: "/features/website-monitoring",
      },
      {
        label: "features.dnsMonitoring.related.emailSecurity",
        path: "/features/email-security",
      },
      { label: "features.dnsMonitoring.related.dnsChecker", path: "/tools/dns-checker" },
    ],
  },

  "email-security": {
    slug: "email-security",
    strings: {
      title: "features.emailSecurity.title",
      metaTitle: "features.emailSecurity.metaTitle",
      metaDescription: "features.emailSecurity.metaDescription",
      h1: "features.emailSecurity.h1",
      intro: "features.emailSecurity.intro",
      problem: "features.emailSecurity.problem",
      solution: "features.emailSecurity.solution",
      ctaLabel: "features.emailSecurity.ctaLabel",
      benefits: "features.emailSecurity.benefits",
      howItWorksSteps: "features.emailSecurity.howItWorksSteps",
      howItWorksDescriptions: "features.emailSecurity.howItWorksDescriptions",
      faqQuestions: "features.emailSecurity.faqQuestions",
      faqAnswers: "features.emailSecurity.faqAnswers",
      checkpoints: "features.emailSecurity.checkpoints",
    },
    related: [
      {
        label: "features.emailSecurity.related.dnsMonitoring",
        path: "/features/dns-monitoring",
      },
      {
        label: "features.emailSecurity.related.securityHeaders",
        path: "/features/security-headers",
      },
      {
        label: "features.emailSecurity.related.emailSecurityChecker",
        path: "/tools/email-security-checker",
      },
    ],
  },

  "uptime-monitoring": {
    slug: "uptime-monitoring",
    strings: {
      title: "features.uptimeMonitoring.title",
      metaTitle: "features.uptimeMonitoring.metaTitle",
      metaDescription: "features.uptimeMonitoring.metaDescription",
      h1: "features.uptimeMonitoring.h1",
      intro: "features.uptimeMonitoring.intro",
      problem: "features.uptimeMonitoring.problem",
      solution: "features.uptimeMonitoring.solution",
      ctaLabel: "features.uptimeMonitoring.ctaLabel",
      benefits: "features.uptimeMonitoring.benefits",
      howItWorksSteps: "features.uptimeMonitoring.howItWorksSteps",
      howItWorksDescriptions: "features.uptimeMonitoring.howItWorksDescriptions",
      faqQuestions: "features.uptimeMonitoring.faqQuestions",
      faqAnswers: "features.uptimeMonitoring.faqAnswers",
      checkpoints: "features.uptimeMonitoring.checkpoints",
    },
    related: [
      {
        label: "features.uptimeMonitoring.related.websiteMonitoring",
        path: "/features/website-monitoring",
      },
      {
        label: "features.uptimeMonitoring.related.websitePerformance",
        path: "/features/website-performance",
      },
      {
        label: "features.uptimeMonitoring.related.alerts",
        path: "/features/website-monitoring",
      },
    ],
  },

  "website-performance": {
    slug: "website-performance",
    strings: {
      title: "features.websitePerformance.title",
      metaTitle: "features.websitePerformance.metaTitle",
      metaDescription: "features.websitePerformance.metaDescription",
      h1: "features.websitePerformance.h1",
      intro: "features.websitePerformance.intro",
      problem: "features.websitePerformance.problem",
      solution: "features.websitePerformance.solution",
      ctaLabel: "features.websitePerformance.ctaLabel",
      benefits: "features.websitePerformance.benefits",
      howItWorksSteps: "features.websitePerformance.howItWorksSteps",
      howItWorksDescriptions:
        "features.websitePerformance.howItWorksDescriptions",
      faqQuestions: "features.websitePerformance.faqQuestions",
      faqAnswers: "features.websitePerformance.faqAnswers",
      checkpoints: "features.websitePerformance.checkpoints",
    },
    related: [
      {
        label: "features.websitePerformance.related.uptimeMonitoring",
        path: "/features/uptime-monitoring",
      },
      {
        label: "features.websitePerformance.related.websiteMonitoring",
        path: "/features/website-monitoring",
      },
      {
        label: "features.websitePerformance.related.websiteChecker",
        path: "/tools/website-checker",
      },
    ],
  },

  "security-headers": {
    slug: "security-headers",
    strings: {
      title: "features.securityHeaders.title",
      metaTitle: "features.securityHeaders.metaTitle",
      metaDescription: "features.securityHeaders.metaDescription",
      h1: "features.securityHeaders.h1",
      intro: "features.securityHeaders.intro",
      problem: "features.securityHeaders.problem",
      solution: "features.securityHeaders.solution",
      ctaLabel: "features.securityHeaders.ctaLabel",
      benefits: "features.securityHeaders.benefits",
      howItWorksSteps: "features.securityHeaders.howItWorksSteps",
      howItWorksDescriptions: "features.securityHeaders.howItWorksDescriptions",
      faqQuestions: "features.securityHeaders.faqQuestions",
      faqAnswers: "features.securityHeaders.faqAnswers",
      checkpoints: "features.securityHeaders.checkpoints",
    },
    related: [
      {
        label: "features.securityHeaders.related.sslMonitoring",
        path: "/features/ssl-monitoring",
      },
      {
        label: "features.securityHeaders.related.emailSecurity",
        path: "/features/email-security",
      },
      {
        label: "features.securityHeaders.related.websiteChecker",
        path: "/tools/website-checker",
      },
    ],
  },

  "review-monitoring": {
    slug: "review-monitoring",
    strings: {
      title: "features.reviewMonitoring.title",
      metaTitle: "features.reviewMonitoring.metaTitle",
      metaDescription: "features.reviewMonitoring.metaDescription",
      h1: "features.reviewMonitoring.h1",
      intro: "features.reviewMonitoring.intro",
      problem: "features.reviewMonitoring.problem",
      solution: "features.reviewMonitoring.solution",
      ctaLabel: "features.reviewMonitoring.ctaLabel",
      benefits: "features.reviewMonitoring.benefits",
      howItWorksSteps: "features.reviewMonitoring.howItWorksSteps",
      howItWorksDescriptions: "features.reviewMonitoring.howItWorksDescriptions",
      faqQuestions: "features.reviewMonitoring.faqQuestions",
      faqAnswers: "features.reviewMonitoring.faqAnswers",
      checkpoints: "features.reviewMonitoring.checkpoints",
    },
    related: [
      { label: "features.reviewMonitoring.related.score", path: "/#score" },
      {
        label: "features.reviewMonitoring.related.reports",
        path: "/features/website-monitoring",
      },
      {
        label: "features.reviewMonitoring.related.alerts",
        path: "/features/website-monitoring",
      },
    ],
  },
}

function FeatureContent({ config }: { config: FeatureConfig }) {
  const { t, tList } = useI18n()
  const [activeFaq, setActiveFaq] = useState<number | null>(null)

  const s = config.strings
  const title = t(s.title)
  const h1 = t(s.h1)
  const benefits = tList(s.benefits)
  const steps = tList(s.howItWorksSteps)
  const descriptions = tList(s.howItWorksDescriptions)
  const checkpoints = tList(s.checkpoints)
  const questions = tList(s.faqQuestions)
  const answers = tList(s.faqAnswers)
  const faqItems = questions.map((q, index) => ({ q, a: answers[index] ?? "" }))

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t(s.metaTitle)}
        description={t(s.metaDescription)}
        path={`/features/${config.slug}`}
        structuredData={[
          softwareAppSchema(),
          faqSchema(faqItems),
          breadcrumbSchema([
            { name: t("features.shared.home"), url: "/" },
            { name: t("features.shared.features"), url: "/#features" },
            { name: title, url: `/features/${config.slug}` },
          ]),
        ]}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link
              to="/#features"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              {t("features.shared.features")}
            </Link>
            <Link
              to="/pricing"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              {t("nav.pricing")}
            </Link>
            <Link
              to="/tools/website-checker"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              {t("features.shared.freeChecker")}
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link
              to="/login"
              className="hidden sm:inline text-sm text-slate-600 hover:text-slate-900"
            >
              {t("features.shared.logIn")}
            </Link>
            {/* The per-feature CTA label is long in German; the hero keeps the
                same actions one scroll away, so the header drops it on phones. */}
            <Link to="/register" className="hidden sm:block">
              <button className="px-3 sm:px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors whitespace-nowrap">
                {t(s.ctaLabel)}
              </button>
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="pt-16 pb-20 px-4 bg-gradient-to-b from-indigo-50/50 to-white">
          <div className="max-w-4xl mx-auto">
            <Breadcrumb
              items={[
                { label: t("features.shared.home"), path: "/" },
                { label: t("features.shared.features"), path: "/#features" },
                { label: title, path: `/features/${config.slug}` },
              ]}
            />
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-slate-900 mb-5 leading-tight hyphens-auto break-words">
              {h1}
            </h1>
            <p className="text-xl text-slate-500 mb-8 leading-relaxed max-w-2xl">
              {t(s.intro)}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/tools/website-checker">
                <button className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2">
                  {t("features.shared.checkFree")} <ArrowRight size={16} />
                </button>
              </Link>
              <Link to="/register">
                <button className="px-6 py-3 border border-slate-300 text-slate-700 font-semibold rounded-xl hover:bg-slate-50 transition-colors">
                  {t("features.shared.startMonitoring")}
                </button>
              </Link>
            </div>
          </div>
        </section>

        {/* What we check */}
        <section className="py-16 px-4 border-y border-slate-100 bg-slate-50">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("features.shared.whatWeCheck")}
            </h2>
            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
              {checkpoints.map((cp) => (
                <div
                  key={cp}
                  className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3"
                >
                  <CheckCircle
                    size={16}
                    className="text-emerald-500 flex-shrink-0"
                  />
                  <span className="text-sm font-medium text-slate-700">
                    {cp}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Problem / Solution */}
        <section className="py-20 px-4">
          <div className="max-w-4xl mx-auto grid md:grid-cols-2 gap-10">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-red-500 mb-3">
                {t("features.shared.problemEyebrow")}
              </p>
              <h2 className="text-2xl font-bold text-slate-900 mb-4">
                {t("features.shared.problemTitle")}
              </h2>
              <p className="text-slate-600 leading-relaxed">{t(s.problem)}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-emerald-600 mb-3">
                {t("features.shared.solutionEyebrow")}
              </p>
              <h2 className="text-2xl font-bold text-slate-900 mb-4">
                {t("features.shared.solutionTitle")}
              </h2>
              <p className="text-slate-600 leading-relaxed">{t(s.solution)}</p>
            </div>
          </div>
        </section>

        {/* Benefits */}
        <section className="py-16 px-4 bg-indigo-600">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-white mb-8">
              {t("features.shared.benefitsTitle")}
            </h2>
            <ul className="space-y-3">
              {benefits.map((b) => (
                <li key={b} className="flex items-center gap-3 text-indigo-100">
                  <CheckCircle
                    size={16}
                    className="text-emerald-400 flex-shrink-0"
                  />
                  {b}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section className="py-20 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 mb-10 text-center">
              {t("features.shared.howItWorks")}
            </h2>
            <div className="grid md:grid-cols-3 gap-8">
              {steps.map((step, index) => (
                <div key={step} className="text-center">
                  <div className="w-12 h-12 bg-indigo-600 text-white rounded-2xl flex items-center justify-center font-bold text-lg mx-auto mb-4">
                    {step.split(".")[0]}
                  </div>
                  <p className="font-semibold text-slate-900 mb-2">
                    {step.replace(/^\d\.\s/, "")}
                  </p>
                  <p className="text-sm text-slate-500">
                    {descriptions[index] ?? ""}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-20 px-4 bg-slate-50">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 mb-8 text-center">
              {t("features.shared.faqTitle")}
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
                    <span className="font-medium text-slate-900">{faq.q}</span>
                    <ChevronDown
                      size={16}
                      className={`text-slate-400 flex-shrink-0 transition-transform ${
                        activeFaq === i ? "rotate-180" : ""
                      }`}
                    />
                  </button>
                  {/* Rendered unconditionally so the answer is part of the
                      pre-rendered HTML; `hidden` keeps it collapsed. */}
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

        {/* Related features */}
        <section className="py-16 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("features.shared.relatedTitle")}
            </h2>
            <div className="flex flex-wrap gap-3">
              {config.related.map(({ label, path }) => (
                <Link
                  key={`${path}-${label}`}
                  to={path}
                  className="px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-700 hover:bg-indigo-50 transition-all flex items-center gap-2"
                >
                  {t(label)} <ArrowRight size={14} />
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-20 px-4 bg-slate-900 text-center">
          <div className="max-w-xl mx-auto">
            <h2 className="text-3xl font-bold text-white mb-4">
              {t("features.shared.ctaTitle")}
            </h2>
            <p className="text-slate-400 mb-8">
              {t("features.shared.ctaBody")}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/tools/website-checker">
                <button className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors">
                  {t("features.shared.checkFree")}
                </button>
              </Link>
              <Link to="/pricing">
                <button className="px-6 py-3 border border-slate-700 text-slate-300 font-semibold rounded-xl hover:bg-slate-800 transition-colors">
                  {t("features.shared.viewPricing")}
                </button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">
          © 2026 Presence.{" "}
          <Link to="/pricing" className="hover:text-slate-600">
            {t("nav.pricing")}
          </Link>{" "}
          ·{" "}
          <Link to="/faq" className="hover:text-slate-600">
            {t("nav.faq")}
          </Link>{" "}
          ·{" "}
          <Link to="/about" className="hover:text-slate-600">
            {t("nav.about")}
          </Link>
        </p>
      </footer>
    </div>
  )
}

export default function FeaturePage({ feature }: { feature: string }) {
  const { t } = useI18n()
  const config = configs[feature]

  if (!config) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-lg font-semibold text-slate-900">
            {t("features.shared.notFound")}
          </p>
          <Link to="/" className="text-indigo-600 hover:underline text-sm">
            {t("features.shared.backHome")}
          </Link>
        </div>
      </div>
    )
  }
  return <FeatureContent config={config} />
}
