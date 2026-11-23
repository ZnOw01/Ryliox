import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect, lazy, Suspense } from 'react';
import { I18nextProvider } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import { HelpCircle } from 'lucide-react';

import { AuthStatusCard } from './AuthStatusCard';
import { DownloadProgressCard } from './DownloadProgressCard';
import { SearchBooksCard } from './SearchBooksCard';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { BeautifulToastContainer } from './ui/BeautifulToast';
import { KeyboardShortcutsModal, useKeyboardShortcuts } from './ui/KeyboardNavigation';
import { SkipLink } from './SkipLink';
import i18n, { applyPreferredLanguage } from '../i18n/config';
import { authenticateAdmin } from '../lib/api';
import { useTranslation } from 'react-i18next';
import { useBookStore } from '../store/book-store';
import {
  AnimatedLayoutGroup,
  StaggeredLayoutContainer,
  StaggeredLayoutItem,
} from './motion/LayoutAnimations';

import { AriaLiveRegion } from './AriaLiveRegion';

// Lazy load non-critical components
const MobileNav = lazy(() => import('./MobileNav').then(m => ({ default: m.MobileNav })));

function AppHeader({ onOpenShortcuts }: { onOpenShortcuts: () => void }) {
  const { t } = useTranslation();

  return (
    <header className="safe-area-top relative py-4 sm:py-6">
      <div className="flex min-w-0 items-center justify-between gap-3 sm:gap-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <div className="relative flex-none">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-primary via-primary/90 to-primary-foreground/20 text-2xl font-heading font-black tracking-tighter text-primary-foreground shadow-md shadow-primary/20 select-none sm:h-12 sm:w-12 sm:rounded-2xl sm:text-2xl">
              R
            </div>
            <span
              className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-background bg-emerald-500 shadow-xs sse-pulse"
              aria-hidden="true"
            ></span>
            <span className="sr-only">{t('app.status.active')}</span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-heading truncate text-lg font-bold leading-tight tracking-tight text-foreground sm:text-2xl md:text-3xl">
                {t('app.title')}
              </h1>
              <span className="hidden sm:inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary font-mono">
                v2.1
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs leading-tight text-muted-foreground">
              {t('app.subtitle')}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
          <button
            type="button"
            onClick={onOpenShortcuts}
            className="hidden sm:flex h-8 items-center gap-1.5 rounded-xl border border-border bg-card/80 px-2.5 text-xs font-medium text-muted-foreground shadow-2xs transition hover:border-primary/40 hover:bg-accent hover:text-foreground active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={t('keyboard_shortcuts.title') || 'Keyboard shortcuts'}
            aria-label={t('keyboard_shortcuts.title') || 'Keyboard shortcuts'}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            <kbd className="font-mono text-[10px] bg-muted px-1 rounded border border-border">
              ?
            </kbd>
          </button>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function AppContent({
  shortcutsModalOpen,
  setShortcutsModalOpen,
}: {
  shortcutsModalOpen: boolean;
  setShortcutsModalOpen: (open: boolean) => void;
}) {
  const { t } = useTranslation();

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      key: '?',
      action: () => setShortcutsModalOpen(true),
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.toggle_help'),
    },
    {
      key: '/',
      modifier: 'ctrl',
      action: () => setShortcutsModalOpen(true),
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.toggle_help'),
    },
    {
      key: 'k',
      modifier: 'ctrl',
      action: () => {
        const input = document.getElementById('search-input') as HTMLInputElement | null;
        if (input) {
          input.focus();
          input.select();
        }
      },
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.quick_search'),
    },
    {
      key: 't',
      modifier: 'alt',
      action: () => {
        window.dispatchEvent(new CustomEvent('ryliox-toggle-theme'));
      },
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.toggle_theme'),
    },
    {
      key: 'Escape',
      action: () => setShortcutsModalOpen(false),
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.close_modals'),
    },
  ]);

  return (
    <>
      <AnimatedLayoutGroup>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(320px,1fr)_minmax(0,1.25fr)] lg:items-start lg:gap-6">
          <StaggeredLayoutContainer className="flex min-w-0 flex-col gap-5">
            <StaggeredLayoutItem className="flex-shrink-0">
              <div id="auth-section" className="scroll-mt-28">
                <AuthStatusCard />
              </div>
            </StaggeredLayoutItem>
            <StaggeredLayoutItem>
              <SearchBooksCard />
            </StaggeredLayoutItem>
          </StaggeredLayoutContainer>
          <div className="min-w-0">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
              className="min-w-0"
            >
              <DownloadProgressCard />
            </motion.div>
          </div>
        </div>
      </AnimatedLayoutGroup>

      {/* Keyboard shortcuts modal */}
      <KeyboardShortcutsModal
        isOpen={shortcutsModalOpen}
        onClose={() => setShortcutsModalOpen(false)}
      />
    </>
  );
}

export default function App() {
  const { t } = useTranslation();
  const selectedBook = useBookStore(state => state.selectedBook);
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false);

  // After hydration, so the first client render matches the prerendered HTML.
  useEffect(applyPreferredLanguage, []);

  // Use lazy initialization to preserve QueryClient across HMR reloads
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  useEffect(() => {
    let authenticating = false;
    const requestAuthentication = async () => {
      if (authenticating) return;
      authenticating = true;
      const token = window.prompt(t('auth.admin_token_prompt'));
      if (!token) {
        authenticating = false;
        return;
      }
      try {
        await authenticateAdmin(token);
        await queryClient.invalidateQueries();
      } catch {
        window.alert(t('auth.admin_token_invalid'));
      } finally {
        authenticating = false;
      }
    };
    window.addEventListener('ryliox-admin-auth-required', requestAuthentication);
    return () => window.removeEventListener('ryliox-admin-auth-required', requestAuthentication);
  }, [queryClient, t]);

  // Smooth scroll to top when switching books
  useEffect(() => {
    if (!selectedBook) return;
    const main = document.getElementById('main-content');
    if (main) {
      main.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [selectedBook?.id]);

  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <SkipLink label={t('accessibility.skip_to_content')} />
        <AnimatePresence mode="wait">
          <motion.div
            key="app"
            className="safe-area-x bottom-nav-safe min-h-screen pb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <AppHeader onOpenShortcuts={() => setShortcutsModalOpen(true)} />
            <main id="main-content" tabIndex={-1} className="mt-4 sm:mt-6 @container">
              <AppContent
                shortcutsModalOpen={shortcutsModalOpen}
                setShortcutsModalOpen={setShortcutsModalOpen}
              />
            </main>
            <footer className="pb-4 pt-10 text-center text-xs text-muted-foreground/70">
              <p>{t('app.footer')}</p>
            </footer>
          </motion.div>
        </AnimatePresence>
        <BeautifulToastContainer />
        <AriaLiveRegion />
        <Suspense fallback={null}>
          <MobileNav />
        </Suspense>
      </QueryClientProvider>
    </I18nextProvider>
  );
}
