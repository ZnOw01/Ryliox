/**
 * useMotionGestures Hook - Framer Motion 2025-2026
 *
 * Hooks avanzados para:
 * - useMotionValue + useTransform
 * - Scroll-based animations
 * - Drag gestures con velocity tracking
 * - Gesture composition
 *
 * Basado en: https://context7.com/grx7/framer-motion/llms.txt
 */

import { useEffect, useRef, useState, useCallback, type RefObject } from 'react';
import {
  useMotionValue,
  useTransform,
  useScroll,
  useVelocity,
  useSpring,
  useDragControls,
  animate,
  scroll,
  type MotionValue,
  type Transition,
} from 'framer-motion';

// ============================================
// TIPOS
// ============================================

interface DragInfo {
  point: { x: number; y: number };
  delta: { x: number; y: number };
  velocity: { x: number; y: number };
  offset: { x: number; y: number };
}

interface ScrollInfo {
  scrollY: MotionValue<number>;
  scrollYProgress: MotionValue<number>;
  scrollX: MotionValue<number>;
  scrollXProgress: MotionValue<number>;
}

interface TransformRange<T> {
  input: number[];
  output: T[];
  options?: { ease?: number[]; clamp?: boolean };
}

// ============================================
// HOOK PARA DRAG CON VELOCITY
// ============================================

interface UseDragVelocityOptions {
  axis?: 'x' | 'y' | 'both';
  constraints?: { left?: number; right?: number; top?: number; bottom?: number };
  elastic?: number;
  momentum?: boolean;
  snapToOrigin?: boolean;
}

interface UseDragVelocityResult {
  x: MotionValue<number>;
  y: MotionValue<number>;
  velocityX: number;
  velocityY: number;
  isDragging: boolean;
  dragControls: ReturnType<typeof useDragControls>;
  onDragStart: () => void;
  onDragEnd: () => void;
}

export function useDragVelocity(options: UseDragVelocityOptions = {}): UseDragVelocityResult {
  const {
    axis = 'both',
    constraints,
    elastic = 0.2,
    momentum = true,
    snapToOrigin = false,
  } = options;

  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragControls = useDragControls();

  const velocityXMotion = useVelocity(x);
  const velocityYMot = useVelocity(y);

  // Convertir MotionValues a números para el retorno
  const [velocityX, setVelocityX] = useState(0);
  const [velocityY, setVelocityY] = useState(0);

  useEffect(() => {
    const unsubX = velocityXMotion.on('change', v => setVelocityX(v));
    const unsubY = velocityYMot.on('change', v => setVelocityY(v));
    return () => {
      unsubX();
      unsubY();
    };
  }, [velocityXMotion, velocityYMot]);

  const onDragStart = useCallback(() => {
    setIsDragging(true);
  }, []);

  const onDragEnd = useCallback(() => {
    setIsDragging(false);
  }, []);

  return {
    x,
    y,
    velocityX,
    velocityY,
    isDragging,
    dragControls,
    onDragStart,
    onDragEnd,
  };
}

// ============================================
// HOOK PARA SCROLL ANIMATIONS
// ============================================

interface UseScrollAnimationOptions {
  /** Elemento objetivo para scroll tracking */
  target?: RefObject<HTMLElement | null>;
  /** Contenedor del scroll */
  container?: RefObject<HTMLElement | null>;
  /** Offset personalizado - use valores válidos como ['start end', 'end start'] */
  offset?: [string, string];
}

interface UseScrollAnimationResult extends ScrollInfo {
  /** Crear transformación basada en scroll progress */
  createTransform: <T>(inputRange: number[], outputRange: T[]) => MotionValue<T>;
  /** Scroll progress normalizado (0-1) */
  getProgress: () => number;
}

