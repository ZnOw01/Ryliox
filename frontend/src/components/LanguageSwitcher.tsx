import { useTranslation } from 'react-i18next';
import { LANGUAGE_NAMES, AVAILABLE_LANGUAGES, type Language } from '../i18n/config';
import { cn } from '../lib/cn';

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const currentLanguage = i18n.resolvedLanguage ?? i18n.language;

  const handleLanguageChange = (lng: Language) => {
    i18n.changeLanguage(lng);
  };

  return (
    <div
      className="flex items-center gap-0.5 rounded-xl border border-border bg-card/80 p-0.5 shadow-2xs"
      role="group"
      aria-label={t('accessibility.language_switcher')}
    >
      {AVAILABLE_LANGUAGES.map(lng => {
        const isCurrent = currentLanguage === lng;
        return (
          <button
            key={lng}
            onClick={() => handleLanguageChange(lng)}
            aria-pressed={isCurrent}
            aria-label={t('accessibility.switch_language', { language: LANGUAGE_NAMES[lng] })}
            title={LANGUAGE_NAMES[lng]}
            className={cn(
              'rounded-lg px-2 py-1 text-[11px] font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isCurrent
                ? 'bg-primary text-primary-foreground shadow-2xs'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )}
          >
            {lng.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
