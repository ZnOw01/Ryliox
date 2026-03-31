/**
 * Optimized Appear Animations - Framer Motion 2025-2026
 *
 * Implementa startOptimizedAppearAnimation para:
 * - SSR/hydration sin layout shift
 * - Animaciones optimizadas en primera carga
 * - Mejor performance crítica
 *
 * Basado en: https://github.com/grx7/framer-motion/blob/main/dev/html/public/optimized-appear/
 */

import {
  motion,
  startOptimizedAppearAnimation,
  optimizedAppearDataAttribute,
  type Target,
  type Transition,
} from 'framer-motion';
import { useEffect, useRef, useState, useId, useMemo, useCallback, type ReactNode } from 'react';

// ============================================
// CONFIGURACIÓN DE APPEAR ANIMATIONS
// ============================================

export const APPEAR_ANIMATION_CONFIG = {
  duration: {
    fast: 300,
    normal: 500,
    slow: 800,
  },
  ease: {
    linear: 'linear' as 'linear',
    easeIn: 'easeIn' as 'easeIn',
    easeOut: 'easeOut' as 'easeOut',
    easeInOut: 'easeInOut' as 'easeInOut',
  },
};

// ============================================
// TIPOS PARA APPEAR ANIMATIONS
// ============================================

type AnimationProperty = 'opacity' | 'transform' | 'scale' | 'translateX' | 'translateY';

interface AppearAnimationOptions {
  duration?: number;
  ease?: string;
  delay?: number;
}

interface OptimizedAppearProps {
  children: ReactNode;
  className?: string;
  /** Valor inicial de la animación */
  initial: Target;
  /** Valor final de la animación */
  animate: Target;
  /** Duración en milisegundos */
  duration?: number;
  /** Delay en milisegundos */
  delay?: number;
  /** Easing de la animación */
  ease?: 'linear' | 'easeIn' | 'easeOut' | 'easeInOut' | number[];
  /** ID único para el elemento (auto-generado si no se proporciona) */
  id?: string;
}

// ============================================
// OPTIMIZED APPEAR COMPONENT
// ============================================

export function OptimizedAppear({
  children,
  className = '',
  initial,
  animate,
  duration = APPEAR_ANIMATION_CONFIG.duration.normal,
  delay = 0,
  ease = APPEAR_ANIMATION_CONFIG.ease.linear,
  id,
}: OptimizedAppearProps) {
  const elementRef = useRef<HTMLDivElement>(null);
  const generatedId = useId();
  const elementId = id || generatedId;

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    // Iniciar animación optimizada para cada propiedad
    Object.entries(initial).forEach(([property, startValue]) => {
      const endValue = animate[property as keyof typeof animate];
      if (endValue === undefined) return;

      // Preparar valores para WAAPI
      let keyframes: (string | number)[];

      if (property === 'opacity') {
        keyframes = [startValue as number, endValue as number];
      } else if (
        property === 'transform' ||
        property.startsWith('translate') ||
        property === 'scale'
      ) {
        keyframes = [
          typeof startValue === 'number' ? `${property}(${startValue}px)` : String(startValue),
          typeof endValue === 'number' ? `${property}(${endValue}px)` : String(endValue),
        ];
      } else {
        keyframes = [String(startValue), String(endValue)];
      }

      // Iniciar animación optimizada
      startOptimizedAppearAnimation(element, property as AnimationProperty, keyframes as string[], {
        duration,
        ease: (ease || 'linear') as any,
        delay,
      });
    });
  }, [initial, animate, duration, delay, ease]);

  return (
    <motion.div
      ref={elementRef}
      className={className}
      initial={initial}
      animate={animate}
      transition={{ duration: duration / 1000, ease: ease as any, delay: delay / 1000 }}
      {...{ [optimizedAppearDataAttribute]: elementId }}
    >
      {children}
    </motion.div>
  );
}

// ============================================
// OPTIMIZED FADE IN
// ============================================

interface OptimizedFadeInProps {
  children: ReactNode;
  className?: string;
  duration?: number;
  delay?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  distance?: number;
}

export function OptimizedFadeIn({
  children,
  className = '',
  duration = APPEAR_ANIMATION_CONFIG.duration.normal,
  delay = 0,
  direction = 'up',
  distance = 20,
}: OptimizedFadeInProps) {
  const getInitialTransform = useCallback(() => {
    switch (direction) {
      case 'up':
        return { y: distance };
      case 'down':
        return { y: -distance };
      case 'left':
        return { x: distance };
      case 'right':
        return { x: -distance };
      case 'none':
        return {};
    }
  }, [direction, distance]);

  const initial = useMemo(
    () => ({
      opacity: 0,
      ...getInitialTransform(),
    }),
    [getInitialTransform]
  );

  const animate = useMemo(
    () => ({
      opacity: 1,
      x: 0,
      y: 0,
    }),
    []
  );

  return (
    <OptimizedAppear
      className={className}
      initial={initial}
      animate={animate}
      duration={duration}
      delay={delay}
      ease={APPEAR_ANIMATION_CONFIG.ease.easeOut}
    >
      {children}
    </OptimizedAppear>
  );
}

