import { useEffect, useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../lib/cn';
import { X, Keyboard } from '@phosphor-icons/react';

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
          // Sin modificador - ignorar si hay modificadores presionados
          modifierMatches = !event.ctrlKey && !event.altKey && !event.shiftKey && !event.metaKey;
        }

        // Para atajos no globales, ignorar si estamos en un input
        if (shortcut.scope !== 'global' && isInput) {
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

// Hook para manejar navegación por teclado en listas
interface UseListNavigationOptions {
  itemCount: number;
  onSelect: (index: number) => void;
  onEscape?: () => void;
  circular?: boolean;
}

export function useListNavigation({
  itemCount,
  onSelect,
  onEscape,
  circular = true,
}: UseListNavigationOptions) {
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLElement>(null);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (itemCount === 0) return;

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setActiveIndex(prev => {
            if (circular && prev === itemCount - 1) return 0;
            return Math.min(prev + 1, itemCount - 1);
          });
          break;
        case 'ArrowUp':
          event.preventDefault();
          setActiveIndex(prev => {
            if (circular && prev === 0) return itemCount - 1;
            return Math.max(prev - 1, 0);
          });
          break;
        case 'Enter':
          event.preventDefault();
          onSelect(activeIndex);
          break;
        case 'Escape':
          event.preventDefault();
          onEscape?.();
          break;
        case 'Home':
          event.preventDefault();
          setActiveIndex(0);
          break;
        case 'End':
          event.preventDefault();
          setActiveIndex(itemCount - 1);
          break;
      }
    },
    [itemCount, activeIndex, onSelect, onEscape, circular]
  );

  // Scroll al item activo
  useEffect(() => {
    if (!listRef.current) return;

    const activeItem = listRef.current.querySelector(`[data-nav-index="${activeIndex}"]`);
    if (activeItem) {
      activeItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [activeIndex]);

  return {
    activeIndex,
    setActiveIndex,
    listRef,
    handleKeyDown,
    getItemProps: (index: number) => ({
      'data-nav-index': index,
      'aria-selected': index === activeIndex,
      tabIndex: index === activeIndex ? 0 : -1,
      onMouseEnter: () => setActiveIndex(index),
    }),
  };
}

// Hook para focus trapping en modales/dialogs
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
    category: 'Navegación',
    items: [
      { keys: ['↑', '↓'], description: 'Navegar entre resultados' },
      { keys: ['Enter'], description: 'Seleccionar elemento' },
      { keys: ['Esc'], description: 'Cerrar o cancelar' },
      { keys: ['Tab'], description: 'Mover entre elementos' },
    ],
  },
  {
    category: 'Búsqueda',
    items: [
      { keys: ['/'], description: 'Foco en búsqueda' },
      { keys: ['Ctrl', 'K'], description: 'Abrir búsqueda rápida' },
      { keys: ['Ctrl', 'L'], description: 'Limpiar búsqueda' },
    ],
  },
  {
    category: 'Descarga',
    items: [
      { keys: ['Ctrl', 'D'], description: 'Iniciar descarga' },
      { keys: ['Ctrl', 'Shift', 'D'], description: 'Cancelar descarga' },
    ],
  },
  {
    category: 'General',
    items: [
      { keys: ['Ctrl', 'T'], description: 'Cambiar tema' },
      { keys: ['?'], description: 'Mostrar ayuda' },
      { keys: ['Ctrl', '/'], description: 'Este menú' },
    ],
  },
];

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
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
                  <Keyboard className="h-5 w-5 text-primary" weight="regular" />
                </div>
                <div>
                  <h2 id="shortcuts-title" className="text-lg font-semibold text-foreground">
                    Atajos de teclado
                  </h2>
                  <p className="text-xs text-muted-foreground">Navega más rápido con el teclado</p>
                </div>
              </div>
              <motion.button
                onClick={onClose}
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                aria-label="Cerrar"
              >
                <X className="h-5 w-5" weight="regular" />
              </motion.button>
            </div>

            {/* Content */}
            <div className="max-h-[60vh] overflow-y-auto p-6">
              <div className="grid gap-6">
                {shortcutsList.map((category, i) => (
                  <motion.div
                    key={category.category}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                  >
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      {category.category}
                    </h3>
                    <div className="space-y-2">
                      {category.items.map((item, j) => (
                        <motion.div
                          key={j}
                          className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3"
                          whileHover={{ backgroundColor: 'rgba(0,0,0,0.04)' }}
                        >
                          <span className="text-sm text-foreground">{item.description}</span>
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
                Presiona <kbd className="rounded bg-background px-1.5 py-0.5 font-medium">?</kbd> en
                cualquier momento para ver esta ayuda
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Componente para mostrar indicador de focus visible
export function FocusRing({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 rounded-lg',
        className
      )}
    >
      {children}
    </div>
  );
}

// Hook para detectar si el usuario está navegando con teclado
export function useKeyboardNavigation() {
  const [isKeyboardNavigating, setIsKeyboardNavigating] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Tab') {
        setIsKeyboardNavigating(true);
      }
    };

    const handleMouseDown = () => {
      setIsKeyboardNavigating(false);
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleMouseDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, []);

  return isKeyboardNavigating;
}

// Componente para atajos contextuales flotantes
interface FloatingShortcutsProps {
  shortcuts: { keys: string[]; description: string }[];
  className?: string;
}

export function FloatingShortcuts({ shortcuts, className }: FloatingShortcutsProps) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
    }, 5000);

    return () => clearTimeout(timer);
  }, []);

  if (!isVisible) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className={cn(
        'absolute bottom-4 left-1/2 z-40 -translate-x-1/2',
        'rounded-full border border-border bg-card/95 px-4 py-2 shadow-lg backdrop-blur-sm',
        className
      )}
    >
      <div className="flex items-center gap-4">
        {shortcuts.map((shortcut, i) => (
          <div key={i} className="flex items-center gap-2">
            <ShortcutHint keys={shortcut.keys} />
            <span className="text-xs text-muted-foreground">{shortcut.description}</span>
          </div>
        ))}
        <button
          onClick={() => setIsVisible(false)}
          className="ml-2 rounded-full p-1 text-muted-foreground/50 hover:bg-accent hover:text-foreground"
          aria-label="Ocultar atajos"
        >
          <X className="h-3 w-3" weight="bold" />
        </button>
      </div>
    </motion.div>
  );
}
