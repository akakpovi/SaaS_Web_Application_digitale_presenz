import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Importer directement les fichiers JSON avec ?url pour les inclure dans le build
import frTranslations from './locales/fr.json';
import enTranslations from './locales/en.json';
import deTranslations from './locales/de.json';

export const SUPPORTED_LOCALES = ['de', 'fr', 'en'] as const;
export type Lang = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Lang = 'de';

function normalizeLocale(value?: string | null): Lang | null {
  const base = (value || '').split('-')[0].toLowerCase();
  return (SUPPORTED_LOCALES as readonly string[]).includes(base)
    ? (base as Lang)
    : null;
}

export function detectLocaleFromPath(pathname = window.location.pathname): Lang | null {
  const match = pathname.match(/^\/(de|fr|en)(?:\/|$)/);
  return match ? (match[1] as Lang) : null;
}

export function detectBrowserLocale(): Lang {
  return normalizeLocale(typeof navigator !== 'undefined' ? navigator.language : null) ?? DEFAULT_LOCALE;
}

export function detectLocale(pathname = window.location.pathname): Lang {
  return detectLocaleFromPath(pathname) ?? detectBrowserLocale();
}

const resources = {
  fr: { translation: frTranslations },
  en: { translation: enTranslations },
  de: { translation: deTranslations },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    lng: detectLocale(),
    supportedLngs: [...SUPPORTED_LOCALES],
    fallbackLng: DEFAULT_LOCALE,
    load: 'languageOnly',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['path', 'navigator'],
      lookupFromPathIndex: 0,
      caches: [],
    },
  });

export default i18n;
