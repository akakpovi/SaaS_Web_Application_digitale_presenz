import Link from "../components/LocaleLink"
import { ArrowLeft, Shield } from "lucide-react"
import SEO from "../components/SEO"
import LegalReviewNotice from "../components/LegalReviewNotice"
import LanguageSwitcher from "../components/LanguageSwitcher"
import OperatorIdentityDetails from "../components/OperatorIdentityDetails"
import { isOperatorIdentityComplete, operatorValue } from "../config/operator"
import { useI18n } from "../i18n"

/**
 * Datenschutzerklärung (privacy policy).
 *
 * The wording is a product draft, not reviewed legal text: the page renders the
 * German and English text from the catalogue and keeps the review banner on top
 * (see `LegalReviewNotice`). Statements were reconciled with the code before
 * translating — erasure is immediate (`delete_user_account`), reach measurement
 * is first-party with hashed IPs (`analytics/middleware.py`), and AKA IA sends
 * the user's input plus scan context to the AI gateway (`aka_client.py`).
 * Unverifiable facts stay as bracketed placeholders instead of being invented.
 */
interface Section {
  title: string
  intro?: string
  items?: string[]
  body?: string
  /** Renders the operator details block from `config/operator.json`. */
  details?: boolean
  links?: { label: string; to: string }[]
}

export default function PrivacyPage() {
  const { t, tList } = useI18n()

  const identityComplete = isOperatorIdentityComplete()

  const sections: Section[] = [
    {
      title: t("legal.privacyControllerTitle"),
      body: identityComplete
        ? t("legal.privacyControllerResolvedBody")
        : t("legal.privacyControllerBody"),
      details: identityComplete,
    },
    { title: t("legal.privacyDataTitle"), items: tList("legal.privacyDataItems") },
    { title: t("legal.privacyPurposeTitle"), items: tList("legal.privacyPurposeItems") },
    {
      title: t("legal.privacyLawfulTitle"),
      intro: t("legal.privacyLawfulIntro"),
      items: tList("legal.privacyLawfulItems"),
    },
    { title: t("legal.privacyAiTitle"), body: t("legal.privacyAiBody") },
    {
      title: t("legal.privacySharingTitle"),
      intro: t("legal.privacySharingIntro"),
      items: tList("legal.privacySharingItems"),
    },
    { title: t("legal.privacyRetentionTitle"), body: t("legal.privacyRetentionBody") },
    {
      title: t("legal.privacyRightsTitle"),
      intro: t("legal.privacyRightsIntro"),
      items: tList("legal.privacyRightsItems"),
      body: t("legal.privacyRightsHow"),
    },
    { title: t("legal.privacySecurityTitle"), body: t("legal.privacySecurityBody") },
    {
      title: t("legal.privacyCookiesTitle"),
      body: t("legal.privacyCookiesBody"),
      links: [{ label: t("legal.privacyCookiesLink"), to: "/cookies" }],
    },
    { title: t("legal.privacyChangesTitle"), body: t("legal.privacyChangesBody") },
    {
      title: t("legal.privacyContactTitle"),
      body: identityComplete
        ? t("legal.privacyContactResolvedBody", {
            email: operatorValue("email") ?? "",
          })
        : t("legal.privacyContactBody"),
      links: [{ label: t("legal.contactFormLink"), to: "/contact" }],
    },
  ]

  return (
    <div className="min-h-screen bg-white">
      <SEO
        title={`${t("legal.privacyTitle")} | Presence`}
        description={t("legal.privacySubtitle")}
        path="/privacy"
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
          <Shield size={24} className="text-indigo-600" />
          {t("legal.privacyTitle")}
        </h1>
        <p className="text-slate-500 text-sm mb-4">
          {t("legal.lastUpdated")}: {t("legal.lastUpdatedDate")}
        </p>
        <p className="text-slate-600 leading-relaxed mb-8">
          {t("legal.privacyIntro")}
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
          <Link to="/terms" className="hover:text-slate-600">
            {t("legal.termsLinkLabel")}
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
