/**
 * Gestures y Motion Values Avanzados - Framer Motion 2025-2026
 *
 * Implementa:
 * - useMotionValue + useTransform para efectos complejos
 * - Scroll-based animations con useScroll
 * - Drag gestures mejorados con velocity tracking
 * - Scroll-linked animations con scroll()
 *
 * Basado en: https://context7.com/grx7/framer-motion/llms.txt
 */

import {
  motion,
  useMotionValue,
  useTransform,
  useScroll,
  useDragControls,
  animate,
  scroll,
  type MotionValue,
  type Transition,
} from 'framer-motion';
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';

// ============================================
// TIPOS PARA GESTURES
// ============================================

interface DragInfo {
  point: { x: number; y: number };
  delta: { x: number; y: number };
  velocity: { x: number; y: number };
  offset: { x: number; y: number };
}

// ============================================
// DRAG GESTURE COMPONENTS
// ============================================

interface DraggableProps {
  children: ReactNode;
  className?: string;
  /** 'x' | 'y' | true */
  axis?: 'x' | 'y' | boolean;
  /** Restricciones de píxeles */
  constraints?: {
    top?: number;
    bottom?: number;
    left?: number;
    right?: number;
  };
  /** Elemento padre para restricciones */
  constraintsRef?: RefObject<HTMLElement | null>;
  /** Elasticidad de los límites (0-1) */
  elastic?: number;
  /** Si debe tener momentum */
  momentum?: boolean;
  /** Volver al origen al soltar */
  snapToOrigin?: boolean;
  /** Callbacks */
  onDragStart?: (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => void;
  onDrag?: (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => void;
  onDragEnd?: (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => void;
}

export function Draggable({
  children,
  className = '',
  axis = true,
  constraints,
  constraintsRef,
  elastic = 0.2,
  momentum = true,
  snapToOrigin = false,
  onDragStart,
  onDrag,
  onDragEnd,
}: DraggableProps) {
  return (
    <motion.div
      className={`cursor-grab active:cursor-grabbing ${className}`}
      drag={axis}
      dragConstraints={constraintsRef || constraints}
      dragElastic={elastic}
      dragMomentum={momentum}
      dragSnapToOrigin={snapToOrigin}
      whileDrag={{ scale: 1.05, cursor: 'grabbing' }}
      onDragStart={onDragStart}
      onDrag={onDrag}
      onDragEnd={onDragEnd}
    >
      {children}
    </motion.div>
  );
}

// ============================================
// DRAG WITH MOTION VALUES
// ============================================

interface DragWithMotionValuesProps {
  children: ReactNode;
  className?: string;
  /** Rango de movimiento en X */
  xRange?: [number, number];
  /** Transformaciones basadas en X */
  transformRange?: {
    opacity?: [number, number, number];
    scale?: [number, number, number];
    rotate?: [number, number];
    backgroundColor?: [string, string, string];
  };
}

export function DragWithMotionValues({
  children,
  className = '',
  xRange = [-200, 200],
  transformRange = {
    opacity: [0, 1, 0],
    rotate: [-45, 45],
  },
}: DragWithMotionValuesProps) {
  const x = useMotionValue(0);
  const [minX, maxX] = xRange;

  // Transformaciones basadas en el valor de X
  const opacity = useTransform(x, [minX, 0, maxX], transformRange.opacity || [0.3, 1, 0.3]);

  const rotate = useTransform(x, [minX, maxX], transformRange.rotate || [-15, 15]);

  const scale = transformRange.scale
    ? useTransform(x, [minX, 0, maxX], transformRange.scale)
    : useMotionValue(1);

  const background = transformRange.backgroundColor
    ? useTransform(x, [minX, 0, maxX], transformRange.backgroundColor)
    : useMotionValue('transparent');

  // Tracking de velocidad
  const [velocity, setVelocity] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const unsubscribe = x.on('change', latest => {
      const velocity = x.getVelocity();
      setVelocity({ x: velocity, y: 0 });
    });
    return () => unsubscribe();
  }, [x]);

  return (
    <motion.div
      className={`touch-none ${className}`}
      drag="x"
      dragConstraints={{ left: minX, right: maxX }}
      dragElastic={0.1}
      style={{ x, opacity, rotate, scale, backgroundColor: background }}
      onDrag={(event, info) => {
        setVelocity({ x: info.velocity.x, y: info.velocity.y });
      }}
    >
      <div className="relative">
        {children}
        {Math.abs(velocity.x) > 100 && (
          <span className="absolute -top-6 left-0 text-xs text-slate-500">
            Velocity: {Math.round(velocity.x)}px/s
          </span>
        )}
      </div>
    </motion.div>
  );
}

// ============================================
// SCROLL-BASED ANIMATIONS
// ============================================

interface ScrollProgressBarProps {
  className?: string;
  color?: string;
}

export function ScrollProgressBar({ className = '', color = 'bg-brand' }: ScrollProgressBarProps) {
  const { scrollYProgress } = useScroll();
  const scaleX = useTransform(scrollYProgress, [0, 1], [0, 1]);

  return (
    <motion.div
      className={`fixed top-0 left-0 right-0 h-1 origin-left z-50 ${color} ${className}`}
      style={{ scaleX }}
    />
  );
}

interface ScrollFadeInProps {
  children: ReactNode;
  className?: string;
  threshold?: number;
}

export function ScrollFadeIn({ children, className = '', threshold = 0.2 }: ScrollFadeInProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });

  const opacity = useTransform(scrollYProgress, [0, threshold, 1 - threshold, 1], [0, 1, 1, 0]);

  const y = useTransform(scrollYProgress, [0, threshold, 1 - threshold, 1], [50, 0, 0, -50]);

  return (
    <motion.div ref={ref} className={className} style={{ opacity, y }}>
      {children}
    </motion.div>
  );
}

