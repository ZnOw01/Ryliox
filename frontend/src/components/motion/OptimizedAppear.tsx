import { motion, useReducedMotion, type Target, type Transition } from 'framer-motion';
import type { ReactNode } from 'react';

export const APPEAR_ANIMATION_CONFIG = {
  duration: {
    fast: 300,
    normal: 500,
  },
  ease: {
    easeOut: 'easeOut' as const,
  },
};

type OptimizedAppearProps = {
  children: ReactNode;
  className?: string;
  initial: Target;
  animate: Target;
  duration?: number;
  delay?: number;
  ease?: Transition['ease'];
};

/** A single declarative animation path; Motion owns all transform composition. */
export function OptimizedAppear({
  children,
  className = '',
  initial,
  animate,
  duration = APPEAR_ANIMATION_CONFIG.duration.normal,
  delay = 0,
  ease = APPEAR_ANIMATION_CONFIG.ease.easeOut,
}: OptimizedAppearProps) {
  const reduceMotion = useReducedMotion();
  const reducedInitial = 'opacity' in initial ? { opacity: initial.opacity } : false;

  return (
    <motion.div
      className={className}
      initial={reduceMotion ? reducedInitial : initial}
      animate={animate}
      transition={{
        duration: reduceMotion ? 0.01 : duration / 1000,
        ease,
        delay: reduceMotion ? 0 : delay / 1000,
      }}
    >
      {children}
    </motion.div>
  );
}

type OptimizedFadeInProps = {
  children: ReactNode;
  className?: string;
  duration?: number;
  delay?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  distance?: number;
};

export function OptimizedFadeIn({
  children,
  className = '',
  duration,
  delay = 0,
  direction = 'up',
  distance = 20,
}: OptimizedFadeInProps) {
  const offset =
    direction === 'up'
      ? { y: distance }
      : direction === 'down'
        ? { y: -distance }
        : direction === 'left'
          ? { x: distance }
          : direction === 'right'
            ? { x: -distance }
            : {};

  return (
    <OptimizedAppear
      className={className}
      initial={{ opacity: 0, ...offset }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      duration={duration}
      delay={delay}
    >
      {children}
    </OptimizedAppear>
  );
}
