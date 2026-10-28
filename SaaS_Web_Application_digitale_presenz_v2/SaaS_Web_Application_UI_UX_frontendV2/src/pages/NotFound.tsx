import React from "react"
import Link from "../components/LocaleLink"
import { ArrowLeft, Search } from "lucide-react"
import SEO from "../components/SEO"
import { useI18n } from "../i18n"

export default function NotFound() {
  const { t } = useI18n()
  return (
    <>
      <SEO
        title={`${t("notFound.title")} | Presence`}
        description={t("notFound.subtitle")}
        noIndex
        path="/404"
      />
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 text-center">
        <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mb-6">
          <Search size={28} className="text-indigo-600" />
        </div>
        <p className="text-7xl font-black text-slate-200 mb-4 select-none">
          404
        </p>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">
          {t("notFound.title")}
        </h1>
        <p className="text-slate-500 max-w-sm mb-8">{t("notFound.subtitle")}</p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white font-medium rounded-xl hover:bg-indigo-700 transition-colors text-sm"
          >
            <ArrowLeft size={15} /> {t("notFound.home")}
          </Link>
          <Link
            to="/app/dashboard"
            className="inline-flex items-center gap-2 px-5 py-2.5 border border-slate-300 text-slate-700 font-medium rounded-xl hover:bg-slate-50 transition-colors text-sm"
          >
            {t("notFound.dashboard")}
          </Link>
        </div>
        <p className="mt-8 text-xs text-slate-400">
          <Link to="/faq" className="text-indigo-600 hover:underline">
            {t("nav.faq")}
          </Link>{" "}
          ·{" "}
          <Link to="/contact" className="text-indigo-600 hover:underline">
            {t("nav.contact")}
          </Link>
        </p>
      </div>
    </>
  )
}
