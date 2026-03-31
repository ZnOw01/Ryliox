import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../lib/cn';
import { Spinner, CheckCircle, XCircle } from '@phosphor-icons/react';

// Tipos de estados de carga
export type LoadingState = 'idle' | 'loading' | 'success' | 'error' | 'pending';

interface LoadingFeedbackProps {
  state: LoadingState;
  message?: string;
  submessage?: string;
  progress?: number;
  className?: string;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

// Componente principal de feedback de carga
export function LoadingFeedback({
  state,
  message,
  submessage,
  progress,
  className,
  showIcon = true,
  size = 'md',
}: LoadingFeedbackProps) {
  const sizes = {
    sm: { icon: 16, text: 'text-xs', subtext: 'text-[10px]' },
    md: { icon: 20, text: 'text-sm', subtext: 'text-xs' },
    lg: { icon: 24, text: 'text-base', subtext: 'text-sm' },
  };

  const config = {
    idle: {
      icon: null,
      color: 'text-muted-foreground',
      bg: 'bg-muted/50',
      initial: { opacity: 1 },
      animate: { opacity: 1 },
      transition: { duration: 0 },
    },
    loading: {
      icon: Spinner,
      color: 'text-primary',
      bg: 'bg-primary/10',
      initial: { rotate: 0 },
      animate: { rotate: 360 },
      transition: { duration: 1, repeat: Infinity, ease: 'linear' as const },
    },
    pending: {
      icon: Spinner,
      color: 'text-amber-500',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      initial: { rotate: 0 },
      animate: { rotate: 360 },
      transition: { duration: 1.5, repeat: Infinity, ease: 'linear' as const },
    },
    success: {
      icon: CheckCircle,
      color: 'text-emerald-600',
      bg: 'bg-emerald-100 dark:bg-emerald-900/30',
      initial: { scale: 0 },
      animate: { scale: 1 },
      transition: { type: 'spring' as const, stiffness: 500, damping: 30 },
    },
    error: {
      icon: XCircle,
      color: 'text-red-600',
      bg: 'bg-red-100 dark:bg-red-900/30',
      initial: { scale: 0 },
      animate: { scale: 1 },
      transition: { type: 'spring' as const, stiffness: 500, damping: 30 },
    },
  };

  const currentConfig = config[state];
  const Icon = currentConfig.icon;

  return (
    <motion.div
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 transition-colors',
        currentConfig.bg,
        className
      )}
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -5 }}
    >
      {showIcon && Icon && (
        <motion.div
          initial={currentConfig.initial}
          animate={currentConfig.animate || {}}
          transition={currentConfig.transition}
          className={cn(currentConfig.color)}
        >
          <Icon
            className={cn('shrink-0')}
            style={{ width: sizes[size].icon, height: sizes[size].icon }}
            weight="fill"
          />
        </motion.div>
      )}

      <div className="min-w-0 flex-1">
        {message && (
          <p className={cn('font-medium leading-tight', currentConfig.color, sizes[size].text)}>
            {message}
          </p>
        )}
        {submessage && (
          <p className={cn('text-muted-foreground', sizes[size].subtext)}>{submessage}</p>
        )}
      </div>

      {/* Progress indicator */}
      {progress !== undefined && state === 'loading' && (
        <div className="ml-auto flex-shrink-0">
          <div className="relative h-8 w-8">
            <svg className="h-8 w-8 -rotate-90" viewBox="0 0 32 32">
              <circle
                cx="16"
                cy="16"
                r="12"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                className="text-muted-foreground/20"
              />
              <motion.circle
                cx="16"
                cy="16"
                r="12"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                className={currentConfig.color}
                strokeDasharray={75.4}
                initial={{ strokeDashoffset: 75.4 }}
                animate={{ strokeDashoffset: 75.4 - (75.4 * progress) / 100 }}
                transition={{ duration: 0.3 }}
              />
            </svg>
            <span
              className={cn(
                'absolute inset-0 flex items-center justify-center text-[10px] font-semibold',
                currentConfig.color
              )}
            >
              {Math.round(progress)}%
            </span>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// Progress bar animado
interface AnimatedProgressBarProps {
  progress: number;
  status?: 'idle' | 'loading' | 'success' | 'error';
  label?: string;
  showPercentage?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function AnimatedProgressBar({
  progress,
  status = 'loading',
  label,
  showPercentage = true,
  size = 'md',
  className,
}: AnimatedProgressBarProps) {
  const heights = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  };

  const statusColors = {
    idle: 'bg-muted',
    loading: 'bg-primary',
    success: 'bg-emerald-500',
    error: 'bg-red-500',
  };

  return (
    <div className={cn('w-full', className)}>
      {(label || showPercentage) && (
        <div className="mb-2 flex items-center justify-between text-sm">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showPercentage && (
            <motion.span
              key={progress}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="font-medium text-foreground"
            >
              {Math.round(progress)}%
            </motion.span>
          )}
        </div>
      )}
      <div className={cn('w-full overflow-hidden rounded-full bg-muted', heights[size])}>
        <motion.div
          className={cn('h-full rounded-full', statusColors[status])}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          {/* Shimmer effect for loading state */}
          {status === 'loading' && (
            <motion.div
              className="h-full w-full"
              style={{
                background:
                  'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
                backgroundSize: '200% 100%',
              }}
              animate={{ backgroundPosition: ['200% 0', '-200% 0'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
            />
          )}
        </motion.div>
      </div>
    </div>
  );
}

// Skeleton con pulso suave
interface ElegantSkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  circle?: boolean;
  animate?: boolean;
  delay?: number;
}

export function ElegantSkeleton({
  className,
  width,
  height,
  circle = false,
  animate = true,
  delay = 0,
}: ElegantSkeletonProps) {
  return (
    <motion.div
      className={cn(
        'relative overflow-hidden bg-muted',
        circle ? 'rounded-full' : 'rounded-lg',
        animate && 'before:absolute before:inset-0 before:-translate-x-full',
        animate &&
          'before:animate-shimmer before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent',
        className
      )}
      style={{ width, height }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay, duration: 0.3 }}
    >
      {animate && (
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          initial={{ x: '-100%' }}
          animate={{ x: '200%' }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'linear',
            delay: delay + 0.5,
          }}
        />
      )}
    </motion.div>
  );
}

// Loading overlay
interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
  children: React.ReactNode;
  blur?: boolean;
  className?: string;
}

