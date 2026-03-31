import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

interface Shortcut {
  key: string;
  description: string;
  action: () => void;
  ctrl?: boolean;
  alt?: boolean;
  shift?: boolean;
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      // Skip if user is typing in an input
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      ) {
        return;
      }

      for (const shortcut of shortcuts) {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl
          ? event.ctrlKey || event.metaKey
          : !event.ctrlKey && !event.metaKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;

        if (keyMatch && ctrlMatch && altMatch && shiftMatch) {
          event.preventDefault();
          shortcut.action();
          break;
        }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shortcuts]);
}

export function KeyboardShortcutsHelp() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const toggleHelp = useCallback(() => setIsOpen(prev => !prev), []);

  // Global ? shortcut
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === '?' && !event.ctrlKey && !event.metaKey && !event.altKey) {
        // Don't trigger if user is typing
        if (
          event.target instanceof HTMLInputElement ||
          event.target instanceof HTMLTextAreaElement ||
          event.target instanceof HTMLSelectElement
        ) {
          return;
        }
        event.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 left-4 z-40 flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-500 shadow-sm transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
        aria-label={t('keyboard_shortcuts.show_help')}
        title={t('keyboard_shortcuts.show_help')}
      >
        <span className="text-sm font-semibold">?</span>
      </button>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => setIsOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="shortcuts-title" className="text-lg font-semibold text-slate-900">
            {t('keyboard_shortcuts.title')}
          </h2>
          <button
            onClick={() => setIsOpen(false)}
            aria-label={t('common.close')}
            className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
          >
            <svg className="h-5 w-5" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M5 5l6 6M11 5l-6 6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <ShortcutSection
            title={t('keyboard_shortcuts.navigation')}
            shortcuts={[
              { key: '↑/↓', desc: t('keyboard_shortcuts.shortcuts.navigate_results') },
              { key: 'Enter', desc: t('keyboard_shortcuts.shortcuts.select_book') },
              { key: 'Esc', desc: t('keyboard_shortcuts.shortcuts.clear_search') },
            ]}
          />
          <ShortcutSection
            title={t('keyboard_shortcuts.actions')}
            shortcuts={[
              { key: 'Ctrl+Enter', desc: t('keyboard_shortcuts.shortcuts.start_download') },
              { key: 'Ctrl+.', desc: t('keyboard_shortcuts.shortcuts.cancel_download') },
              { key: '?', desc: t('keyboard_shortcuts.shortcuts.toggle_help') },
            ]}
          />
          <ShortcutSection
            title={t('keyboard_shortcuts.search')}
            shortcuts={[
              { key: '/', desc: t('keyboard_shortcuts.shortcuts.focus_search') },
              { key: 'Ctrl+K', desc: t('keyboard_shortcuts.shortcuts.focus_search') },
            ]}
          />
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={() => setIsOpen(false)}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
}

function ShortcutSection({
  title,
  shortcuts,
}: {
  title: string;
  shortcuts: { key: string; desc: string }[];
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="space-y-1">
        {shortcuts.map(shortcut => (
          <div key={shortcut.key} className="flex items-center justify-between py-1">
            <span className="text-sm text-slate-700">{shortcut.desc}</span>
            <kbd className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-mono text-slate-600">
              {shortcut.key}
            </kbd>
          </div>
        ))}
      </div>
    </div>
  );
}
