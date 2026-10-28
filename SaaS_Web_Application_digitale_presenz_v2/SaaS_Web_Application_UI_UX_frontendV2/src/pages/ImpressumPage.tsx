import Link from "../components/LocaleLink"
import { AlertTriangle, ArrowLeft, FileWarning } from "lucide-react"
import SEO from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"
import {
  hasUnresolvedPlaceholders,
  operatorImpressumRows,
} from "../config/operator"

/**
 * Impressum (§ 5 DDG).
 *
 * The provider data comes from the single source in `config/operator.json`:
 * filling a value there updates the imprint — and the privacy, terms and
 * withdrawal pages — at once. Values that are not set stay visibly marked
 * placeholders; the page never invents an address, register number or VAT ID.
 * German law requires the real provider, a reachable contact address and the
 * authorised representative, so publishing the placeholders unchanged is a
 * legal defect, not a cosmetic one.
 */
export default function ImpressumPage() {
  const { t } = useI18n()

  const rows = operatorImpressumRows()
  const placeholdersPending = hasUnresolvedPlaceholders()

  return (
    <div className="min-h-screen bg-white">
      <SEO
        title={t("meta.impressum.title")}
        description={t("meta.impressum.description")}
        path="/impressum"
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
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          {t("legal.impressumTitle")}
        </h1>
        <p className="text-sm text-slate-500 mb-8">
          {t("legal.impressumSubtitle")}
        </p>

        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-300 rounded-xl mb-10">
          <AlertTriangle
            size={18}
            className="text-amber-600 flex-shrink-0 mt-0.5"
          />
          <div>
            <p className="text-sm font-semibold text-amber-900 mb-1">
              {t(
                placeholdersPending
                  ? "legal.legalNoticeTitle"
                  : "legal.legalNoticeTitleComplete",
              )}
            </p>
            <p className="text-sm text-amber-800 leading-relaxed">
              {t(
                placeholdersPending
                  ? "legal.legalNoticeBody"
                  : "legal.legalNoticeBodyComplete",
              )}
            </p>
          </div>
        </div>

        <dl className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
          {rows.map((row) => {
            const isPlaceholder = row.status === "missing"
            return (
              <div
                key={row.key}
                className="grid sm:grid-cols-3 gap-2 px-4 py-3"
              >
                <dt className="text-sm font-medium text-slate-600">
                  {t(row.labelKey)}
                </dt>
                <dd className="sm:col-span-2 text-sm text-slate-900 flex items-start gap-2">
                  {isPlaceholder && (
                    <FileWarning
                      size={14}
                      className="text-amber-500 flex-shrink-0 mt-0.5"
                    />
                  )}
                  <span
                    className={
                      isPlaceholder ? "font-mono break-all" : "break-words"
                    }
                  >
                    {isPlaceholder && row.placeholderKey
                      ? t(row.placeholderKey)
                      : row.value}
                    {isPlaceholder && (
                      <span className="ml-2 inline-block px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-semibold uppercase tracking-wide">
                        {t("legal.placeholderLabel")}
                      </span>
                    )}
                  </span>
                </dd>
              </div>
            )
          })}
        </dl>

        <section className="mt-10 space-y-4 text-sm text-slate-600 leading-relaxed">
          <h2 className="text-lg font-bold text-slate-900">
            {t("legal.withdrawalTitle")}
          </h2>
          <p>{t("legal.withdrawalNotice")}</p>
          <p>{t("legal.vatNotice")}</p>
        </section>
      </main>
    </div>
  )
}
