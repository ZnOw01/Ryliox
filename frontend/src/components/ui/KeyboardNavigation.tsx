import { useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import { X, Keyboard } from 'lucide-react';

// Tipos para atajos de teclado
export interface KeyboardShortcut {
  key: string;
  modifier?: 'ctrl' | 'alt' | 'shift' | 'meta';
  description: string;
  action: () => void;
  scope?: 'global' | 'search' | 'download' | 'modal';
}

// Hook para manejar atajos de teclado
export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[]) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignorar si estamos en un input o textarea (excepto atajos globales)
      const target = event.target as HTMLElement;
      const isInput =
        target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

      for (const shortcut of shortcuts) {
        const keyMatches = event.key.toLowerCase() === shortcut.key.toLowerCase();
        let modifierMatches = true;

        if (shortcut.modifier) {
          switch (shortcut.modifier) {
            case 'ctrl':
              modifierMatches = event.ctrlKey || event.metaKey;
              break;
            case 'alt':
              modifierMatches = event.altKey;
              break;
            case 'shift':
              modifierMatches = event.shiftKey;
              break;
            case 'meta':
              modifierMatches = event.metaKey;
              break;
          }
        } else {
          // Sin modificador - ignorar si hay modificadores presionados. Shift is
          // allowed for symbols, since it is what types them ('?' is Shift+/).
          const isSymbol = !/^[a-z0-9]$/i.test(shortcut.key);
          modifierMatches =
            !event.ctrlKey && !event.altKey && !event.metaKey && (isSymbol || !event.shiftKey);
        }

        // Para atajos no globales, ignorar si estamos en un input. A global
        // shortcut without Ctrl/Alt/Meta is a plain character there, so the
        // field keeps it (Escape is not a character and still works).
        const typesCharacter = !shortcut.modifier && shortcut.key.length === 1;
        if (isInput && (shortcut.scope !== 'global' || typesCharacter)) {
          continue;
        }

        if (keyMatches && modifierMatches) {
          event.preventDefault();
          shortcut.action();
          break;
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}

export function useFocusTrap(isActive: boolean, containerRef: React.RefObject<HTMLElement | null>) {
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isActive) return;

    // Guardar el focus anterior
    previousFocusRef.current = document.activeElement as HTMLElement;

    // Enfocar el primer elemento enfocable en el contenedor
    const container = containerRef.current;
    if (container) {
      const focusableElements = container.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      firstElement?.focus();
    }

    // Restaurar el focus al cerrar
    return () => {
      previousFocusRef.current?.focus();
    };
  }, [isActive, containerRef]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key !== 'Tab' || !containerRef.current) return;

      const focusableElements = containerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement?.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement?.focus();
      }
    },
    [containerRef]
  );

  return { handleKeyDown };
}

// Componente para mostrar hints de atajos
interface ShortcutHintProps {
  keys: string[];
  className?: string;
}

export function ShortcutHint({ keys, className }: ShortcutHintProps) {
  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      {keys.map((key, i) => (
        <span key={i} className="flex items-center">
          <kbd className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            {key}
          </kbd>
          {i < keys.length - 1 && <span className="mx-0.5 text-muted-foreground/50">+</span>}
        </span>
      ))}
    </span>
  );
}

// Modal de ayuda de atajos de teclado
interface KeyboardShortcutsHelpProps {
  isOpen: boolean;
  onClose: () => void;
}

const shortcutsList = [
  {
    categoryKey: 'keyboard_shortcuts.navigation',
    items: [
      { keys: ['↑', '↓'], descriptionKey: 'keyboard_shortcuts.shortcuts.navigate_results' },
      { keys: ['Enter'], descriptionKey: 'keyboard_shortcuts.shortcuts.select_book' },
      { keys: ['Esc'], descriptionKey: 'keyboard_shortcuts.shortcuts.close_or_cancel' },
      { keys: ['Tab'], descriptionKey: 'keyboard_shortcuts.shortcuts.move_focus' },
    ],
  },
  {
    categoryKey: 'keyboard_shortcuts.search',
    items: [{ keys: ['Ctrl', 'K'], descriptionKey: 'keyboard_shortcuts.shortcuts.quick_search' }],
  },
  {
    categoryKey: 'keyboard_shortcuts.general',
    items: [
      { keys: ['Alt', 'T'], descriptionKey: 'keyboard_shortcuts.shortcuts.toggle_theme' },
      { keys: ['?'], descriptionKey: 'keyboard_shortcuts.shortcuts.toggle_help' },
      { keys: ['Ctrl', '/'], descriptionKey: 'keyboard_shortcuts.shortcuts.this_menu' },
    ],
  },
];

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const { handleKeyDown } = useFocusTrap(isOpen, containerRef);

  // Cerrar con Escape
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            ref={containerRef}
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            onKeyDown={handleKeyDown}
            className={cn(
              'fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2',
              'rounded-2xl border border-border bg-card shadow-2xl',
              'max-h-[80vh] overflow-hidden'
            )}
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-title"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                  <Keyboard className="h-5 w-5 text-primary" aria-hidden="true" />
                </div>
                <div>
                  <h2 id="shortcuts-title" className="text-lg font-semibold text-foreground">
                    {t('keyboard_shortcuts.title')}
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    {t('keyboard_shortcuts.modal.description')}
                  </p>
                </div>
              </div>
              <motion.button
                onClick={onClose}
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                aria-label={t('common.close')}
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </motion.button>
            </div>

            {/* Content */}
            <div className="max-h-[60vh] overflow-y-auto p-6">
              <div className="grid gap-6">
                {shortcutsList.map((category, i) => (
                  <motion.div
                    key={category.categoryKey}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                  >
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      {t(category.categoryKey)}
                    </h3>
                    <div className="space-y-2">
                      {category.items.map((item, j) => (
                        <motion.div
                          key={j}
                          className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3"
                          whileHover={{ backgroundColor: 'rgba(0,0,0,0.04)' }}
                        >
                          <span className="text-sm text-foreground">{t(item.descriptionKey)}</span>
                          <ShortcutHint keys={item.keys} />
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="border-t border-border bg-muted/30 px-6 py-3">
              <p className="text-center text-xs text-muted-foreground">
                {t('keyboard_shortcuts.modal.hint_prefix')}
                <kbd className="rounded bg-background px-1.5 py-0.5 font-medium">?</kbd>
                {t('keyboard_shortcuts.modal.hint_suffix')}
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
