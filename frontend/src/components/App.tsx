import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect, lazy, Suspense } from 'react';
import { I18nextProvider } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';

import { AuthStatusCard } from './AuthStatusCard';
import { DownloadProgressCard } from './DownloadProgressCard';
import { SearchBooksCard } from './SearchBooksCard';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { BeautifulToastContainer, toast as beautifulToast } from './ui/BeautifulToast';
import { KeyboardShortcutsModal, useKeyboardShortcuts } from './ui/KeyboardNavigation';
import { SkipLink } from './SkipLink';
import i18n from '../i18n/config';
import { isEnabled } from '../lib/feature-flags';
import { useTranslation } from 'react-i18next';
import type { ProgressResponse } from '../lib/types';
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
    <header className="safe-area-top sticky-header soft-rise rounded-2xl border border-border bg-card/90 px-4 py-3 shadow-panel backdrop-blur-sm sm:px-6 sm:py-4">
      <div className="flex min-w-0 items-center justify-between gap-3 sm:gap-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <div className="relative flex-none">
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-primary to-primary-foreground text-2xl font-bold tracking-tight text-primary-foreground shadow-md select-none sm:h-14 sm:w-14 sm:rounded-2xl sm:text-3xl">
              R
            </div>
            <span
              className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-background bg-emerald-400 shadow-sm sm:h-3.5 sm:w-3.5"
              aria-hidden="true"
            ></span>
            <span className="sr-only">{t('app.status.active')}</span>
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl md:text-4xl">
              {t('app.title')}
            </h1>
            <p className="mt-1 truncate text-xs leading-tight text-muted-foreground sm:text-sm">
              {t('app.subtitle')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
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
      description: 'Mostrar atajos de teclado',
    },
    {
      key: 'Escape',
      action: () => setShortcutsModalOpen(false),
      scope: 'global',
      description: 'Cerrar modales',
    },
  ]);

  // Announce download progress changes
  useEffect(() => {
    const handleProgressUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<ProgressResponse>;
      const data = customEvent.detail;

      if (data.status === 'completed') {
        beautifulToast.success(t('download.notifications.download_completed'));
      } else if (data.status === 'error' && data.error) {
        beautifulToast.error(data.error);
      }
    };

    window.addEventListener('download-progress', handleProgressUpdate);
    return () => window.removeEventListener('download-progress', handleProgressUpdate);
  }, [t]);

  return (
    <>
      <AnimatedLayoutGroup>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(320px,1fr)_minmax(0,1.25fr)] lg:items-start lg:gap-6">
          <StaggeredLayoutContainer className="flex min-w-0 flex-col gap-4">
            <StaggeredLayoutItem className="flex-shrink-0">
              <AuthStatusCard />
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
            <main id="main-content" tabIndex={-1} className="mt-6 sm:mt-8">
              <AppContent />
            </main>
            <footer className="pb-2 pt-8 text-center text-xs text-muted-foreground">
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
