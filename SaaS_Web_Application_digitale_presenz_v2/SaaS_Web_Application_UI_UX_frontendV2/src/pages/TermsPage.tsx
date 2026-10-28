import Link from "../components/LocaleLink"
import { ArrowLeft, FileText } from "lucide-react"
import SEO from "../components/SEO"
import LegalReviewNotice from "../components/LegalReviewNotice"
import LanguageSwitcher from "../components/LanguageSwitcher"
import OperatorIdentityDetails from "../components/OperatorIdentityDetails"
import { isOperatorIdentityComplete } from "../config/operator"
import { useI18n } from "../i18n"

/**
 * Allgemeine Geschäftsbedingungen (terms of service).
 *
 * Same rules as the privacy page: German and English live in the catalogue, the
 * review banner stays visible, and clauses that need a lawyer are phrased as
 * open points instead of legal assertions. The B2B/B2C decision is deliberately
 * unresolved — the text says so rather than presuming consumers or businesses.
 */
interface Section {
  title: string
  intro?: string
  items?: string[]
  body?: string
  /** Additional paragraphs that always belong to the section. */
  extra?: string[]
  /** Renders the operator details block from `config/operator.json`. */
  details?: boolean
  links?: { label: string; to: string }[]
}

export default function TermsPage() {
  const { t, tList } = useI18n()

  const identityComplete = isOperatorIdentityComplete()

  const sections: Section[] = [
    {
      title: t("legal.termsScopeTitle"),
      body: identityComplete
        ? t("legal.termsScopeResolvedBody")
        : t("legal.termsScopeBody"),
      extra: [t("legal.termsScopeAudienceNote")],
      details: identityComplete,
    },
    { title: t("legal.termsServiceTitle"), body: t("legal.termsServiceBody") },
    { title: t("legal.termsAccountTitle"), body: t("legal.termsAccountBody") },
    {
      title: t("legal.termsUseTitle"),
      intro: t("legal.termsUseIntro"),
      items: tList("legal.termsUseItems"),
    },
    { title: t("legal.termsBillingTitle"), body: t("legal.termsBillingBody") },
    { title: t("legal.termsTermTitle"), body: t("legal.termsTermBody") },
    {
      title: t("legal.termsWithdrawalTitle"),
      body: t("legal.termsWithdrawalBody"),
      links: [{ label: t("legal.termsWithdrawalLink"), to: "/widerruf" }],
    },
    { title: t("legal.termsAvailabilityTitle"), body: t("legal.termsAvailabilityBody") },
    { title: t("legal.termsLiabilityTitle"), body: t("legal.termsLiabilityBody") },
    { title: t("legal.termsChangesTitle"), body: t("legal.termsChangesBody") },
    { title: t("legal.termsLawTitle"), body: t("legal.termsLawBody") },
    {
      title: t("legal.termsContactTitle"),
      body: t("legal.termsContactBody"),
      links: [{ label: t("legal.contactFormLink"), to: "/contact" }],
    },
  ]

  return (
    <div className="min-h-screen bg-white">
      <SEO
        title={`${t("legal.termsTitle")} | Presence`}
        description={t("legal.termsSubtitle")}
        path="/terms"
      />

      <header className="border-b border-slate-200">
        <div className="max-w-3xl mx-auto px-4 h-16 flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800"
          >
            <ArrowLeft size={14} /> Presence
          </Link>
          <div className="ml-auto">
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold text-slate-900 mb-3 flex items-center gap-3">
          <FileText size={24} className="text-indigo-600" />
          {t("legal.termsTitle")}
        </h1>
        <p className="text-slate-500 text-sm mb-4">
          {t("legal.lastUpdated")}: {t("legal.lastUpdatedDate")}
        </p>
        <p className="text-slate-600 leading-relaxed mb-8">
          {t("legal.termsIntro")}
        </p>

        {/* The banner stays until a qualified person has approved the text. */}
        <LegalReviewNotice />

        <div className="space-y-8 text-slate-700 leading-relaxed text-sm">
          {sections.map((section, index) => (
            <section key={section.title}>
              <h2 className="text-lg font-bold text-slate-900 mb-2">
                {index + 1}. {section.title}
              </h2>
              {section.intro && <p className="mb-2">{section.intro}</p>}
              {section.items && (
                <ul className="list-disc pl-5 space-y-1">
                  {section.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {section.body && <p className="mt-2">{section.body}</p>}
              {section.extra?.map((paragraph) => (
                <p key={paragraph} className="mt-2">
                  {paragraph}
                </p>
              ))}
              {section.details && <OperatorIdentityDetails />}
              {section.links?.map((link) => (
                <p key={link.to} className="mt-2">
                  <Link
                    to={link.to}
                    className="text-indigo-600 hover:underline"
                  >
                    {link.label}
                  </Link>
                </p>
              ))}
            </section>
          ))}
        </div>

        <p className="mt-10 text-sm text-slate-500">
          <Link to="/" className="text-indigo-600 hover:text-indigo-700">
            {t("legal.backHome")}
          </Link>
        </p>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center">
        <p className="text-sm text-slate-400">
          © 2026 Presence ·{" "}
          <Link to="/privacy" className="hover:text-slate-600">
            {t("legal.privacyLinkLabel")}
          </Link>{" "}
          ·{" "}
          <Link to="/contact" className="hover:text-slate-600">
            {t("legal.contactFormLink")}
          </Link>
        </p>
      </footer>
    </div>
  )
}
