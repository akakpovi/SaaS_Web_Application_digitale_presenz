import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Importer directement les fichiers JSON avec ?url pour les inclure dans le build
import frTranslations from './locales/fr.json';
import enTranslations from './locales/en.json';
import deTranslations from './locales/de.json';

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
    fallbackLng: 'fr',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['path', 'cookie', 'localStorage', 'navigator'],
      lookupFromPathIndex: 0,
      caches: ['cookie', 'localStorage'],
      cookieMinutes: 43200,
    },
  });

export default i18n;
