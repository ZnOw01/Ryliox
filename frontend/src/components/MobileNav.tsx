import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/cn';

const MOBILE_SECTIONS = [
  { id: 'search-section', label: 'Buscar', icon: SearchIcon },
  { id: 'auth-section', label: 'Sesión', icon: UserIcon },
  { id: 'download-section', label: 'Descarga', icon: DownloadIcon },
] as const;

const HEADER_OFFSET_PX = 104;
type MobileSectionId = (typeof MOBILE_SECTIONS)[number]['id'];

/**
 * MobileNav - Bottom navigation for mobile devices
 * Provides quick access to main app sections on small screens.
 */
export function MobileNav() {
  const { t } = useTranslation();
  const sections = useMemo(
    () =>
      [
        { id: 'search-section', label: t('search.title'), icon: SearchIcon },
        { id: 'auth-section', label: t('auth.title'), icon: UserIcon },
        { id: 'download-section', label: t('download.title'), icon: DownloadIcon },
      ] as const,
    [t]
  );
  const [isVisible, setIsVisible] = useState(false);
  const [activeSection, setActiveSection] = useState<MobileSectionId>('search-section');
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const checkScreenSize = () => {
      setIsVisible(window.innerWidth < 1024);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 400);
    };

    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (!isVisible) {
      return;
    }

    const updateActiveSection = () => {
      let nextSection: MobileSectionId = sections[0].id;
      let bestDistance = Number.POSITIVE_INFINITY;

      for (const section of sections) {
        const element = document.getElementById(section.id);
        if (!element) {
          continue;
        }

        const distance = Math.abs(element.getBoundingClientRect().top - HEADER_OFFSET_PX);
        if (distance < bestDistance) {
          bestDistance = distance;
          nextSection = section.id;
        }
      }

      setActiveSection(nextSection);
    };

    updateActiveSection();
    window.addEventListener('scroll', updateActiveSection, { passive: true });
    window.addEventListener('resize', updateActiveSection);
    return () => {
      window.removeEventListener('scroll', updateActiveSection);
      window.removeEventListener('resize', updateActiveSection);
    };
  }, [isVisible, sections]);

  const scrollToSection = (sectionId: MobileSectionId) => {
    const element = document.getElementById(sectionId);
    if (!element) {
      return;
    }

    const top = element.getBoundingClientRect().top + window.scrollY - HEADER_OFFSET_PX;
    window.scrollTo({ top: Math.max(top, 0), behavior: 'smooth' });
    setActiveSection(sectionId);
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (!isVisible) return null;

  return (
    <>
      <nav
        className="safe-area-bottom fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card/95 px-2 py-2 shadow-lg backdrop-blur-lg sm:hidden"
        role="navigation"
        aria-label={t('common.navigation', { defaultValue: 'Mobile navigation' })}
      >
        <div className="mx-auto flex max-w-md items-center justify-around">
          {sections.map(section => {
            const Icon = section.icon;
            return (
              <NavButton
                key={section.id}
                active={activeSection === section.id}
                onClick={() => scrollToSection(section.id)}
                icon={<Icon />}
                label={section.label}
                controls={section.id}
              />
            );
          })}
          <NavButton
            active={false}
            onClick={scrollToTop}
            icon={<ArrowUpIcon />}
            label={t('mobile_nav.up')}
          />
        </div>
      </nav>

      <button
        onClick={scrollToTop}
        className={cn(
          'fixed bottom-6 right-6 z-50 hidden h-12 w-12 items-center justify-center rounded-full bg-primary p-3 text-primary-foreground shadow-lg transition-all duration-300 hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:flex',
          showScrollTop
            ? 'translate-y-0 opacity-100'
            : 'pointer-events-none translate-y-20 opacity-0'
        )}
        aria-label={t('mobile_nav.up')}
      >
        <ArrowUpIcon className="h-6 w-6" />
      </button>
    </>
  );
}

type NavButtonProps = {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  controls?: string;
};

function NavButton({ active, onClick, icon, label, controls }: NavButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex min-h-touch min-w-touch flex-col items-center justify-center gap-0.5 rounded-lg px-3 py-1 transition-colors',
        active
          ? 'bg-accent text-accent-foreground'
          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
      )}
      aria-controls={controls}
      aria-current={active ? 'location' : undefined}
    >
      <span className="h-5 w-5">{icon}</span>
      <span className="text-[10px] font-medium">{label}</span>
    </button>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className || 'h-5 w-5'}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className || 'h-5 w-5'}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className || 'h-5 w-5'}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className || 'h-5 w-5'}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m18 15-6-6-6 6" />
    </svg>
  );
}
