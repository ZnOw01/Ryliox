import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import es from './locales/es.json';
import en from './locales/en.json';

export const AVAILABLE_LANGUAGES = ['es', 'en'] as const;
export type Language = (typeof AVAILABLE_LANGUAGES)[number];

export const LANGUAGE_NAMES: Record<Language, string> = {
  es: 'Español',
  en: 'English',
};

const DEFAULT_LANGUAGE: Language = 'es';
const STORAGE_KEY = 'i18nextLng';

function isLanguage(value: string): value is Language {
  return AVAILABLE_LANGUAGES.some(language => language === value);
}

// The page is prerendered in DEFAULT_LANGUAGE and must hydrate in the same
// language, so i18n always starts there. The visitor's choice is applied once
// React has hydrated, by applyPreferredLanguage().
i18n.use(initReactI18next).init({
  resources: {
    es: { translation: es },
    en: { translation: en },
  },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: AVAILABLE_LANGUAGES,
  interpolation: {
    escapeValue: false, // React already escapes values
  },
});

i18n.on('languageChanged', language => {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = language;
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, language);
  }
});

/** The stored choice, else the first supported browser language, else the default. */
export function preferredLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && isLanguage(stored)) {
    return stored;
  }
  for (const tag of navigator.languages) {
    const base = tag.split('-')[0]?.toLowerCase() ?? '';
    if (isLanguage(base)) {
      return base;
    }
  }
  return DEFAULT_LANGUAGE;
}

export function applyPreferredLanguage(): void {
  const language = preferredLanguage();
  if (language !== i18n.language) {
    void i18n.changeLanguage(language);
  }
}

export default i18n;
