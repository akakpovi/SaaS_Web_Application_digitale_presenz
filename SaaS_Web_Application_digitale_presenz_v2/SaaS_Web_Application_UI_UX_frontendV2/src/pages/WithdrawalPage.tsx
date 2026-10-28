import Link from "../components/LocaleLink"
import { AlertTriangle, ArrowLeft, Undo2 } from "lucide-react"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import OperatorIdentityDetails from "../components/OperatorIdentityDetails"
import { isOperatorIdentityComplete } from "../config/operator"
import { useI18n } from "../i18n"

/**
 * Widerrufsbelehrung (right of withdrawal).
 *
 * German consumer law expects this information before a paid subscription can
 * be concluded. No deadline wording and no model form text are known to the
 * code base, so nothing is invented here: the page carries the same warning
 * band as the imprint, four explained sections and the explicit list of items
 * a qualified person has to complete before launch. Once the operator data
 * exists in `config/operator.json`, the recipient address is rendered from
 * that single source instead of pointing at the imprint.
 */
export default function WithdrawalPage() {
  const { t, tList } = useI18n()
  const identityComplete = isOperatorIdentityComplete()

  const sections: { title: string; body: string }[] = [
    {
      title: t("legal.withdrawalScopeTitle"),
      body: t("legal.withdrawalScopeBody"),
    },
    {
      title: t("legal.withdrawalDeadlineTitle"),
      body: t("legal.withdrawalDeadlineBody"),
    },
    {
      title: t("legal.withdrawalProcessTitle"),
      body: t("legal.withdrawalProcessBody"),
    },
    {
      title: t("legal.withdrawalFormTitle"),
      body: t("legal.withdrawalFormBody"),
    },
  ]

  return (
    <div className="min-h-screen bg-white">
      <SEO
        title={`${t("legal.withdrawalTitle")} | Presence`}
        description={t("legal.withdrawalSubtitle")}
        path="/widerruf"
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
          <Undo2 size={24} className="text-indigo-600" />
          {t("legal.withdrawalTitle")}
        </h1>
        <p className="text-slate-600 leading-relaxed mb-6">
          {t("legal.withdrawalSubtitle")}
        </p>

        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-300 bg-amber-50 mb-8">
          <AlertTriangle
            size={16}
            className="text-amber-500 flex-shrink-0 mt-0.5"
          />
          <div className="text-sm text-amber-900">
            <p className="font-semibold mb-1">{t("legal.legalNoticeTitle")}</p>
            <p className="leading-relaxed">{t("legal.withdrawalNotice")}</p>
          </div>
        </div>

        <div className="space-y-6">
          {sections.map((section) => (
            <section key={section.title}>
              <h2 className="text-lg font-bold text-slate-900 mb-1">
                {section.title}
              </h2>
              <p className="text-slate-600 leading-relaxed text-sm">
                {section.body}
              </p>
            </section>
          ))}
        </div>

        {identityComplete && (
          <section className="mt-10">
            <h2 className="text-lg font-bold text-slate-900 mb-1">
              {t("legal.withdrawalRecipientTitle")}
            </h2>
            <OperatorIdentityDetails variant="address" />
          </section>
        )}

        <section className="mt-10 p-5 rounded-xl border border-slate-200 bg-slate-50">
          <h2 className="text-sm font-bold text-slate-900 mb-3">
            {t("legal.withdrawalMissingTitle")}
          </h2>
          <ul className="space-y-2 text-sm text-slate-600">
            {tList("legal.withdrawalMissingItems").map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500"
                />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <p className="mt-8 text-sm text-slate-500">
          <Link to="/" className="text-indigo-600 hover:text-indigo-700">
            {t("legal.backHome")}
          </Link>
        </p>
      </main>
    </div>
  )
}