export function useScrollAnimation(
  options: UseScrollAnimationOptions = {}
): UseScrollAnimationResult {
  const { target, container, offset = ['start end', 'end start'] as const } = options;

  const scrollConfig: Record<string, unknown> = { offset };
  if (target) scrollConfig.target = target;
  if (container) scrollConfig.container = container;

  const { scrollY, scrollYProgress, scrollX, scrollXProgress } = useScroll(
    scrollConfig as Parameters<typeof useScroll>[0]
  );

  // Wrapper para crear transformaciones basadas en scroll
  const createTransform = useCallback(
    <T>(inputRange: number[], outputRange: T[]): MotionValue<T> => {
      return useTransform(scrollYProgress, inputRange, outputRange);
    },
    [scrollYProgress]
  );

  // Obtener progreso actual
  const getProgress = useCallback(() => {
    return scrollYProgress.get();
  }, [scrollYProgress]);

  return {
    scrollY,
    scrollYProgress,
    scrollX,
    scrollXProgress,
    createTransform,
    getProgress,
  };
}

// ============================================
// HOOK PARA ELEMENT IN VIEW
// ============================================

interface UseElementInViewOptions {
  /** Threshold para considerar el elemento visible (0-1) */
  threshold?: number;
  /** Offset del viewport - use valores válidos como ['start end', 'end start'] */
  offset?: [string, string];
}

interface UseElementInViewResult {
  ref: RefObject<HTMLElement | null>;
  isInView: boolean;
  progress: MotionValue<number>;
  opacity: MotionValue<number>;
  y: MotionValue<number>;
}

export function useElementInView(options: UseElementInViewOptions = {}): UseElementInViewResult {
  const { threshold = 0.2, offset = ['start end', 'end start'] as const } = options;
  const ref = useRef<HTMLElement>(null);
  const [isInView, setIsInView] = useState(false);

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: offset as any,
  });

  const progress = useTransform(scrollYProgress, [0, threshold, 1 - threshold, 1], [0, 1, 1, 0]);

  const opacity = useTransform(scrollYProgress, [0, threshold, 1 - threshold, 1], [0, 1, 1, 0]);

  const y = useTransform(scrollYProgress, [0, threshold, 1 - threshold, 1], [50, 0, 0, -50]);

  useEffect(() => {
    const unsubscribe = scrollYProgress.on('change', latest => {
      setIsInView(latest >= threshold && latest <= 1 - threshold);
    });
    return () => unsubscribe();
  }, [scrollYProgress, threshold]);

  return {
    ref: ref as RefObject<HTMLElement | null>,
    isInView,
    progress,
    opacity,
    y,
  };
}

// ============================================
// HOOK PARA PROGRESS BAR
// ============================================

interface UseProgressBarResult {
  ref: RefObject<HTMLElement | null>;
  scaleX: MotionValue<number>;
  progress: number;
}

export function useProgressBar(): UseProgressBarResult {
  const { scrollYProgress } = useScroll();
  const [progress, setProgress] = useState(0);

  const scaleX = useTransform(scrollYProgress, [0, 1], [0, 1]);

  useEffect(() => {
    const unsubscribe = scrollYProgress.on('change', latest => {
      setProgress(Math.round(latest * 100));
    });
    return () => unsubscribe();
  }, [scrollYProgress]);

  return {
    ref: useRef<HTMLElement>(null),
    scaleX,
    progress,
  };
}

// ============================================
// HOOK PARA MAGNETIC EFFECT
// ============================================

interface UseMagneticOptions {
  strength?: number;
  radius?: number;
}

interface UseMagneticResult {
  x: MotionValue<number>;
  y: MotionValue<number>;
  onMouseMove: (event: React.MouseEvent) => void;
  onMouseLeave: () => void;
}

export function useMagnetic(options: UseMagneticOptions = {}): UseMagneticResult {
  const { strength = 0.3, radius = 100 } = options;
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const elementRef = useRef<DOMRect | null>(null);

  const onMouseMove = useCallback(
    (event: React.MouseEvent) => {
      const rect =
        elementRef.current || (event.currentTarget as HTMLElement).getBoundingClientRect();
      elementRef.current = rect;

      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const distanceX = event.clientX - centerX;
      const distanceY = event.clientY - centerY;

      // Solo afectar si está dentro del radio
      const distance = Math.sqrt(distanceX ** 2 + distanceY ** 2);
      if (distance < radius) {
        const factor = (radius - distance) / radius;
        x.set(distanceX * strength * factor);
        y.set(distanceY * strength * factor);
      }
    },
    [strength, radius, x, y]
  );

  const onMouseLeave = useCallback(() => {
    x.set(0);
    y.set(0);
    elementRef.current = null;
  }, [x, y]);

  return {
    x,
    y,
    onMouseMove,
    onMouseLeave,
  };
}

