import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { LANGUAGE_NAMES, AVAILABLE_LANGUAGES, type Language } from '../i18n/config';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const currentLanguage = ((i18n.resolvedLanguage || i18n.language).split('-')[0] ||
    'es') as Language;

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
    document.documentElement.dir = 'ltr';
  }, [currentLanguage]);

  const handleLanguageChange = (lng: Language) => {
    i18n.changeLanguage(lng);
  };

  return (
    <div className="flex items-center gap-1" role="group" aria-label="Language selector">
      {AVAILABLE_LANGUAGES.map(lng => (
        <button
          key={lng}
          onClick={() => handleLanguageChange(lng)}
          aria-pressed={currentLanguage === lng}
          aria-label={`Switch to ${LANGUAGE_NAMES[lng]}`}
          className={`rounded-md px-2 py-1 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 ${
            currentLanguage === lng
              ? 'bg-brand/10 text-brand-deep'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
          }`}
        >
          {lng.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
