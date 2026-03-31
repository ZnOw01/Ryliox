import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { cn } from '../../lib/cn';
import { useRef, useState, useCallback } from 'react';

// ============================================================================
// HOVER EFFECTS
// ============================================================================

interface HoverCardProps {
  children: React.ReactNode;
  className?: string;
  lift?: boolean;
  glow?: boolean;
  scale?: number;
}

export function HoverCard({
  children,
  className,
  lift = true,
  glow = false,
  scale = 1.02,
}: HoverCardProps) {
  return (
    <motion.div
      className={cn(
        'transition-shadow duration-300',
        glow && 'hover:shadow-xl hover:shadow-primary/10',
        className
      )}
      whileHover={lift ? { y: -4, scale } : { scale }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      {children}
    </motion.div>
  );
}

// Botón con efecto de ripple al hacer click
interface RippleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  success?: boolean;
}

export function RippleButton({
  children,
  className,
  variant = 'primary',
  size = 'md',
  loading = false,
  success = false,
  onClick,
  ...props
}: RippleButtonProps) {
  const [ripples, setRipples] = useState<{ x: number; y: number; id: number }[]>([]);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const addRipple = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
    if (!buttonRef.current) return;

    const rect = buttonRef.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const id = Date.now();

    setRipples(prev => [...prev, { x, y, id }]);

    setTimeout(() => {
      setRipples(prev => prev.filter(ripple => ripple.id !== id));
    }, 600);
  }, []);

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2.5 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  const variants = {
    primary: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-md hover:shadow-lg',
    secondary:
      'bg-secondary text-secondary-foreground border border-border hover:bg-accent hover:border-primary/30',
    ghost: 'text-foreground hover:bg-accent/50',
    danger: 'bg-red-600 text-white hover:bg-red-700 shadow-md hover:shadow-lg',
  };

  return (
    <motion.button
      ref={buttonRef}
      className={cn(
        'relative overflow-hidden rounded-xl font-medium transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-60',
        sizes[size],
        variants[variant],
        className
      )}
      onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
        addRipple(e);
        onClick?.(e);
      }}
      whileHover={{ scale: 1.02, y: -1 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring' as const, stiffness: 400, damping: 25 }}
      {...(props as object)}
    >
      <span className="relative z-10 flex items-center justify-center gap-2">{children}</span>

      {/* Ripple effects */}
      {ripples.map(ripple => (
        <motion.span
          key={ripple.id}
          className="pointer-events-none absolute rounded-full bg-white/30"
          style={{
            left: ripple.x,
            top: ripple.y,
          }}
          initial={{ width: 0, height: 0, x: 0, y: 0, opacity: 1 }}
          animate={{ width: 200, height: 200, x: -100, y: -100, opacity: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      ))}

      {/* Loading state */}
      {loading && (
        <motion.div
          className="absolute inset-0 flex items-center justify-center bg-inherit rounded-xl"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <motion.div
            className="h-4 w-4 rounded-full border-2 border-current border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
        </motion.div>
      )}

      {/* Success state */}
      {success && (
        <motion.div
          className="absolute inset-0 flex items-center justify-center bg-emerald-500 rounded-xl"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        >
          <svg className="h-5 w-5 text-white" viewBox="0 0 16 16" fill="none">
            <path
              d="M3 8l3.5 3.5L13 5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </motion.div>
      )}
    </motion.button>
  );
}

// Magnetic button que sigue el cursor
interface MagneticButtonProps {
  children: React.ReactNode;
  className?: string;
  strength?: number;
  onClick?: () => void;
}

export function MagneticButton({
  children,
  className,
  strength = 0.3,
  onClick,
}: MagneticButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const springX = useSpring(x, { stiffness: 150, damping: 15 });
  const springY = useSpring(y, { stiffness: 150, damping: 15 });

  const handleMouseMove = (event: React.MouseEvent) => {
    if (!ref.current) return;

    const rect = ref.current.getBoundingClientRect();
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
      className={cn(
        'relative rounded-xl bg-primary px-6 py-3 text-primary-foreground font-medium',
        'shadow-lg transition-shadow hover:shadow-xl',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className
      )}
      style={{ x: springX, y: springY }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      whileTap={{ scale: 0.95 }}
    >
      {children}
    </motion.button>
  );
}

// ============================================================================
// CLICK FEEDBACK
// ============================================================================

interface ClickFeedbackProps {
  children: React.ReactNode;
  feedback?: 'pulse' | 'scale' | 'glow' | 'none';
  className?: string;
}

export function ClickFeedback({ children, feedback = 'scale', className }: ClickFeedbackProps) {
  const feedbackVariants = {
    pulse: {
      whileTap: { scale: 0.95 },
    },
    scale: {
      whileTap: { scale: 0.97 },
    },
    glow: {
      whileTap: {
        boxShadow: '0 0 0 4px var(--ring)',
      },
    },
    none: {},
  };

  return (
    <motion.div
      className={className}
      {...feedbackVariants[feedback]}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      {children}
    </motion.div>
  );
}

// ============================================================================
// TRANSICIONES ELEGANTES
// ============================================================================

// Fade transition wrapper
interface FadeTransitionProps {
  children: React.ReactNode;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  delay?: number;
  duration?: number;
  className?: string;
  distance?: number;
}

export function FadeTransition({
  children,
  direction = 'up',
  delay = 0,
  duration = 0.4,
  className,
  distance = 20,
}: FadeTransitionProps) {
  const directions = {
    up: { y: distance },
    down: { y: -distance },
    left: { x: distance },
    right: { x: -distance },
    none: {},
  };

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, ...directions[direction] }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={{ opacity: 0, ...directions[direction] }}
      transition={{
        duration,
        delay,
        ease: [0.25, 0.46, 0.45, 0.94],
      }}
    >
      {children}
    </motion.div>
  );
}

// Stagger children animation
interface StaggerContainerProps {
  children: React.ReactNode;
  className?: string;
  staggerDelay?: number;
  initialDelay?: number;
}

export function StaggerContainer({
  children,
  className,
  staggerDelay = 0.1,
  initialDelay = 0,
}: StaggerContainerProps) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: {
            delayChildren: initialDelay,
            staggerChildren: staggerDelay,
          },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 20 },
        visible: {
          opacity: 1,
          y: 0,
          transition: {
            duration: 0.4,
            ease: [0.25, 0.46, 0.45, 0.94],
          },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

// Page transition
interface PageTransitionProps {
  children: React.ReactNode;
  className?: string;
}

export function PageTransition({ children, className }: PageTransitionProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {children}
    </motion.div>
  );
}

