import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Moon, Sun, Monitor } from 'lucide-react';
import { cn } from '../lib/cn';

type Theme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'theme-preference';

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'system';
  return (localStorage.getItem(STORAGE_KEY) as Theme) || 'system';
}

function applyThemeToDocument(theme: Theme) {
  if (typeof window === 'undefined') return;
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', isDark);
}

// Apply theme immediately on module load to prevent flash
if (typeof window !== 'undefined') {
  applyThemeToDocument(getInitialTheme());
}

export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    applyThemeToDocument(theme);

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleMediaChange = () => {
      if (theme === 'system') {
        applyThemeToDocument('system');
      }
    };

    const handleToggleEvent = () => {
      cycleTheme();
    };

    mediaQuery.addEventListener('change', handleMediaChange);
    window.addEventListener('ryliox-toggle-theme', handleToggleEvent);
    return () => {
      mediaQuery.removeEventListener('change', handleMediaChange);
      window.removeEventListener('ryliox-toggle-theme', handleToggleEvent);
    };
  }, [theme]);

  const setThemePreference = (newTheme: Theme) => {
    setTheme(newTheme);
    localStorage.setItem(STORAGE_KEY, newTheme);
  };

  const cycleTheme = () => {
    if (theme === 'system') {
      const isSystemDark =
        typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
      setThemePreference(isSystemDark ? 'light' : 'dark');
      return;
    }

    if (theme === 'dark') {
      setThemePreference('light');
      return;
    }

    setThemePreference('system');
  };

  // Prevent hydration mismatch by rendering placeholder until mounted
  if (!mounted) {
    return (
      <button
        className="flex h-8 w-8 items-center justify-center rounded-xl border border-border bg-card/80 text-muted-foreground"
        aria-label={t('theme.loading')}
      >
        <Sun className="h-4 w-4 opacity-50" strokeWidth={1.75} />
      </button>
    );
  }

  const getThemeIcon = () => {
    switch (theme) {
      case 'dark':
        return <Moon className="h-4 w-4 text-primary" strokeWidth={2} aria-hidden="true" />;
      case 'system':
        return (
          <Monitor className="h-4 w-4 text-muted-foreground" strokeWidth={2} aria-hidden="true" />
        );
      case 'light':
      default:
        return <Sun className="h-4 w-4 text-amber-500" strokeWidth={2} aria-hidden="true" />;
    }
  };

  return (
    <button
      onClick={cycleTheme}
      aria-label={t(`theme.${theme}`)}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded-xl border border-border bg-card/80 shadow-2xs transition-all duration-200',
        'hover:border-primary/40 hover:bg-accent hover:text-foreground active:scale-95',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
      )}
      title={t(`theme.${theme}`)}
    >
      {getThemeIcon()}
    </button>
  );
}
