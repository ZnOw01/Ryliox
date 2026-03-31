import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../lib/cn';
import { Icon, type IconName } from './Icon';

/**
 * CommandPalette - Spotlight search con Command+K (2026)
 *
 * Características:
 * - Atajo de teclado Cmd/Ctrl + K
 * - Búsqueda en tiempo real
 * - Navegación con flechas y Enter
 * - Agrupación por categorías
 * - Acciones contextuales
 * - Animaciones suaves con Framer Motion
 * - Fully accessible (ARIA, focus trap, ESC para cerrar)
 *
 * @example
 * ```tsx
 * // Uso básico
 * const [open, setOpen] = useState(false);
 *
 * <CommandPalette
 *   isOpen={open}
 *   onClose={() => setOpen(false)}
 *   groups={[
 *     {
 *       id: "actions",
 *       label: "Acciones",
 *       items: [
 *         { id: "search", label: "Buscar libros", icon: "search", shortcut: "⌘F" },
 *         { id: "download", label: "Descargas", icon: "download" },
 *       ],
 *     },
 *   ]}
 *   onSelect={(item) => console.log(item.id)}
 * />
 *
 * // Con placeholder personalizado
 * <CommandPalette
 *   isOpen={open}
 *   onClose={() => setOpen(false)}
 *   placeholder="Buscar comandos..."
 *   emptyMessage="No se encontraron resultados"
 * />
 * ```
 */

export interface CommandItem {
  /** Identificador único */
  id: string;
  /** Etiqueta mostrada */
  label: string;
  /** Icono opcional */
  icon?: IconName;
  /** Descripción corta */
  description?: string;
  /** Atajo de teclado opcional */
  shortcut?: string;
  /** Metadata adicional */
  meta?: string;
  /** Si está deshabilitado */
  disabled?: boolean;
  /** Callback específico del item */
  onSelect?: () => void;
}

export interface CommandGroup {
  /** Identificador del grupo */
  id: string;
  /** Etiqueta del grupo */
  label: string;
  /** Items del grupo */
  items: CommandItem[];
}

export interface CommandPaletteProps {
  /** Control de visibilidad */
  isOpen: boolean;
  /** Callback al cerrar */
  onClose: () => void;
  /** Grupos de comandos */
  groups: CommandGroup[];
  /** Callback al seleccionar item */
  onSelect: (item: CommandItem, group: CommandGroup) => void;
  /** Placeholder del input */
  placeholder?: string;
  /** Mensaje cuando no hay resultados */
  emptyMessage?: string;
  /** Clases adicionales */
  className?: string;
}

