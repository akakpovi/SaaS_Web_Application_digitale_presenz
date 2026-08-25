import { Helmet } from "react-helmet-async";

const SITE_NAME = "Presence";
const BASE_URL = "https://presence.io";
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.png`;

interface SEOProps {
  title: string;
  description: string;
  path?: string;
  noIndex?: boolean;
  ogType?: "website" | "article";
  ogImage?: string;
  lang?: "en" | "fr" | "de";
  hreflang?: { en?: string; fr?: string; de?: string };
  structuredData?: Record<string, unknown> | Record<string, unknown>[];
}

export default function SEO({
  title,
  description,
  path = "/",
  noIndex = false,
  ogType = "website",
  ogImage = DEFAULT_OG_IMAGE,
  lang = "en",
  hreflang,
  structuredData,
}: SEOProps) {
  const canonicalUrl = `${BASE_URL}${path}`;
  const fullTitle = title.includes(SITE_NAME) ? title : `${title} | ${SITE_NAME}`;

  const schemas = structuredData
    ? Array.isArray(structuredData)
      ? structuredData
      : [structuredData]
    : [];

  return (
    <Helmet>
      <html lang={lang} />
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <meta name="robots" content={noIndex ? "noindex,nofollow" : "index,follow"} />
      <link rel="canonical" href={canonicalUrl} />

      {/* Hreflang */}
      {hreflang?.en && <link rel="alternate" hrefLang="en" href={`${BASE_URL}${hreflang.en}`} />}
      {hreflang?.fr && <link rel="alternate" hrefLang="fr" href={`${BASE_URL}${hreflang.fr}`} />}
      {hreflang?.de && <link rel="alternate" hrefLang="de" href={`${BASE_URL}${hreflang.de}`} />}
      {hreflang?.en && <link rel="alternate" hrefLang="x-default" href={`${BASE_URL}${hreflang.en}`} />}

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content={ogType} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:site_name" content={SITE_NAME} />

      {/* Twitter/X Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@presenceio" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {/* Structured data */}
      {schemas.map((schema, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      ))}
    </Helmet>
  );
}

/* ── Reusable structured data builders ── */

export const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Presence",
  url: "https://presence.io",
  logo: "https://presence.io/icons/icon-512.png",
  description: "Digital presence monitoring for small businesses.",
  sameAs: [],
};

export const websiteSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Presence",
  url: "https://presence.io",
  potentialAction: {
    "@type": "SearchAction",
    target: "https://presence.io/tools/website-checker?q={search_term_string}",
    "query-input": "required name=search_term_string",
  },
};

export const softwareAppSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Presence",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web, iOS, Android",
  offers: [
    { "@type": "Offer", price: "0", priceCurrency: "EUR", name: "Free" },
    { "@type": "Offer", price: "5.99", priceCurrency: "EUR", name: "Pro" },
    { "@type": "Offer", price: "14.99", priceCurrency: "EUR", name: "Business" },
  ],
  description: "Monitor your website, SSL, DNS, email security, uptime and online reputation from one simple dashboard.",
  url: "https://presence.io",
};

export function faqSchema(items: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  };
}

export function breadcrumbSchema(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map(({ name, url }, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name,
      item: `https://presence.io${url}`,
    })),
  };
}
