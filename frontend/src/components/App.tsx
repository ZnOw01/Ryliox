import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect, lazy, Suspense } from 'react';
import { I18nextProvider } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';

import { AuthStatusCard } from './AuthStatusCard';
import { DownloadProgressCard } from './DownloadProgressCard';
import { SearchBooksCard } from './SearchBooksCard';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { BeautifulToastContainer } from './ui/BeautifulToast';
import { KeyboardShortcutsModal, useKeyboardShortcuts } from './ui/KeyboardNavigation';
import { SkipLink } from './SkipLink';
import i18n from '../i18n/config';
import { isEnabled } from '../lib/feature-flags';
import { authenticateAdmin } from '../lib/api';
import { useTranslation } from 'react-i18next';
import { useBookStore } from '../store/book-store';
import {
  AnimatedLayoutGroup,
  StaggeredLayoutContainer,
  StaggeredLayoutItem,
} from './motion/LayoutAnimations';

// Lazy load non-critical components
const AriaLiveRegion = lazy(() =>
  import('./AriaLiveRegion').then(m => ({ default: m.AriaLiveRegion }))
);
const MobileNav = lazy(() => import('./MobileNav').then(m => ({ default: m.MobileNav })));

function AppHeader() {
  const { t } = useTranslation();

  return (
    <header className="safe-area-top relative py-4 sm:py-6">
      <div className="flex min-w-0 items-center justify-between gap-3 sm:gap-4">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-4">
          <div className="relative flex-none">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-primary to-primary-foreground text-xl font-heading font-extrabold tracking-tight text-primary-foreground shadow-md select-none sm:h-12 sm:w-12 sm:rounded-2xl sm:text-2xl">
              R
            </div>
            <span
              className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-400 shadow-sm sse-pulse sm:h-3 sm:w-3"
              aria-hidden="true"
            ></span>
            <span className="sr-only">{t('app.status.active')}</span>
          </div>
          <div className="min-w-0">
            <h1 className="font-heading truncate text-lg font-bold leading-tight tracking-tight text-foreground sm:text-2xl md:text-3xl">
              {t('app.title')}
            </h1>
            <p className="mt-0.5 truncate text-[10px] leading-tight text-muted-foreground sm:text-xs sm:mt-1">
              {t('app.subtitle')}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
          {isEnabled('enable_i18n') && <LanguageSwitcher />}
          {isEnabled('enable_dark_mode') && <ThemeToggle />}
        </div>
      </div>
    </header>
  );
}

function AppContent() {
  const { t } = useTranslation();
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false);

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      key: '?',
      action: () => setShortcutsModalOpen(true),
      scope: 'global',
      description: t('keyboard_shortcuts.shortcuts.toggle_help'),
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
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(320px,1fr)_minmax(0,1.25fr)] lg:items-start lg:gap-6">
          <StaggeredLayoutContainer className="flex min-w-0 flex-col gap-4">
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
            className="safe-area-x bottom-nav-safe min-h-screen pb-6 sm:pb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <AppHeader />
            <main id="main-content" tabIndex={-1} className="mt-6 sm:mt-8 @container">
              <AppContent />
            </main>
            <footer className="pb-2 pt-8 text-center text-xs text-gray-400">
              {t('app.footer')}
            </footer>
          </motion.div>
        </AnimatePresence>
        {isEnabled('enable_toast_notifications') && <BeautifulToastContainer />}
        <Suspense fallback={null}>
          <AriaLiveRegion />
          <MobileNav />
        </Suspense>
      </QueryClientProvider>
    </I18nextProvider>
  );
}