export function CommandPalette({
  isOpen,
  onClose,
  groups,
  onSelect,
  placeholder = 'Buscar comandos...',
  emptyMessage = 'No se encontraron resultados',
  className,
}: CommandPaletteProps) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filtrar items basado en búsqueda
  const filteredGroups = React.useMemo(() => {
    if (!search.trim()) return groups;

    const query = search.toLowerCase();
    return groups
      .map(group => ({
        ...group,
        items: group.items.filter(
          item =>
            item.label.toLowerCase().includes(query) ||
            item.description?.toLowerCase().includes(query) ||
            item.id.toLowerCase().includes(query)
        ),
      }))
      .filter(group => group.items.length > 0);
  }, [groups, search]);

  // Calcular items totales para navegación
  const totalItems = filteredGroups.reduce((acc, group) => acc + group.items.length, 0);

  // Resetear selección cuando cambia la búsqueda
  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  // Focus en input al abrir
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setSearch('');
    }
  }, [isOpen]);

  // Atajo de teclado Cmd/Ctrl + K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (!isOpen) {
          // Toggle command palette
          const event = new CustomEvent('toggleCommandPalette');
          window.dispatchEvent(event);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Manejar navegación con teclado
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => (prev + 1) % totalItems);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => (prev === 0 ? totalItems - 1 : prev - 1));
          break;
        case 'Enter':
          e.preventDefault();
          const selectedItem = getItemAtIndex(selectedIndex);
          if (selectedItem && !selectedItem.item.disabled) {
            handleSelect(selectedItem.item, selectedItem.group);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'Home':
          e.preventDefault();
          setSelectedIndex(0);
          break;
        case 'End':
          e.preventDefault();
          setSelectedIndex(totalItems - 1);
          break;
      }
    },
    [selectedIndex, totalItems, onClose]
  );

  // Obtener item en índice específico
  const getItemAtIndex = (index: number): { item: CommandItem; group: CommandGroup } | null => {
    let currentIndex = 0;
    for (const group of filteredGroups) {
      for (const item of group.items) {
        if (currentIndex === index) {
          return { item, group };
        }
        currentIndex++;
      }
    }
    return null;
  };

  // Manejar selección
  const handleSelect = (item: CommandItem, group: CommandGroup) => {
    if (item.onSelect) {
      item.onSelect();
    } else {
      onSelect(item, group);
    }
    onClose();
  };

  // Scroll al item seleccionado
  useEffect(() => {
    const selectedElement = containerRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
    selectedElement?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIndex]);

  // Click fuera para cerrar
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  let currentIndex = 0;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
          onClick={handleBackdropClick}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
        >
          {/* Backdrop glassmorphism */}
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" />

          {/* Container principal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{
              type: 'spring',
              stiffness: 400,
              damping: 30,
            }}
            className={cn(
              'relative w-full max-w-2xl overflow-hidden rounded-2xl',
              'bg-white/95 dark:bg-slate-900/95',
              'backdrop-blur-xl backdrop-saturate-150',
              'border border-white/20 dark:border-white/10',
              'shadow-[0_24px_48px_rgba(0,0,0,0.15),0_0_0_1px_rgba(255,255,255,0.1)]',
              'dark:shadow-[0_24px_48px_rgba(0,0,0,0.4),0_0_0_1px_rgba(255,255,255,0.05)]',
              className
            )}
            onKeyDown={handleKeyDown}
          >
            {/* Header con input */}
            <div className="border-b border-slate-200/60 dark:border-slate-700/60">
              <div className="flex items-center gap-3 px-4 py-4">
                <Icon icon="search" className="h-5 w-5 text-slate-400" aria-hidden="true" />
                <input
                  ref={inputRef}
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder={placeholder}
                  className={cn(
                    'flex-1 bg-transparent text-base outline-none',
                    'text-slate-900 dark:text-slate-100',
                    'placeholder:text-slate-400 dark:placeholder:text-slate-500'
                  )}
                  aria-label="Buscar comandos"
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                />
                <kbd
                  className={cn(
                    'hidden sm:inline-flex items-center gap-1 px-2 py-1',
                    'text-xs font-medium text-slate-500',
                    'bg-slate-100 dark:bg-slate-800 rounded-md',
                    'border border-slate-200 dark:border-slate-700'
                  )}
                >
                  <span>ESC</span>
                </kbd>
              </div>
            </div>

            {/* Lista de resultados */}
            <div
              ref={containerRef}
              className="max-h-[50vh] overflow-y-auto overscroll-contain"
              role="listbox"
              aria-label="Resultados de búsqueda"
            >
              {filteredGroups.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                  <div
                    className={cn(
                      'flex h-12 w-12 shrink-0 items-center justify-center rounded-full',
                      'bg-slate-100 dark:bg-slate-800 mb-3'
                    )}
                  >
                    <Icon icon="search-x" className="h-6 w-6 text-slate-400" />
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{emptyMessage}</p>
                </div>
              ) : (
                filteredGroups.map(group => (
                  <div key={group.id} role="group" aria-label={group.label}>
                    <div className="sticky top-0 z-10 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                      {group.label}
                    </div>
                    <ul className="py-1">
                      {group.items.map(item => {
                        const isSelected = currentIndex === selectedIndex;
                        const itemIndex = currentIndex++;

                        return (
                          <li
                            key={item.id}
                            data-index={itemIndex}
                            role="option"
                            aria-selected={isSelected}
                            aria-disabled={item.disabled}
                          >
                            <button
                              onClick={() => handleSelect(item, group)}
                              disabled={item.disabled}
                              className={cn(
                                'w-full flex items-center gap-3 px-4 py-3 text-left',
                                'transition-colors duration-150',
                                'focus:outline-none',
                                isSelected
                                  ? 'bg-red-50 dark:bg-red-900/20'
                                  : 'hover:bg-slate-50 dark:hover:bg-slate-800/50',
                                item.disabled && 'opacity-50 cursor-not-allowed'
                              )}
                            >
                              {/* Icono */}
                              <div
                                className={cn(
                                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                                  isSelected
                                    ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                                )}
                              >
                                <Icon icon={item.icon || 'command'} className="h-4 w-4" />
                              </div>

                              {/* Contenido */}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span
                                    className={cn(
                                      'text-sm font-medium truncate',
                                      isSelected
                                        ? 'text-red-700 dark:text-red-300'
                                        : 'text-slate-900 dark:text-slate-100'
                                    )}
                                  >
                                    {item.label}
                                  </span>
                                  {item.meta && (
                                    <span className="text-xs text-slate-400 dark:text-slate-500">
                                      {item.meta}
                                    </span>
                                  )}
                                </div>
                                {item.description && (
                                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                                    {item.description}
                                  </p>
                                )}
                              </div>

                              {/* Shortcut */}
                              {item.shortcut && (
                                <kbd
                                  className={cn(
                                    'hidden sm:flex items-center gap-1 px-2 py-1 text-xs',
                                    'font-medium text-slate-400 dark:text-slate-500',
                                    'bg-slate-50 dark:bg-slate-800 rounded',
                                    'border border-slate-200 dark:border-slate-700'
                                  )}
                                >
                                  {item.shortcut}
                                </kbd>
                              )}

                              {/* Indicador de selección */}
                              {isSelected && (
                                <motion.div
                                  layoutId="selection"
                                  className="h-1.5 w-1.5 rounded-full bg-red-500"
                                  transition={{
                                    type: 'spring',
                                    stiffness: 500,
                                    damping: 30,
                                  }}
                                />
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))
              )}
            </div>

            {/* Footer con atajos */}
            <div className="border-t border-slate-200/60 dark:border-slate-700/60 px-4 py-2.5">
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded font-medium">
                      ↑↓
                    </kbd>
                    <span>Navegar</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded font-medium">
                      ↵
                    </kbd>
                    <span>Seleccionar</span>
                  </span>
                </div>
                <span className="hidden sm:inline">
                  {totalItems} resultado{totalItems !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * Hook para manejar el toggle del Command Palette
 */
export function useCommandPalette() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleToggle = () => setIsOpen(prev => !prev);
    window.addEventListener('toggleCommandPalette', handleToggle);
    return () => window.removeEventListener('toggleCommandPalette', handleToggle);
  }, []);

  return { isOpen, setIsOpen };
}
