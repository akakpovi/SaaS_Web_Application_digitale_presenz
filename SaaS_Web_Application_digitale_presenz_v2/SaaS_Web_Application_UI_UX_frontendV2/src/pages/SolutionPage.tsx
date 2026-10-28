import React from "react"
import Link from "../components/LocaleLink"
import {
  CheckCircle,
  ArrowRight,
  Shield,
  Globe,
  Bell,
  FileText,
  Activity,
} from "lucide-react"
import SEO, { softwareAppSchema, breadcrumbSchema } from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"

type SolutionId =
  | "smallBusiness"
  | "freelancers"
  | "agencies"
  | "restaurants"
  | "ecommerce"
  | "localBusiness"

type IconComponent = React.FC<{ size?: number; className?: string }>

interface SolutionConfig {
  id: SolutionId
  slug: string
  /** Icons are structure, not copy: they stay in code, in rendering order. */
  icons: IconComponent[]
}

/**
 * Catalogue key for one solution. The template literal is a union of the six
 * concrete keys, so a typo or a missing German entry is still a `tsc` error.
 */
const solutionKey = <S extends string>(id: SolutionId, suffix: S) =>
  `solutions.${id}.${suffix}` as const

const SOLUTION_CONFIGS: Record<string, SolutionConfig> = {
  "small-business": {
    id: "smallBusiness",
    slug: "small-business",
    icons: [Bell, Globe, FileText, Shield],
  },
  freelancers: {
    id: "freelancers",
    slug: "freelancers",
    icons: [Bell, Globe, FileText, Shield],
  },
  agencies: {
    id: "agencies",
    slug: "agencies",
    icons: [Bell, FileText, Globe, Activity],
  },
  restaurants: {
    id: "restaurants",
    slug: "restaurants",
    icons: [Bell, Globe, Shield, FileText],
  },
  ecommerce: {
    id: "ecommerce",
    slug: "ecommerce",
    icons: [Bell, Shield, Activity, Globe],
  },
  "local-business": {
    id: "localBusiness",
    slug: "local-business",
    icons: [Globe, Bell, FileText, Shield],
  },
}

function PublicNav() {
  const { t } = useI18n()
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
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
            className="hidden sm:inline text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-1.5"
          >
            {t("common.login")}
          </Link>
          <Link
            to="/register"
            className="px-3 sm:px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors whitespace-nowrap"
          >
            {t("common.startFree")}
          </Link>
        </div>
      </div>
    </header>
  )
}

