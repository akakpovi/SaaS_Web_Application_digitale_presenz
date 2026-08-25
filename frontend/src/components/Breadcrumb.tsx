import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { breadcrumbSchema } from "./SEO";
import { Helmet } from "react-helmet-async";

interface CrumbItem {
  label: string;
  path: string;
}

export default function Breadcrumb({ items }: { items: CrumbItem[] }) {
  const schema = breadcrumbSchema(items.map(i => ({ name: i.label, url: i.path })));

  return (
    <>
      <Helmet>
        <script type="application/ld+json">{JSON.stringify(schema)}</script>
      </Helmet>
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-slate-500 mb-6">
        {items.map((item, i) => (
          <span key={item.path} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight size={12} className="text-slate-300 flex-shrink-0" />}
            {i < items.length - 1 ? (
              <Link to={item.path} className="hover:text-slate-700 transition-colors">
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
  );
}
