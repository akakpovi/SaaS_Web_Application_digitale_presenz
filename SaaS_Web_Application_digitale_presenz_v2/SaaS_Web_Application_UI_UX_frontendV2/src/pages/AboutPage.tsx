import React from "react"
import Link from "../components/LocaleLink"
import { Shield, Globe, Bell, ArrowRight } from "lucide-react"
import SEO, { organizationSchema } from "../components/SEO"
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

/** Icons stay in code; every string comes from the catalogue. */
const VALUE_ICONS = [Shield, Globe, Bell]

/** Scoring weights are product facts, so only the unit is translated. */
const DIMENSION_POINTS = [20, 20, 15, 15, 15, 15]

export default function AboutPage() {
  const { t, tList } = useI18n()
  const valueTitles = tList("about.valueTitles")
  const valueBodies = tList("about.valueBodies")
  const dimensionLabels = tList("about.dimensionLabels")
  const dimensionDescriptions = tList("about.dimensionDescriptions")

  return (
    <>
      <SEO
        title={t("about.metaTitle")}
        description={t("about.metaDescription")}
        path="/about"
        structuredData={[organizationSchema()]}
      />
      <PublicNav />
      <main>
        <section className="py-20 px-4 bg-slate-900 text-white">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-2xl sm:text-4xl font-black mb-4 hyphens-auto break-words">
              {t("about.h1")}
            </h1>
            <p className="text-slate-300 text-lg leading-relaxed">
              {t("about.lede")}
            </p>
          </div>
        </section>

        <section className="py-16 px-4 bg-white">
          <div className="max-w-3xl mx-auto prose prose-slate">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              {t("about.whyTitle")}
            </h2>
            <p className="text-slate-600 leading-relaxed mb-4">
              {t("about.why1")}
            </p>
            <p className="text-slate-600 leading-relaxed mb-4">
              {t("about.why2")}
            </p>
            <p className="text-slate-600 leading-relaxed mb-8">
              {t("about.why3")}
            </p>

            <div className="grid sm:grid-cols-3 gap-6 mb-12">
              {VALUE_ICONS.map((Icon, index) => (
                <div
                  key={valueTitles[index]}
                  className="text-center p-5 bg-slate-50 rounded-2xl border border-slate-100"
                >
                  <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center mx-auto mb-3">
                    <Icon size={18} className="text-indigo-600" />
                  </div>
                  <p className="font-semibold text-slate-900 mb-1">
                    {valueTitles[index]}
                  </p>
                  <p className="text-sm text-slate-500">{valueBodies[index]}</p>
                </div>
              ))}
            </div>

            <h2 className="text-2xl font-bold text-slate-900 mb-4">
              {t("about.monitorsTitle")}
            </h2>
            <p className="text-slate-600 leading-relaxed mb-4">
              {t("about.monitorsIntroBefore")}{" "}
              <strong>{t("about.healthScoreTerm")}</strong>{" "}
              {t("about.monitorsIntroAfter")}
            </p>
            <ul className="space-y-2 mb-8">
              {DIMENSION_POINTS.map((points, index) => (
                <li
                  key={dimensionLabels[index]}
                  className="flex items-start gap-3 text-sm text-slate-600"
                >
                  <span className="font-semibold text-slate-800 w-36 flex-shrink-0">
                    {dimensionLabels[index]}
                  </span>
                  <span className="text-indigo-600 font-mono w-12 flex-shrink-0">
                    {points} {t("about.points")}
                  </span>
                  <span>{dimensionDescriptions[index]}</span>
                </li>
              ))}
            </ul>

            <p className="text-slate-600 leading-relaxed">
              {t("about.uptimeNote")}
            </p>
          </div>
        </section>

        <section className="py-16 px-4 bg-indigo-600 text-white text-center">
          <h2 className="text-2xl font-bold mb-3">{t("about.ctaTitle")}</h2>
          <p className="text-indigo-200 mb-6">{t("about.ctaText")}</p>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 px-6 py-3 bg-white text-indigo-700 font-semibold rounded-xl hover:bg-indigo-50 transition-colors"
          >
            {t("about.ctaButton")} <ArrowRight size={15} />
          </Link>
        </section>
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
          </Link>{" "}
          ·{" "}
          <Link to="/contact" className="hover:text-slate-600">
            {t("nav.contact")}
          </Link>
        </p>
      </footer>
    </>
  )
}