function SolutionContent({ config }: { config: SolutionConfig }) {
  const [url, setUrl] = React.useState("")
  const { t, tList } = useI18n()
  const { id, slug } = config

  const h1 = t(solutionKey(id, "h1"))
  const checks = tList(solutionKey(id, "checks"))
  const benefitTitles = tList(solutionKey(id, "benefitTitles"))
  const benefitBodies = tList(solutionKey(id, "benefitBodies"))
  const useCases = tList(solutionKey(id, "useCases"))

  return (
    <>
      <SEO
        title={t(solutionKey(id, "metaTitle"))}
        description={t(solutionKey(id, "metaDescription"))}
        path={`/solutions/${slug}`}
        structuredData={[
          softwareAppSchema(),
          // There is no `/solutions` index route, so the trail only carries the
          // home page and the current solution instead of a link to a 404.
          breadcrumbSchema([
            { name: t("common.home"), url: "/" },
            { name: h1, url: `/solutions/${slug}` },
          ]),
        ]}
      />
      <PublicNav />

      <main>
        {/* Hero */}
        <section className="bg-gradient-to-br from-slate-900 to-slate-800 text-white py-20 px-4">
          <div className="max-w-3xl mx-auto text-center">
            <p className="text-indigo-400 font-semibold text-sm uppercase tracking-wider mb-3">
              {t("solutions.shared.eyebrow", {
                segment: t(solutionKey(id, "segment")),
              })}
            </p>
            <h1 className="text-2xl sm:text-4xl font-black mb-4 leading-tight hyphens-auto break-words">
              {h1}
            </h1>
            <p className="text-slate-300 text-lg mb-8">
              {t(solutionKey(id, "tagline"))}
            </p>

            {/* Inline scanner */}
            <div className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="url"
                placeholder="yourdomain.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="flex-1 px-4 py-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
                aria-label={t("solutions.shared.urlAria")}
              />
              <Link
                to={`/onboarding${url ? `?domain=${encodeURIComponent(url)}` : ""}`}
                className="px-5 py-3 bg-indigo-500 hover:bg-indigo-400 text-white font-semibold rounded-xl transition-colors text-sm whitespace-nowrap"
              >
                {t("solutions.shared.checkCta")}
              </Link>
            </div>
            <p className="text-slate-400 text-xs mt-3">
              {t("solutions.shared.noCard")}
            </p>
          </div>
        </section>

        {/* Problem */}
        <section className="py-16 px-4 bg-white">
          <div className="max-w-3xl mx-auto">
            <div className="p-6 bg-amber-50 border border-amber-200 rounded-2xl mb-8">
              <p className="text-amber-800 font-semibold mb-1">
                {t("solutions.shared.problemTitle")}
              </p>
              <p className="text-amber-700">{t(solutionKey(id, "problem"))}</p>
            </div>
            <p className="text-lg text-slate-700 leading-relaxed">
              {t(solutionKey(id, "intro"))}
            </p>
          </div>
        </section>

        {/* What Presence checks */}
        <section className="py-16 px-4 bg-slate-50">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("solutions.shared.monitorsTitle")}
            </h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {checks.map((c, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3"
                >
                  <CheckCircle
                    size={15}
                    className="text-emerald-500 flex-shrink-0"
                    aria-hidden="true"
                  />
                  <span className="text-sm text-slate-700">{c}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Benefits */}
        <section className="py-16 px-4 bg-white">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-8">
              {t("solutions.shared.helpsTitle")}
            </h2>
            <div className="grid sm:grid-cols-2 gap-6">
              {config.icons.map((Icon, index) => (
                <div key={benefitTitles[index]} className="flex gap-4">
                  <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon size={18} className="text-indigo-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900 mb-1">
                      {benefitTitles[index]}
                    </p>
                    <p className="text-sm text-slate-600 leading-relaxed">
                      {benefitBodies[index]}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Use cases */}
        <section className="py-16 px-4 bg-slate-50">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("solutions.shared.usersTitle")}
            </h2>
            <p className="text-slate-500 mb-4 text-sm">
              {t(solutionKey(id, "audienceLabel"))}:
            </p>
            <ul className="space-y-2">
              {useCases.map((uc, i) => (
                <li
                  key={i}
                  className="flex items-center gap-2 text-slate-700 text-sm"
                >
                  <CheckCircle
                    size={14}
                    className="text-indigo-500 flex-shrink-0"
                    aria-hidden="true"
                  />
                  {uc}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* CTA */}
        <section className="py-20 px-4 bg-indigo-600">
          <div className="max-w-2xl mx-auto text-center text-white">
            <h2 className="text-2xl font-bold mb-3">
              {t("solutions.shared.ctaTitle")}
            </h2>
            <p className="text-indigo-200 mb-8">
              {t("solutions.shared.ctaBody")}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                to="/register"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-white text-indigo-700 font-semibold rounded-xl hover:bg-indigo-50 transition-colors"
              >
                {t("solutions.shared.createAccount")} <ArrowRight size={15} />
              </Link>
              <Link
                to="/pricing"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 border border-indigo-400 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
              >
                {t("solutions.shared.viewPricing")}
              </Link>
            </div>
          </div>
        </section>

        {/* Related solutions */}
        <section className="py-12 px-4 bg-white border-t border-slate-100">
          <div className="max-w-3xl mx-auto">
            <p className="text-sm font-semibold text-slate-500 mb-4">
              {t("solutions.shared.allBusinesses")}
            </p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(SOLUTION_CONFIGS).map(([key, cfg]) =>
                key !== slug ? (
                  <Link
                    key={key}
                    to={`/solutions/${key}`}
                    className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
                  >
                    {t(solutionKey(cfg.id, "segment"))}
                  </Link>
                ) : null,
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">
          © 2026 Presence ·{" "}
          <Link to="/" className="hover:text-slate-600">
            {t("common.home")}
          </Link>{" "}
          ·{" "}
          <Link to="/pricing" className="hover:text-slate-600">
            {t("nav.pricing")}
          </Link>{" "}
          ·{" "}
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

export default function SolutionPage({ solution }: { solution: string }) {
  const config = SOLUTION_CONFIGS[solution]
  if (!config) return null
  return <SolutionContent config={config} />
}