export function LoadingOverlay({
  isLoading,
  message,
  children,
  blur = true,
  className,
}: LoadingOverlayProps) {
  return (
    <div className={cn('relative', className)}>
      {children}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={cn(
              'absolute inset-0 z-50 flex items-center justify-center rounded-xl',
              blur && 'bg-background/80 backdrop-blur-sm',
              !blur && 'bg-background/90'
            )}
          >
            <motion.div
              className="flex flex-col items-center gap-3"
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
            >
              <motion.div
                className="h-8 w-8 rounded-full border-2 border-primary/30 border-t-primary"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              />
              {message && <p className="text-sm text-muted-foreground">{message}</p>}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Staggered loading list
interface StaggeredLoadingListProps {
  count?: number;
  itemHeight?: number;
  className?: string;
}

export function StaggeredLoadingList({
  count = 3,
  itemHeight = 60,
  className,
}: StaggeredLoadingListProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          className="flex items-center gap-3 rounded-lg p-3"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            delay: i * 0.1,
            duration: 0.3,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          <ElegantSkeleton circle width={40} height={40} delay={i * 0.1} />
          <div className="flex-1 space-y-2">
            <ElegantSkeleton height={16} width={`${70 - i * 10}%`} delay={i * 0.1 + 0.05} />
            <ElegantSkeleton height={12} width={`${50 - i * 5}%`} delay={i * 0.1 + 0.1} />
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// Content loading placeholder
interface ContentPlaceholderProps {
  lines?: number;
  hasImage?: boolean;
  hasActions?: boolean;
  className?: string;
}

export function ContentPlaceholder({
  lines = 3,
  hasImage = true,
  hasActions = true,
  className,
}: ContentPlaceholderProps) {
  return (
    <div className={cn('space-y-4 rounded-xl border border-border bg-card p-5', className)}>
      {hasImage && <ElegantSkeleton height={120} className="rounded-lg" />}
      <ElegantSkeleton height={24} width="70%" />
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <ElegantSkeleton
            key={i}
            height={14}
            width={i === lines - 1 ? '60%' : '100%'}
            delay={i * 0.05}
          />
        ))}
      </div>
      {hasActions && (
        <div className="flex gap-3 pt-2">
          <ElegantSkeleton height={36} width={100} delay={0.2} />
          <ElegantSkeleton height={36} width={80} delay={0.25} />
        </div>
      )}
    </div>
  );
}
