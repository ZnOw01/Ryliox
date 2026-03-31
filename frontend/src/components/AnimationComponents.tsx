import {
  motion,
  AnimatePresence,
  type Variants,
  type Transition,
  type Target,
} from 'framer-motion';
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

// ============================================
// CONFIGURACIÃ“N GLOBAL DE ANIMACIONES
// ============================================

type EasingDefinition = [number, number, number, number];

export const ANIMATION_CONFIG = {
  duration: {
    fast: 0.15,
    normal: 0.25,
    slow: 0.35,
  },
  ease: {
    default: [0.4, 0, 0.2, 1] as EasingDefinition,
    bounce: [0.68, -0.55, 0.265, 1.55] as EasingDefinition,
    smooth: [0.25, 0.1, 0.25, 1] as EasingDefinition,
  },
  stagger: {
    fast: 0.03,
    normal: 0.05,
    slow: 0.08,
  },
};

// ============================================
// VARIANTES REUTILIZABLES
// ============================================

export const fadeInVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: ANIMATION_CONFIG.duration.normal, ease: ANIMATION_CONFIG.ease.default },
  },
  exit: {
    opacity: 0,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
};

export const slideUpVariants: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: ANIMATION_CONFIG.duration.normal, ease: ANIMATION_CONFIG.ease.default },
  },
  exit: {
    opacity: 0,
    y: -12,
    scale: 0.98,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
};

export const slideRightVariants: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: ANIMATION_CONFIG.duration.normal, ease: ANIMATION_CONFIG.ease.default },
  },
  exit: {
    opacity: 0,
    x: 20,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
};

export const scaleVariants: Variants = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: ANIMATION_CONFIG.duration.normal, ease: ANIMATION_CONFIG.ease.bounce },
  },
  exit: {
    opacity: 0,
    scale: 0.9,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
};

export const cardLiftVariants: Variants = {
  rest: {
    y: 0,
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
  hover: {
    y: -3,
    boxShadow: '0 8px 25px rgba(0,0,0,0.12)',
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
  tap: {
    y: 0,
    scale: 0.98,
    transition: { duration: 0.08 },
  },
};

export const buttonVariants: Variants = {
  rest: {
    scale: 1,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
  hover: {
    scale: 1.02,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
  tap: {
    scale: 0.97,
    transition: { duration: 0.08 },
  },
};

export const checkboxVariants: Variants = {
  unchecked: { scale: 1 },
  checked: {
    scale: [1, 1.15, 1],
    transition: { duration: 0.25, ease: ANIMATION_CONFIG.ease.bounce },
  },
};

export const staggerContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: ANIMATION_CONFIG.stagger.normal,
      delayChildren: 0.05,
    },
  },
  exit: {
    opacity: 0,
    transition: {
      staggerChildren: ANIMATION_CONFIG.stagger.fast,
      staggerDirection: -1,
    },
  },
};

export const staggerItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: 0.1 },
  },
};

export const toastVariants: Variants = {
  hidden: { opacity: 0, x: 100, scale: 0.9 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { duration: ANIMATION_CONFIG.duration.normal, ease: ANIMATION_CONFIG.ease.default },
  },
  exit: {
    opacity: 0,
    x: 100,
    scale: 0.9,
    transition: { duration: ANIMATION_CONFIG.duration.fast },
  },
};

export const celebrationVariants: Variants = {
  hidden: { scale: 0, rotate: -180, opacity: 0 },
  visible: {
    scale: 1,
    rotate: 0,
    opacity: 1,
    transition: {
      duration: 0.6,
      ease: ANIMATION_CONFIG.ease.bounce,
      type: 'spring',
      stiffness: 200,
      damping: 15,
    },
  },
};

// ============================================
// COMPONENTES DE ANIMACIÃ“N REUTILIZABLES
// ============================================

interface AnimatedCardProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

