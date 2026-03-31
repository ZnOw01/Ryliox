/**
 * useOptimizedAppear Hook - Framer Motion 2025-2026
 *
 * Hook para animaciones de aparición optimizadas:
 * - SSR-safe hydration
 * - startOptimizedAppearAnimation API
 * - Layout shift prevention
 * - Critical performance optimization
 *
 * Basado en: https://github.com/grx7/framer-motion/blob/main/dev/html/public/optimized-appear/
 */

import { useEffect, useRef, useState, useCallback, type RefObject } from 'react';
import {
  startOptimizedAppearAnimation,
  optimizedAppearDataAttribute,
  type Target,
} from 'framer-motion';

// ============================================
// TIPOS
// ============================================

type AnimationProperty = 'opacity' | 'transform' | 'scale' | 'translateX' | 'translateY' | 'rotate';

interface OptimizedAppearOptions {
  /** Duración en milisegundos */
  duration?: number;
  /** Easing de la animación */
  ease?: 'linear' | 'easeIn' | 'easeOut' | 'easeInOut' | number[];
  /** Delay en milisegundos */
  delay?: number;
}

interface UseOptimizedAppearResult {
  ref: RefObject<HTMLElement | null>;
  isAnimating: boolean;
  isComplete: boolean;
  startAnimation: () => void;
  stopAnimation: () => void;
}

// ============================================
// HOOK PRINCIPAL
// ============================================

export function useOptimizedAppear(
  property: AnimationProperty,
  keyframes: (string | number)[],
  options: OptimizedAppearOptions = {}
): UseOptimizedAppearResult {
  const ref = useRef<HTMLElement>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const animationRef = useRef<Animation | null>(null);

  const startAnimation = useCallback(() => {
    const element = ref.current;
    if (!element || isAnimating) return;

    setIsAnimating(true);
    setIsComplete(false);

    const { duration = 500, ease = 'easeOut', delay = 0 } = options;

    // Iniciar animación optimizada
    startOptimizedAppearAnimation(
      element,
      property,
      keyframes as string[],
      {
        duration,
        ease: (ease || 'easeOut') as any,
        delay,
      },
      anim => {
        if (anim) {
          animationRef.current = anim;

          // Detectar finalización
          anim.onfinish = () => {
            setIsAnimating(false);
            setIsComplete(true);
          };
        }
      }
    );
  }, [property, keyframes, options, isAnimating]);

  const stopAnimation = useCallback(() => {
    if (animationRef.current) {
      animationRef.current.cancel();
      animationRef.current = null;
    }
    setIsAnimating(false);
  }, []);

  // Auto-start en mount si no hay delay
  useEffect(() => {
    if (options.delay === 0) {
      // Pequeño delay para asegurar que el DOM esté listo
      const timer = setTimeout(startAnimation, 16);
      return () => clearTimeout(timer);
    }
  }, [startAnimation, options.delay]);

  return {
    ref: ref as RefObject<HTMLElement | null>,
    isAnimating,
    isComplete,
    startAnimation,
    stopAnimation,
  };
}

// ============================================
// HOOK PARA MULTIPLES PROPIEDADES
// ============================================

interface MultiPropertyAnimation {
  property: AnimationProperty;
  keyframes: (string | number)[];
}

export function useOptimizedAppearMulti(
  animations: MultiPropertyAnimation[],
  options: OptimizedAppearOptions = {}
): UseOptimizedAppearResult {
  const ref = useRef<HTMLElement>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const animationsRef = useRef<Animation[]>([]);

  const startAnimation = useCallback(() => {
    const element = ref.current;
    if (!element || isAnimating) return;

    setIsAnimating(true);
    setIsComplete(false);
    animationsRef.current = [];

    const { duration = 500, ease = 'easeOut', delay = 0 } = options;
    let completedCount = 0;

    animations.forEach(({ property, keyframes }) => {
      startOptimizedAppearAnimation(
        element,
        property,
        keyframes as string[],
        {
          duration,
          ease: (ease || 'easeOut') as any,
          delay,
        },
        anim => {
          if (anim) {
            animationsRef.current.push(anim);
            anim.onfinish = () => {
              completedCount++;
              if (completedCount >= animations.length) {
                setIsAnimating(false);
                setIsComplete(true);
              }
            };
          }
        }
      );
    });
  }, [animations, options, isAnimating]);

  const stopAnimation = useCallback(() => {
    animationsRef.current.forEach(anim => anim?.cancel());
    animationsRef.current = [];
    setIsAnimating(false);
  }, []);

  useEffect(() => {
    if (options.delay === 0) {
      const timer = setTimeout(startAnimation, 16);
      return () => clearTimeout(timer);
    }
  }, [startAnimation, options.delay]);

  return {
    ref: ref as RefObject<HTMLElement | null>,
    isAnimating,
    isComplete,
    startAnimation,
    stopAnimation,
  };
}

