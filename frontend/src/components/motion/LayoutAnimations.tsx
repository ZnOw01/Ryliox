/**
 * Layout Animations Componentes - Framer Motion 2025-2026
 *
 * Implementa:
 * - LayoutGroup para coordinar múltiples layouts
 * - layout prop para animaciones automáticas de size/position
 * - layout="position" para animaciones de posición únicamente
 * - layoutId para shared layout transitions
 *
 * Basado en: https://context7.com/grx7/framer-motion/llms.txt
 */

import {
  motion,
  LayoutGroup,
  AnimatePresence,
  type Variants,
  type Transition,
} from 'framer-motion';
import { createContext, useContext, useState, type ReactNode, useId } from 'react';

// ============================================
// CONFIGURACIÓN DE LAYOUT ANIMATIONS
// ============================================

export const LAYOUT_ANIMATION_CONFIG = {
  transition: {
    type: 'spring' as const,
    stiffness: 500,
    damping: 30,
    mass: 1,
  } satisfies Transition,
  positionOnlyTransition: {
    type: 'spring' as const,
    stiffness: 600,
    damping: 25,
  } satisfies Transition,
  sharedTransition: {
    type: 'spring' as const,
    stiffness: 400,
    damping: 35,
  } satisfies Transition,
};

// ============================================
// LAYOUT GROUP PROVIDER
// ============================================

interface LayoutGroupContextType {
  groupId: string;
}

const LayoutGroupContext = createContext<LayoutGroupContextType | null>(null);

export function useLayoutGroup() {
  const context = useContext(LayoutGroupContext);
  if (!context) {
    return { groupId: 'default' };
  }
  return context;
}

interface AnimatedLayoutGroupProps {
  children: ReactNode;
  id?: string;
  className?: string;
}

export function AnimatedLayoutGroup({ children, id, className = '' }: AnimatedLayoutGroupProps) {
  const generatedId = useId();
  const groupId = id || generatedId;

  return (
    <LayoutGroup id={groupId}>
      <LayoutGroupContext.Provider value={{ groupId }}>
        <div className={className}>{children}</div>
      </LayoutGroupContext.Provider>
    </LayoutGroup>
  );
}

// ============================================
// LAYOUT ANIMATION COMPONENTS
// ============================================

interface LayoutAnimatedProps {
  children: ReactNode;
  className?: string;
  layoutId?: string;
  /**
   * 'true' - Anima size y position
   * 'position' - Solo anima position (size cambia instantáneamente)
   * 'size' - Solo anima size (position cambia instantáneamente)
   * 'preserve-aspect' - Mantiene aspect ratio durante animación
   */
  layout?: boolean | 'position' | 'size' | 'preserve-aspect';
  transition?: Transition;
}

export function LayoutAnimated({
  children,
  className = '',
  layoutId,
  layout = true,
  transition = LAYOUT_ANIMATION_CONFIG.transition,
}: LayoutAnimatedProps) {
  return (
    <motion.div className={className} layout={layout} layoutId={layoutId} transition={transition}>
      {children}
    </motion.div>
  );
}

interface LayoutPositionAnimatedProps {
  children: ReactNode;
  className?: string;
  layoutId?: string;
}

export function LayoutPositionAnimated({
  children,
  className = '',
  layoutId,
}: LayoutPositionAnimatedProps) {
  return (
    <motion.div
      className={className}
      layout="position"
      layoutId={layoutId}
      transition={LAYOUT_ANIMATION_CONFIG.positionOnlyTransition}
    >
      {children}
    </motion.div>
  );
}

// ============================================
// SHARED LAYOUT TRANSITIONS
// ============================================

interface SharedLayoutItemProps {
  children: ReactNode;
  id: string;
  className?: string;
  onClick?: () => void;
}

export function SharedLayoutItem({ children, id, className = '', onClick }: SharedLayoutItemProps) {
  return (
    <motion.div
      className={className}
      layoutId={id}
      onClick={onClick}
      transition={LAYOUT_ANIMATION_CONFIG.sharedTransition}
      style={{ cursor: onClick ? 'pointer' : undefined }}
    >
      {children}
    </motion.div>
  );
}

interface SharedLayoutTitleProps {
  children: ReactNode;
  id: string;
  className?: string;
}

export function SharedLayoutTitle({ children, id, className = '' }: SharedLayoutTitleProps) {
  return (
    <motion.h2
      className={className}
      layoutId={`title-${id}`}
      transition={LAYOUT_ANIMATION_CONFIG.sharedTransition}
    >
      {children}
    </motion.h2>
  );
}