export function AnimatedCard({ children, className = '', delay = 0 }: AnimatedCardProps) {
  return (
    <motion.div
      className={className}
      variants={slideUpVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      transition={{ delay }}
    >
      {children}
    </motion.div>
  );
}

interface AnimatedButtonProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

export function AnimatedButton({
  children,
  className = '',
  onClick,
  disabled,
  type = 'button',
}: AnimatedButtonProps) {
  return (
    <motion.button
      type={type}
      className={className}
      variants={buttonVariants}
      initial="rest"
      whileHover={disabled ? undefined : 'hover'}
      whileTap={disabled ? undefined : 'tap'}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </motion.button>
  );
}

interface AnimatedCheckboxProps {
  checked: boolean;
  onChange: () => void;
  className?: string;
  label?: ReactNode;
}

export function AnimatedCheckbox({
  checked,
  onChange,
  className = '',
  label,
}: AnimatedCheckboxProps) {
  return (
    <motion.label
      className={`flex items-center gap-2 cursor-pointer ${className}`}
      variants={checkboxVariants}
      animate={checked ? 'checked' : 'unchecked'}
    >
      <input type="checkbox" checked={checked} onChange={onChange} className="sr-only" />
      <motion.div
        className={`h-4 w-4 rounded border-2 flex items-center justify-center ${
          checked
            ? 'bg-brand border-brand'
            : 'border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-800'
        }`}
        animate={checked ? { scale: [1, 1.15, 1] } : { scale: 1 }}
        transition={{ duration: 0.2, ease: ANIMATION_CONFIG.ease.bounce }}
      >
        {checked && (
          <motion.svg
            className="h-3 w-3 text-white"
            viewBox="0 0 16 16"
            fill="none"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            <motion.path
              d="M3 8l3.5 3.5L13 5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.2 }}
            />
          </motion.svg>
        )}
      </motion.div>
      {label && <span className="text-sm">{label}</span>}
    </motion.label>
  );
}

interface AnimatedProgressBarProps {
  progress: number;
  className?: string;
  isActive?: boolean;
}

export function AnimatedProgressBar({
  progress,
  className = '',
  isActive = false,
}: AnimatedProgressBarProps) {
  return (
    <div
      className={`h-2.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ${className}`}
    >
      <motion.div
        className={`h-full bg-brand ${isActive ? 'progress-bar-active' : ''}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        transition={{
          duration: 0.5,
          ease: ANIMATION_CONFIG.ease.default,
        }}
      />
    </div>
  );
}

interface StaggerContainerProps {
  children: ReactNode;
  className?: string;
  staggerDelay?: number;
}

export function StaggerContainer({
  children,
  className = '',
  staggerDelay = ANIMATION_CONFIG.stagger.normal,
}: StaggerContainerProps) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: {
            staggerChildren: staggerDelay,
            delayChildren: 0.05,
          },
        },
      }}
      initial="hidden"
      animate="visible"
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={staggerItemVariants}>
      {children}
    </motion.div>
  );
}

// ============================================
// HOOKS DE ANIMACIÃ“N
// ============================================

export function useReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useState(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  });

  return prefersReducedMotion;
}

interface RippleState {
  x: number;
  y: number;
  id: number;
}

export function useRipple() {
  const [ripples, setRipples] = useState<RippleState[]>([]);

  const createRipple = useCallback((event: React.MouseEvent<HTMLElement>) => {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const id = Date.now();

    setRipples(prev => [...prev, { x, y, id }]);

    setTimeout(() => {
      setRipples(prev => prev.filter(ripple => ripple.id !== id));
    }, 600);
  }, []);

  return { ripples, createRipple };
}

// ============================================
// CONTEXTO DE ANIMACIÃ“N
// ============================================

interface AnimationContextType {
  isReducedMotion: boolean;
  config: typeof ANIMATION_CONFIG;
}

const AnimationContext = createContext<AnimationContextType>({
  isReducedMotion: false,
  config: ANIMATION_CONFIG,
});

export function AnimationProvider({ children }: { children: ReactNode }) {
  const isReducedMotion = useReducedMotion();

  return (
    <AnimationContext.Provider value={{ isReducedMotion, config: ANIMATION_CONFIG }}>
      {children}
    </AnimationContext.Provider>
  );
}

export function useAnimation() {
  return useContext(AnimationContext);
}

// ============================================
// WRAPPER CON PREFERS-REDUCED-MOTION
// ============================================

interface AccessibleMotionProps {
  children: ReactNode;
  variants?: Variants;
  initial?: string | Target | false;
  animate?: string | Target;
  exit?: string | Target;
  transition?: Transition;
  className?: string;
}

export function AccessibleMotion({
  children,
  variants,
  initial,
  animate,
  exit,
  transition,
  className,
}: AccessibleMotionProps) {
  const { isReducedMotion } = useAnimation();

  if (isReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      variants={variants}
      initial={initial}
      animate={animate}
      exit={exit}
      transition={transition}
    >
      {children}
    </motion.div>
  );
}
