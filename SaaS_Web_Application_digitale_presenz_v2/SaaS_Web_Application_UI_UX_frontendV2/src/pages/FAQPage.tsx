import React, { useState } from "react"
import Link from "../components/LocaleLink"
import { ChevronDown, ArrowRight } from "lucide-react"
import SEO, { faqSchema } from "../components/SEO"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n, type MessageKey } from "../i18n"

interface FaqItem {
  q: string
  a: string
}

/**
 * Catalogue keys for one question.
 *
 * The key is built from the section and the item id; the casts are the single
 * dynamic boundary of this page and are covered by the compile-time shape
 * check of the catalogues plus the runtime "missing key" warning in `t()`.
 */
function item(section: string, id: string): { qKey: MessageKey; aKey: MessageKey } {
  return {
    qKey: `faqPage.categories.${section}.${id}.q` as MessageKey,
    aKey: `faqPage.categories.${section}.${id}.a` as MessageKey,
  }
}

const FAQ_SECTIONS: {
  nameKey: MessageKey
  items: { qKey: MessageKey; aKey: MessageKey }[]
}[] = [
  {
    nameKey: "faqPage.categories.general.name",
    items: [item("general", "i1"), item("general", "i2"), item("general", "i3"), item("general", "i4")],
  },
  {
    nameKey: "faqPage.categories.monitoring.name",
    items: [
      item("monitoring", "i1"),
      item("monitoring", "i2"),
      item("monitoring", "i3"),
      item("monitoring", "i4"),
      item("monitoring", "i5"),
    ],
  },
  {
    nameKey: "faqPage.categories.security.name",
    items: [
      item("security", "i1"),
      item("security", "i2"),
      item("security", "i3"),
      item("security", "i4"),
      item("security", "i5"),
    ],
  },
  {
    nameKey: "faqPage.categories.pwa.name",
    items: [item("pwa", "i1"), item("pwa", "i2"), item("pwa", "i3")],
  },
  {
    nameKey: "faqPage.categories.billing.name",
    items: [
      item("billing", "i1"),
      item("billing", "i2"),
      item("billing", "i3"),
      item("billing", "i4"),
    ],
  },
]

export default function FAQPage() {
  const { t } = useI18n()
  const [active, setActive] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  const sections = FAQ_SECTIONS.map((section) => ({
    name: t(section.nameKey),
    items: section.items.map<FaqItem>((entry) => ({
      q: t(entry.qKey),
      a: t(entry.aKey),
    })),
  }))

  const allFaqItems = sections.flatMap((section) => section.items)

  const filtered = search.trim()
    ? allFaqItems.filter(
        (faq) =>
          faq.q.toLowerCase().includes(search.toLowerCase()) ||
          faq.a.toLowerCase().includes(search.toLowerCase()),
      )
    : null

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t("meta.faq.title")}
        description={t("meta.faq.description")}
        path="/faq"
        structuredData={faqSchema(allFaqItems)}
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/#features" className="hover:text-slate-900">
              {t("nav.features")}
            </Link>
            <Link to="/pricing" className="hover:text-slate-900">
              {t("nav.pricing")}
            </Link>
            <Link to="/tools/website-checker" className="hover:text-slate-900">
              {t("faqPage.freeChecker")}
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link to="/register">
              <button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">
                {t("common.signup")}
              </button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-16">
        <h1 className="text-4xl font-bold text-slate-900 mb-4">
          {t("faqPage.title")}
        </h1>
        <p className="text-lg text-slate-500 mb-8">{t("faqPage.subtitle")}</p>

        {/* Search */}
        <div className="mb-10">
          <input
            type="search"
            placeholder={t("faqPage.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-4 py-3 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            aria-label={t("faqPage.searchLabel")}
          />
        </div>

        {/* Search results */}
        {filtered ? (
          <div className="space-y-3">
            {filtered.length === 0 ? (
              <p className="text-slate-500 text-sm">
                {t("faqPage.noResults", { query: search })}
              </p>
            ) : (
              filtered.map((faq, i) => {
                const key = `s-${i}`
                return (
                  <article
                    key={key}
                    className="bg-white border border-slate-200 rounded-xl overflow-hidden"
                  >
                    <button
                      className="w-full flex items-center justify-between px-5 py-4 text-left"
                      onClick={() => setActive(active === key ? null : key)}
                      aria-expanded={active === key}
                    >
                      <span className="font-medium text-slate-900">
                        {faq.q}
                      </span>
                      <ChevronDown
                        size={16}
                        className={`text-slate-400 flex-shrink-0 transition-transform ${
                          active === key ? "rotate-180" : ""
                        }`}
                      />
                    </button>
                    {/* Always rendered so the answer is part of the
                        pre-rendered HTML for crawlers; `hidden` keeps the
                        collapsed state for sighted users and assistive tech. */}
                    <div
                      hidden={active !== key}
                      className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3"
                    >
                      {faq.a}
                    </div>
                  </article>
                )
              })
            )}
          </div>
        ) : (
          /* Categorized */
          <div className="space-y-10">
            {sections.map(({ name, items }) => (
              <section key={name} aria-labelledby={`cat-${name}`}>
                <h2
                  id={`cat-${name}`}
                  className="text-lg font-bold text-slate-800 mb-4"
                >
                  {name}
                </h2>
                <div className="space-y-2">
                  {items.map((faq, i) => {
                    const key = `${name}-${i}`
                    return (
                      <article
                        key={key}
                        className="bg-white border border-slate-200 rounded-xl overflow-hidden"
                      >
                        <button
                          className="w-full flex items-center justify-between px-5 py-4 text-left"
                          onClick={() => setActive(active === key ? null : key)}
                          aria-expanded={active === key}
                        >
                          <span className="font-medium text-slate-900">
                            {faq.q}
                          </span>
                          <ChevronDown
                            size={16}
                            className={`text-slate-400 flex-shrink-0 transition-transform ${
                              active === key ? "rotate-180" : ""
                            }`}
                          />
                        </button>
                        {/* See the search-results branch above: the answer
                            stays in the HTML and is hidden with `hidden`. */}
                        <div
                          hidden={active !== key}
                          className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3"
                        >
                          {faq.a}
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        )}

        {/* CTA */}
        <div className="mt-16 p-6 bg-indigo-50 border border-indigo-100 rounded-2xl flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1">
            <p className="font-semibold text-indigo-900">
              {t("faqPage.ctaTitle")}
            </p>
            <p className="text-sm text-indigo-700 mt-1">{t("faqPage.ctaText")}</p>
          </div>
          <Link to="/tools/website-checker">
            <button className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2 whitespace-nowrap">
              {t("faqPage.ctaButton")} <ArrowRight size={14} />
            </button>
          </Link>
        </div>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center mt-8">
        <p className="text-sm text-slate-400">
          {t("footer.rights")}{" "}
          <Link to="/" className="hover:text-slate-600">
            {t("nav.about")}
          </Link>{" "}
          ·{" "}
          <Link to="/pricing" className="hover:text-slate-600">
            {t("nav.pricing")}
          </Link>{" "}
          ·{" "}
          <Link to="/impressum" className="hover:text-slate-600">
            {t("footer.impressum")}
          </Link>
        </p>
      </footer>
    </div>
  )
}
