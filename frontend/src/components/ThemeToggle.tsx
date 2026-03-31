import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Moon, Sun, Desktop } from '@phosphor-icons/react';

type Theme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'theme-preference';

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'system';
  return (localStorage.getItem(STORAGE_KEY) as Theme) || 'system';
}

function getIsDark(theme: Theme): boolean {
  if (typeof window === 'undefined') return false;
  if (theme === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  return theme === 'dark';
}

// Apply theme immediately on module load to prevent flash
if (typeof window !== 'undefined') {
  const savedTheme = localStorage.getItem(STORAGE_KEY) as Theme | null;
  const isDark = savedTheme
    ? savedTheme === 'dark' ||
      (savedTheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.classList.toggle('dark', isDark);
}

export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [isDark, setIsDark] = useState(() => getIsDark(getInitialTheme()));
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const updateTheme = () => {
      const isDarkMode = getIsDark(theme);
      setIsDark(isDarkMode);
      document.documentElement.classList.toggle('dark', isDarkMode);
    };

    updateTheme();

    mediaQuery.addEventListener('change', updateTheme);
    return () => mediaQuery.removeEventListener('change', updateTheme);
  }, [theme]);

  const setThemePreference = (newTheme: Theme) => {
    setTheme(newTheme);
    localStorage.setItem(STORAGE_KEY, newTheme);
  };

  const cycleTheme = () => {
    if (theme === 'system') {
      setThemePreference(getIsDark('system') ? 'light' : 'dark');
      return;
    }

    if (theme === 'dark') {
      setThemePreference('light');
      return;
    }

    setThemePreference('system');
  };

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <button
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground"
        aria-label={t('theme.loading')}
      >
        <Sun className="h-4 w-4 opacity-50" weight="regular" />
      </button>
    );
  }

  const getThemeIcon = () => {
    switch (theme) {
      case 'dark':
        return <Moon className="h-4 w-4" weight="regular" aria-hidden="true" />;
      case 'system':
        return <Desktop className="h-4 w-4" weight="regular" aria-hidden="true" />;
      case 'light':
      default:
        return <Sun className="h-4 w-4" weight="regular" aria-hidden="true" />;
    }
  };

  return (
    <button
      onClick={cycleTheme}
      aria-label={t(`theme.${theme}`)}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground transition hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
      title={t(`theme.${theme}`)}
    >
      {getThemeIcon()}
    </button>
  );
}

// Hook to use theme in other components
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  const [isDark, setIsDark] = useState(() => getIsDark(getInitialTheme()));
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const updateTheme = () => {
      const isDarkMode = getIsDark(theme);
      setIsDark(isDarkMode);
      document.documentElement.classList.toggle('dark', isDarkMode);
    };

    updateTheme();

    mediaQuery.addEventListener('change', updateTheme);
    return () => mediaQuery.removeEventListener('change', updateTheme);
  }, [theme]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem(STORAGE_KEY, newTheme);
  };

  return { theme, setTheme, isDark, mounted };
}