// ============================================
// HOOK PARA PARALLAX
// ============================================

interface UseParallaxOptions {
  speed?: number;
  offset?: [string, string];
}

interface UseParallaxResult {
  ref: RefObject<HTMLElement | null>;
  y: MotionValue<number>;
}

export function useParallax(options: UseParallaxOptions = {}): UseParallaxResult {
  const { speed = 0.5, offset = ['start end', 'end start'] as const } = options;
  const ref = useRef<HTMLElement>(null);

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: offset as any,
  });

  const y = useTransform(scrollYProgress, [0, 1], [0, 100 * speed]);

  return {
    ref: ref as RefObject<HTMLElement | null>,
    y,
  };
}

// ============================================
// HOOK PARA SWIPE
// ============================================

interface UseSwipeOptions {
  threshold?: number;
  velocityThreshold?: number;
}

interface UseSwipeResult {
  x: MotionValue<number>;
  rotate: MotionValue<number>;
  opacity: MotionValue<number>;
  onDragEnd: (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => void;
  isSwiped: boolean;
  reset: () => void;
}

export function useSwipe(
  onSwipe: (direction: 'left' | 'right' | 'up') => void,
  options: UseSwipeOptions = {}
): UseSwipeResult {
  const { threshold = 100, velocityThreshold = 500 } = options;
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const [isSwiped, setIsSwiped] = useState(false);

  const rotate = useTransform(x, [-200, 200], [-30, 30]);
  const opacity = useTransform(
    x,
    [-threshold - 50, -threshold, threshold, threshold + 50],
    [0, 1, 1, 0]
  );

  const onDragEnd = useCallback(
    (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => {
      const velocity = Math.abs(info.velocity.x);
      const offset = Math.abs(info.offset.x);

      if (offset > threshold || velocity > velocityThreshold) {
        setIsSwiped(true);
        if (info.offset.x > 0) {
          onSwipe('right');
        } else {
          onSwipe('left');
        }
      } else if (info.offset.y < -threshold) {
        setIsSwiped(true);
        onSwipe('up');
      }
    },
    [onSwipe, threshold, velocityThreshold]
  );

  const reset = useCallback(() => {
    x.set(0);
    y.set(0);
    setIsSwiped(false);
  }, [x, y]);

  return {
    x,
    rotate,
    opacity,
    onDragEnd,
    isSwiped,
    reset,
  };
}

// ============================================
// HOOK PARA GESTURE COMPOSITION
// ============================================

interface UseGestureCompositionResult {
  x: MotionValue<number>;
  y: MotionValue<number>;
  scale: MotionValue<number>;
  rotate: MotionValue<number>;
  opacity: MotionValue<number>;
  backgroundColor: MotionValue<string>;
}

export function useGestureComposition(
  xRange: [number, number] = [-200, 200],
  colorRange: [string, string, string] = ['#ff008c', '#7700ff', '#00d5ff']
): UseGestureCompositionResult {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const scale = useTransform([x, y], ([latestX, latestY]) => {
    const distance = Math.sqrt((latestX as number) ** 2 + (latestY as number) ** 2);
    return 1 - distance / 1000;
  });

  const rotate = useTransform(x, xRange, [-45, 45]);
  const opacity = useTransform(x, [xRange[0], 0, xRange[1]], [0.3, 1, 0.3]);
  const backgroundColor = useTransform(x, xRange, colorRange);

  return {
    x,
    y,
    scale,
    rotate,
    opacity,
    backgroundColor,
  };
}

// ============================================
// HOOK PARA SPRING PHYSICS
// ============================================

interface UseSpringPhysicsOptions {
  stiffness?: number;
  damping?: number;
  mass?: number;
}

export function useSpringPhysics(
  targetValue: MotionValue<number>,
  options: UseSpringPhysicsOptions = {}
): MotionValue<number> {
  const { stiffness = 100, damping = 10, mass = 1 } = options;

  return useSpring(targetValue, {
    stiffness,
    damping,
    mass,
  });
}