// ============================================
// HOOK PARA HYDRATION SSR
// ============================================

interface HydrationAppearOptions extends OptimizedAppearOptions {
  /** ID único para el elemento */
  elementId?: string;
  /** Si debe animar en hydratation */
  animateOnHydrate?: boolean;
}

interface UseHydrationAppearResult extends UseOptimizedAppearResult {
  isHydrated: boolean;
  dataAttribute: Record<string, string>;
}

export function useHydrationAppear(
  property: AnimationProperty,
  keyframes: (string | number)[],
  options: HydrationAppearOptions = {}
): UseHydrationAppearResult {
  const [isHydrated, setIsHydrated] = useState(false);
  const elementId = options.elementId || `hydration-${Math.random().toString(36).slice(2, 11)}`;

  const { ref, isAnimating, isComplete, startAnimation, stopAnimation } = useOptimizedAppear(
    property,
    keyframes,
    {
      ...options,
      delay: options.animateOnHydrate ? 0 : options.delay,
    }
  );

  useEffect(() => {
    // Detectar si estamos en cliente (hydratation completada)
    if (typeof window !== 'undefined') {
      setIsHydrated(true);

      if (options.animateOnHydrate) {
        // Pequeño delay para asegurar que React haya hidratado
        const timer = setTimeout(() => {
          startAnimation();
        }, 50);
        return () => clearTimeout(timer);
      }
    }
  }, [options.animateOnHydrate, startAnimation]);

  const dataAttribute = {
    [optimizedAppearDataAttribute]: elementId,
  };

  return {
    ref,
    isAnimating,
    isComplete,
    isHydrated,
    startAnimation,
    stopAnimation,
    dataAttribute,
  };
}

// ============================================
// HOOK PARA FADE IN OPTIMIZADO
// ============================================

interface UseOptimizedFadeInOptions {
  duration?: number;
  delay?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  distance?: number;
}

export function useOptimizedFadeIn(
  options: UseOptimizedFadeInOptions = {}
): UseOptimizedAppearResult {
  const { duration = 500, delay = 0, direction = 'up', distance = 20 } = options;

  let keyframes: (string | number)[];
  let transformKeyframes: string[] | undefined;

  switch (direction) {
    case 'up':
      keyframes = [0, 1];
      transformKeyframes = [`translateY(${distance}px)`, 'translateY(0)'];
      break;
    case 'down':
      keyframes = [0, 1];
      transformKeyframes = [`translateY(-${distance}px)`, 'translateY(0)'];
      break;
    case 'left':
      keyframes = [0, 1];
      transformKeyframes = [`translateX(${distance}px)`, 'translateX(0)'];
      break;
    case 'right':
      keyframes = [0, 1];
      transformKeyframes = [`translateX(-${distance}px)`, 'translateX(0)'];
      break;
    case 'none':
    default:
      keyframes = [0, 1];
      transformKeyframes = undefined;
  }

  // Usar multi-property si hay transform
  if (transformKeyframes) {
    return useOptimizedAppearMulti(
      [
        { property: 'opacity', keyframes },
        { property: 'transform', keyframes: transformKeyframes },
      ],
      { duration, delay, ease: 'easeOut' }
    );
  }

  return useOptimizedAppear('opacity', keyframes, { duration, delay, ease: 'easeOut' });
}

// ============================================
// HOOK PARA STAGGER APPEAR
// ============================================

interface StaggerItem {
  id: string;
  delay: number;
}

export function useOptimizedStagger(
  itemCount: number,
  baseDelay: number = 0,
  staggerDelay: number = 50,
  options: OptimizedAppearOptions = {}
): {
  items: StaggerItem[];
  getItemProps: (index: number) => { delay: number; id: string };
} {
  const items: StaggerItem[] = Array.from({ length: itemCount }, (_, i) => ({
    id: `stagger-${i}-${Math.random().toString(36).slice(2, 7)}`,
    delay: baseDelay + i * staggerDelay,
  }));

  const getItemProps = useCallback(
    (index: number) => ({
      delay: items[index]?.delay ?? 0,
      id: items[index]?.id ?? `stagger-${index}`,
    }),
    [items]
  );

  return { items, getItemProps };
}
