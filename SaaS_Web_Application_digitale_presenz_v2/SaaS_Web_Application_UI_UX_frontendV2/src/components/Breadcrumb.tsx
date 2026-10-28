import Link from "./LocaleLink"
import { ChevronRight } from "lucide-react"
import { breadcrumbSchema } from "./SEO"
import { Helmet } from "react-helmet-async"
import { useT } from "../i18n"

interface CrumbItem {
  label: string
  path: string
}

export default function Breadcrumb({ items }: { items: CrumbItem[] }) {
  const t = useT()
  const schema = breadcrumbSchema(
    items.map((i) => ({ name: i.label, url: i.path })),
  )

  return (
    <>
      <Helmet>
        <script type="application/ld+json">{JSON.stringify(schema)}</script>
      </Helmet>
      <nav
        aria-label={t("common.breadcrumb")}
        className="flex items-center gap-1.5 text-sm text-slate-500 mb-6"
      >
        {items.map((item, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && (
              <ChevronRight
                size={12}
                className="text-slate-300 flex-shrink-0"
              />
            )}
            {i < items.length - 1 ? (
              <Link
                to={item.path}
                className="hover:text-slate-700 transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span className="text-slate-800 font-medium" aria-current="page">
                {item.label}
              </span>
            )}
          </span>
        ))}
      </nav>
    </>
  )
}