// ============================================
// SCROLL-LINKED ANIMATION (scroll function)
// ============================================

interface ScrollLinkedAnimationProps {
  children: ReactNode;
  className?: string;
  /** Animación a vincular al scroll */
  animation: {
    property: 'opacity' | 'y' | 'scale' | 'rotate';
    values: [number, number];
  };
  /** Offset del scroll target */
  offset?: [string, string];
}

export function ScrollLinkedAnimation({
  children,
  className = '',
  animation,
  offset = ['start end', 'end start'],
}: ScrollLinkedAnimationProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const controls = animate(element, { [animation.property]: animation.values }, { duration: 1 });

    const cleanup = scroll(controls, {
      target: element,
      offset: offset as any,
    });

    return cleanup;
  }, [animation, offset]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}

// ============================================
// DRAG CONTROLS (Programmatic drag)
// ============================================

interface DragHandleProps {
  children: ReactNode;
  className?: string;
  dragControls: ReturnType<typeof useDragControls>;
}

export function DragHandle({ children, className = '', dragControls }: DragHandleProps) {
  return (
    <div
      className={`cursor-grab ${className}`}
      onPointerDown={e => dragControls.start(e, { snapToCursor: true })}
    >
      {children}
    </div>
  );
}

interface ControlledDraggableProps {
  children: ReactNode;
  className?: string;
  /** Elemento que controla el drag */
  handle?: ReactNode;
  /** Axis de drag */
  axis?: 'x' | 'y';
  /** Restricciones */
  constraints?: { left?: number; right?: number; top?: number; bottom?: number };
}

export function ControlledDraggable({
  children,
  className = '',
  handle,
  axis = 'x',
  constraints,
}: ControlledDraggableProps) {
  const dragControls = useDragControls();

  return (
    <div className={className}>
      {handle && (
        <DragHandle dragControls={dragControls} className="mb-2">
          {handle}
        </DragHandle>
      )}
      <motion.div
        drag={axis}
        dragControls={dragControls}
        dragListener={!handle}
        dragConstraints={constraints}
        dragElastic={0.2}
        whileDrag={{ scale: 1.02 }}
      >
        {children}
      </motion.div>
    </div>
  );
}

// ============================================
// SWIPE CARD (Tinder-like)
// ============================================

interface SwipeCardProps {
  children: ReactNode;
  className?: string;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  onSwipeUp?: () => void;
  threshold?: number;
}

export function SwipeCard({
  children,
  className = '',
  onSwipeLeft,
  onSwipeRight,
  onSwipeUp,
  threshold = 100,
}: SwipeCardProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-30, 30]);
  const opacity = useTransform(
    x,
    [-threshold - 50, -threshold, threshold, threshold + 50],
    [0, 1, 1, 0]
  );

  const handleDragEnd = (event: MouseEvent | TouchEvent | PointerEvent, info: DragInfo) => {
    const velocity = Math.abs(info.velocity.x);
    const offset = Math.abs(info.offset.x);

    if (offset > threshold || velocity > 500) {
      if (info.offset.x > 0) {
        onSwipeRight?.();
      } else {
        onSwipeLeft?.();
      }
    }

    if (Math.abs(info.offset.y) > threshold && info.offset.y < 0) {
      onSwipeUp?.();
    }
  };

  return (
    <motion.div
      className={`touch-none ${className}`}
      style={{ x, y, rotate, opacity }}
      drag
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      dragElastic={0.7}
      onDragEnd={handleDragEnd}
      whileDrag={{ scale: 1.02, cursor: 'grabbing' }}
    >
      {children}
    </motion.div>
  );
}

// ============================================
// MAGNETIC BUTTON
// ============================================

interface MagneticButtonProps {
  children: ReactNode;
  className?: string;
  strength?: number;
  onClick?: () => void;
}

export function MagneticButton({
  children,
  className = '',
  strength = 0.3,
  onClick,
}: MagneticButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const handleMouseMove = (event: React.MouseEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;

    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const distanceX = event.clientX - centerX;
    const distanceY = event.clientY - centerY;

    x.set(distanceX * strength);
    y.set(distanceY * strength);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.button
      ref={ref}
      className={className}
      style={{ x, y }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      {children}
    </motion.button>
  );
}

// ============================================
// PARALLAX CONTAINER
// ============================================

interface ParallaxContainerProps {
  children: ReactNode;
  className?: string;
  speed?: number;
}

export function ParallaxContainer({
  children,
  className = '',
  speed = 0.5,
}: ParallaxContainerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });

  const y = useTransform(scrollYProgress, [0, 1], [0, 100 * speed]);

  return (
    <div ref={ref} className={`relative overflow-hidden ${className}`}>
      <motion.div style={{ y }}>{children}</motion.div>
    </div>
  );
}

// ============================================
// USE VELOCITY HOOK
// ============================================

export function useVelocity(motionValue: MotionValue<number>) {
  const [velocity, setVelocity] = useState(0);

  useEffect(() => {
    const unsubscribe = motionValue.on('change', () => {
      setVelocity(motionValue.getVelocity());
    });
    return () => unsubscribe();
  }, [motionValue]);

  return velocity;
}

// ============================================
// DISTANCE FROM CENTER
// ============================================

export function useDistanceFromCenter(
  x: MotionValue<number>,
  y: MotionValue<number>
): MotionValue<number> {
  return useTransform([x, y], ([latestX, latestY]) => {
    return Math.sqrt((latestX as number) ** 2 + (latestY as number) ** 2);
  });
}
