import { Helmet } from 'react-helmet-async';
import { useLocation } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_BASE_URL ?? 'https://monsaas.com';
const SUPPORTED_LANGS = ['fr', 'en', 'de'] as const;
const DEFAULT_LANG = 'en';

interface SeoTagsProps {
  title?: string;
  description?: string;
}

/**
 * Composant SEO injectant dynamiquement les balises <title>, <meta>
 * et les balises hreflang pour le SEO multilingue.
 *
 * Usage :
 *   <SeoTags title="Scanner mon site" description="Analysez..." />
 */
export function SeoTags({ title, description }: SeoTagsProps) {
  const { pathname } = useLocation();

  // Extraire le chemin sans le préfixe de langue
  const langMatch = pathname.match(/^\/(fr|en|de)(\/.*)?$/);
  const currentLang = langMatch?.[1] ?? DEFAULT_LANG;
  const pathWithoutLang = langMatch?.[2] || pathname || '/';

  const pageTitle = title
    ? `${title} | Presence SaaS`
    : 'Presence SaaS — Surveillance de Présence Digitale';

  const pageDesc = description
    ?? 'Analysez la santé de votre site web en 30 secondes. SSL, DNS, performance, sécurité.';

  return (
    <Helmet>
      <title>{String(pageTitle)}</title>
      <meta name="description" content={pageDesc} />

      {/* Hreflang tags pour le SEO multilingue */}
      {SUPPORTED_LANGS.map((lang) => (
        <link
          key={lang}
          rel="alternate"
          hrefLang={lang}
          href={`${BASE_URL}/${lang}${pathWithoutLang}`}
        />
      ))}
      <link
        rel="alternate"
        hrefLang="x-default"
        href={`${BASE_URL}/${DEFAULT_LANG}${pathWithoutLang}`}
      />

      {/* Open Graph */}
      <meta property="og:title" content={pageTitle} />
      <meta property="og:description" content={pageDesc} />
      <meta property="og:locale" content={currentLang === 'fr' ? 'fr_FR' : currentLang === 'de' ? 'de_DE' : 'en_US'} />
      <meta property="og:type" content="website" />
    </Helmet>
  );
}

export default SeoTags;