interface SharedLayoutOverlayProps {
  children: ReactNode;
  id: string;
  isVisible: boolean;
  className?: string;
  onClose?: () => void;
}

export function SharedLayoutOverlay({
  children,
  id,
  isVisible,
  className = '',
  onClose,
}: SharedLayoutOverlayProps) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className={className}
          layoutId={id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={LAYOUT_ANIMATION_CONFIG.sharedTransition}
        >
          {children}
          {onClose && (
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-full p-2 hover:bg-slate-100"
              aria-label="Cerrar"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ============================================
// EXPANDABLE CARD WITH LAYOUT
// ============================================

interface ExpandableCardProps {
  children: ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  className?: string;
  header: ReactNode;
  expandContent: ReactNode;
}

export function ExpandableCard({
  children,
  isExpanded,
  onToggle,
  className = '',
  header,
  expandContent,
}: ExpandableCardProps) {
  return (
    <motion.div
      className={`overflow-hidden rounded-xl border border-slate-200 bg-white ${className}`}
      layout
      onClick={onToggle}
      transition={LAYOUT_ANIMATION_CONFIG.transition}
    >
      <motion.div layout="position" className="p-4">
        {header}
      </motion.div>
      <AnimatePresence mode="popLayout">
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            {expandContent}
          </motion.div>
        )}
      </AnimatePresence>
      <motion.div layout="position">{children}</motion.div>
    </motion.div>
  );
}

// ============================================
// REORDERABLE LIST WITH LAYOUT ANIMATIONS
// ============================================

interface ReorderableItemProps {
  children: ReactNode;
  className?: string;
}

export function ReorderableItem({ children, className = '' }: ReorderableItemProps) {
  return (
    <motion.div
      className={className}
      layout
      layoutId={useId()}
      transition={LAYOUT_ANIMATION_CONFIG.transition}
    >
      {children}
    </motion.div>
  );
}

interface AnimatedListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => ReactNode;
  keyExtractor: (item: T) => string;
  className?: string;
  itemClassName?: string;
}

export function AnimatedList<T>({
  items,
  renderItem,
  keyExtractor,
  className = '',
  itemClassName = '',
}: AnimatedListProps<T>) {
  return (
    <LayoutGroup>
      <div className={className}>
        <AnimatePresence mode="popLayout">
          {items.map((item, index) => (
            <motion.div
              key={keyExtractor(item)}
              layout
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20, transition: { duration: 0.15 } }}
              transition={LAYOUT_ANIMATION_CONFIG.transition}
              className={itemClassName}
            >
              {renderItem(item, index)}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </LayoutGroup>
  );
}

// ============================================
// STAGGERED LAYOUT CONTAINER
// ============================================

const staggerLayoutVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
  exit: {
    opacity: 0,
    transition: {
      staggerChildren: 0.03,
      staggerDirection: -1,
    },
  },
};

const staggerLayoutItemVariants: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring',
      stiffness: 500,
      damping: 28,
    },
  },
  exit: {
    opacity: 0,
    y: -12,
    scale: 0.95,
    transition: { duration: 0.15 },
  },
};

interface StaggeredLayoutContainerProps {
  children: ReactNode;
  className?: string;
}

export function StaggeredLayoutContainer({
  children,
  className = '',
}: StaggeredLayoutContainerProps) {
  return (
    <LayoutGroup>
      <motion.div
        className={className}
        variants={staggerLayoutVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        {children}
      </motion.div>
    </LayoutGroup>
  );
}

interface StaggeredLayoutItemProps {
  children: ReactNode;
  className?: string;
  layoutId?: string;
}

export function StaggeredLayoutItem({
  children,
  className = '',
  layoutId,
}: StaggeredLayoutItemProps) {
  return (
    <motion.div
      className={className}
      layout
      layoutId={layoutId}
      variants={staggerLayoutItemVariants}
    >
      {children}
    </motion.div>
  );
}

// ============================================
// LAYOUT ANIMATION WITH RESIZE OBSERVER
// ============================================

interface AutoLayoutContainerProps {
  children: ReactNode;
  className?: string;
}

export function AutoLayoutContainer({ children, className = '' }: AutoLayoutContainerProps) {
  return (
    <LayoutGroup>
      <motion.div
        className={`will-change-transform ${className}`}
        layout
        transition={LAYOUT_ANIMATION_CONFIG.transition}
      >
        {children}
      </motion.div>
    </LayoutGroup>
  );
}