// ============================================================================
// EFFICIENT ANIMATIONS (GPU Accelerated)
// ============================================================================

// Shake animation para errores
interface ShakeProps {
  children: React.ReactNode;
  trigger: boolean;
  className?: string;
}

export function Shake({ children, trigger, className }: ShakeProps) {
  return (
    <motion.div
      className={className}
      animate={
        trigger
          ? {
              x: [0, -8, 8, -8, 8, 0],
            }
          : {}
      }
      transition={{ duration: 0.4 }}
    >
      {children}
    </motion.div>
  );
}

// Pulse animation para indicar actividad
interface PulseProps {
  children: React.ReactNode;
  active?: boolean;
  className?: string;
}

export function Pulse({ children, active = true, className }: PulseProps) {
  return (
    <motion.div
      className={className}
      animate={
        active
          ? {
              scale: [1, 1.05, 1],
              opacity: [1, 0.8, 1],
            }
          : {}
      }
      transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
    >
      {children}
    </motion.div>
  );
}

// Bounce animation para llamar la atención
interface BounceProps {
  children: React.ReactNode;
  className?: string;
}

export function Bounce({ children, className }: BounceProps) {
  return (
    <motion.div
      className={className}
      animate={{ y: [0, -6, 0] }}
      transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
    >
      {children}
    </motion.div>
  );
}

// Glow effect que se activa al hover
interface GlowEffectProps {
  children: React.ReactNode;
  className?: string;
  color?: string;
}

export function GlowEffect({ children, className, color = 'var(--primary)' }: GlowEffectProps) {
  return (
    <motion.div
      className={cn('relative', className)}
      whileHover={{
        boxShadow: `0 0 30px 5px ${color}30`,
      }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
}

// Number counter animation
interface CounterProps {
  value: number;
  className?: string;
  duration?: number;
  prefix?: string;
  suffix?: string;
}

export function Counter({
  value,
  className,
  duration = 1,
  prefix = '',
  suffix = '',
}: CounterProps) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, latest => Math.round(latest));

  return (
    <motion.span className={className}>
      {prefix}
      <motion.span>{rounded}</motion.span>
      {suffix}
    </motion.span>
  );
}