// ============================================
// OPTIMIZED STAGGERED APPEAR
// ============================================

interface OptimizedStaggerContainerProps {
  children: ReactNode;
  className?: string;
  staggerDelay?: number;
  baseDelay?: number;
}

export function OptimizedStaggerContainer({
  children,
  className = '',
  staggerDelay = 50,
  baseDelay = 0,
}: OptimizedStaggerContainerProps) {
  return <div className={className}>{children}</div>;
}

interface OptimizedStaggerItemProps {
  children: ReactNode;
  className?: string;
  index: number;
  staggerDelay?: number;
  baseDelay?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
}

export function OptimizedStaggerItem({
  children,
  className = '',
  index,
  staggerDelay = 50,
  baseDelay = 0,
  direction = 'up',
}: OptimizedStaggerItemProps) {
  const totalDelay = baseDelay + index * staggerDelay;

  return (
    <OptimizedFadeIn
      className={className}
      delay={totalDelay}
      direction={direction}
      duration={APPEAR_ANIMATION_CONFIG.duration.normal}
    >
      {children}
    </OptimizedFadeIn>
  );
}

// ============================================
// OPTIMIZED CARD APPEAR
// ============================================

interface OptimizedCardProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  index?: number;
}

export function OptimizedCard({
  children,
  className = '',
  delay = 0,
  index = 0,
}: OptimizedCardProps) {
  const staggerDelay = index * 80;
  const totalDelay = delay + staggerDelay;

  return (
    <OptimizedAppear
      className={className}
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      duration={APPEAR_ANIMATION_CONFIG.duration.normal}
      delay={totalDelay}
      ease={APPEAR_ANIMATION_CONFIG.ease.easeOut}
    >
      {children}
    </OptimizedAppear>
  );
}

// ============================================
// OPTIMIZED PROGRESS BAR
// ============================================

interface OptimizedProgressBarProps {
  progress: number;
  className?: string;
  isActive?: boolean;
}

export function OptimizedProgressBar({
  progress,
  className = '',
  isActive = false,
}: OptimizedProgressBarProps) {
  const elementRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    // Animación optimizada del width
    startOptimizedAppearAnimation(
      element,
      'transform',
      ['scaleX(0)', `scaleX(${Math.min(100, Math.max(0, progress)) / 100})`],
      {
        duration: APPEAR_ANIMATION_CONFIG.duration.normal,
        ease: 'easeOut',
      }
    );
  }, [progress]);

  return (
    <div
      className={`h-2.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ${className}`}
    >
      <motion.div
        ref={elementRef}
        className={`h-full origin-left bg-brand ${isActive ? 'progress-bar-active' : ''}`}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: Math.min(100, Math.max(0, progress)) / 100 }}
        transition={{
          duration: APPEAR_ANIMATION_CONFIG.duration.normal / 1000,
          ease: 'easeOut',
        }}
        style={{ transformOrigin: 'left' }}
      />
    </div>
  );
}

// ============================================
// HYDRATION SAFE WRAPPER
// ============================================

interface HydrationSafeAppearProps {
  children: ReactNode;
  className?: string;
  fallback?: ReactNode;
}

export function HydrationSafeAppear({
  children,
  className = '',
  fallback = null,
}: HydrationSafeAppearProps) {
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  if (!isHydrated) {
    return (
      <div className={className} style={{ visibility: 'hidden' }}>
        {fallback || children}
      </div>
    );
  }

  return (
    <OptimizedFadeIn
      className={className}
      delay={0}
      direction="none"
      duration={APPEAR_ANIMATION_CONFIG.duration.fast}
    >
      {children}
    </OptimizedFadeIn>
  );
}

// ============================================
// PAGE TRANSITION WITH OPTIMIZED APPEAR
// ============================================

interface OptimizedPageTransitionProps {
  children: ReactNode;
  className?: string;
  isVisible: boolean;
}

export function OptimizedPageTransition({
  children,
  className = '',
  isVisible,
}: OptimizedPageTransitionProps) {
  const [hasAppeared, setHasAppeared] = useState(false);

  useEffect(() => {
    if (isVisible && !hasAppeared) {
      setHasAppeared(true);
    }
  }, [isVisible, hasAppeared]);

  if (!isVisible && !hasAppeared) return null;

  return (
    <OptimizedAppear
      className={className}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      duration={APPEAR_ANIMATION_CONFIG.duration.normal}
      delay={0}
      ease={APPEAR_ANIMATION_CONFIG.ease.easeOut}
    >
      {children}
    </OptimizedAppear>
  );
}
