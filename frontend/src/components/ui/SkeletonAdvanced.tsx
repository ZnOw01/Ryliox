import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../lib/cn';
import { cva, type VariantProps } from 'class-variance-authority';

/**
 * SkeletonAdvanced - Skeleton loading con efectos modernos (2026)
 *
 * Características:
 * - Shimmer effect con gradient animado
 * - Pulse animations sutiles
 * - Content-aware skeletons (círculo, texto, card, etc.)
 * - Staggered loading animations
 * - Dark mode support
 * - Reduced motion support
 *
 * @example
 * ```tsx
 * // Skeleton shimmer avanzado
 * <SkeletonAdvanced variant="text" shimmer />
 *
 * // Card skeleton con múltiples elementos
 * <CardSkeletonModern />
 *
 * // Lista con staggered loading
 * <ListSkeletonAdvanced count={5} staggerDelay={0.1} />
 *
 * // Content-aware: avatar + texto
 * <AvatarTextSkeleton />
 *
 * // Bento grid skeletons
 * <BentoSkeletonAnimated />
 * ```
 */

const skeletonVariants = cva('relative overflow-hidden bg-slate-200/60 dark:bg-slate-700/60', {
  variants: {
    variant: {
      text: 'rounded h-4 w-full',
      title: 'rounded h-6 w-3/4',
      heading: 'rounded h-8 w-2/3',
      circle: 'rounded-full',
      avatar: 'rounded-full',
      square: 'rounded-lg',
      card: 'rounded-xl',
      button: 'rounded-lg h-10 w-24',
      image: 'rounded-lg',
      line: 'rounded h-px w-full',
      badge: 'rounded-full h-6 w-16',
    },
    size: {
      sm: '',
      default: '',
      lg: '',
      xl: '',
    },
    width: {
      full: 'w-full',
      auto: 'w-auto',
      '3/4': 'w-3/4',
      '2/3': 'w-2/3',
      '1/2': 'w-1/2',
      '1/3': 'w-1/3',
      '1/4': 'w-1/4',
    },
    height: {
      sm: 'h-2',
      default: 'h-4',
      lg: 'h-6',
      xl: 'h-8',
    },
    animation: {
      pulse: 'animate-pulse-slow',
      shimmer: '',
      none: '',
    },
  },
  defaultVariants: {
    variant: 'text',
    size: 'default',
    width: 'full',
    height: 'default',
    animation: 'shimmer',
  },
});

export interface SkeletonAdvancedProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof skeletonVariants> {
  /** Activar efecto shimmer */
  shimmer?: boolean;
  /** Delay de animación en segundos */
  delay?: number;
  /** Duración del ciclo shimmer en segundos */
  duration?: number;
  /** Color del shimmer */
  shimmerColor?: string;
}

export function SkeletonAdvanced({
  className,
  variant,
  size,
  width,
  height,
  animation,
  shimmer = true,
  delay = 0,
  duration = 1.5,
  style,
  ...props
}: SkeletonAdvancedProps) {
  const shimmerStyle: React.CSSProperties = shimmer
    ? {
        backgroundImage:
          'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
        backgroundSize: '200% 100%',
        animation: `shimmer ${duration}s infinite`,
        animationDelay: `${delay}s`,
      }
    : {};

  return (
    <div
      className={cn(skeletonVariants({ variant, size, width, height, animation }), className)}
      style={{
        ...shimmerStyle,
        ...style,
        animationDelay: `${delay}s`,
      }}
      aria-hidden="true"
      {...props}
    />
  );
}

/**
 * CardSkeletonModern - Card completa skeleton
 */
export interface CardSkeletonModernProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Mostrar imagen/header */
  hasImage?: boolean;
  /** Número de líneas de texto */
  lines?: number;
  /** Mostrar footer con botones */
  hasFooter?: boolean;
  /** Animación shimmer */
  shimmer?: boolean;
  /** Delay de animación */
  delay?: number;
}

export function CardSkeletonModern({
  hasImage = true,
  lines = 3,
  hasFooter = true,
  shimmer = true,
  delay = 0,
  className,
  ...props
}: CardSkeletonModernProps) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-slate-200/60 dark:border-slate-700/60',
        'bg-white/80 dark:bg-slate-900/80 p-5 space-y-4',
        className
      )}
      aria-busy="true"
      aria-label="Cargando contenido"
      {...props}
    >
      {hasImage && (
        <SkeletonAdvanced
          variant="image"
          height="xl"
          className="h-40"
          shimmer={shimmer}
          delay={delay}
        />
      )}

      <SkeletonAdvanced variant="title" shimmer={shimmer} delay={delay + 0.1} />

      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonAdvanced
            key={i}
            variant="text"
            width={i === lines - 1 ? '2/3' : 'full'}
            shimmer={shimmer}
            delay={delay + 0.15 + i * 0.05}
          />
        ))}
      </div>

      {hasFooter && (
        <div className="flex items-center gap-3 pt-2">
          <SkeletonAdvanced variant="button" shimmer={shimmer} delay={delay + 0.3} />
          <SkeletonAdvanced
            variant="button"
            width="1/2"
            className="w-20"
            shimmer={shimmer}
            delay={delay + 0.35}
          />
        </div>
      )}
    </div>
  );
}

/**
 * ListSkeletonAdvanced - Lista con staggered loading
 */
export interface ListSkeletonAdvancedProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Número de items */
  count?: number;
  /** Tipo de item */
  itemVariant?: 'text' | 'avatar-text' | 'icon-text' | 'card';
  /** Delay entre items */
  staggerDelay?: number;
  /** Mostrar separadores */
  showDividers?: boolean;
  /** Animación shimmer */
  shimmer?: boolean;
}

export function ListSkeletonAdvanced({
  count = 5,
  itemVariant = 'avatar-text',
  staggerDelay = 0.08,
  showDividers = true,
  shimmer = true,
  className,
  ...props
}: ListSkeletonAdvancedProps) {
  return (
    <div className={cn('space-y-1', className)} {...props}>
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            duration: 0.3,
            delay: i * staggerDelay,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          {showDividers && i > 0 && (
            <SkeletonAdvanced
              variant="line"
              height="sm"
              className="my-2"
              shimmer={false}
              animation="none"
            />
          )}

          {itemVariant === 'avatar-text' && (
            <div className="flex items-center gap-3 py-3">
              <SkeletonAdvanced
                variant="avatar"
                size="lg"
                className="h-10 w-10"
                shimmer={shimmer}
                delay={i * staggerDelay}
              />
              <div className="flex-1 space-y-2">
                <SkeletonAdvanced
                  variant="title"
                  height="lg"
                  className="h-4 w-1/3"
                  shimmer={shimmer}
                  delay={i * staggerDelay + 0.05}
                />
                <SkeletonAdvanced
                  variant="text"
                  width="1/2"
                  shimmer={shimmer}
                  delay={i * staggerDelay + 0.1}
                />
              </div>
            </div>
          )}

          {itemVariant === 'text' && (
            <div className="py-2 space-y-2">
              <SkeletonAdvanced variant="title" shimmer={shimmer} delay={i * staggerDelay} />
              <SkeletonAdvanced
                variant="text"
                width="3/4"
                shimmer={shimmer}
                delay={i * staggerDelay + 0.05}
              />
            </div>
          )}

          {itemVariant === 'icon-text' && (
            <div className="flex items-center gap-3 py-3">
              <SkeletonAdvanced
                variant="square"
                size="lg"
                className="h-10 w-10 rounded-lg"
                shimmer={shimmer}
                delay={i * staggerDelay}
              />
              <SkeletonAdvanced
                variant="title"
                width="2/3"
                shimmer={shimmer}
                delay={i * staggerDelay + 0.05}
              />
            </div>
          )}

          {itemVariant === 'card' && (
            <CardSkeletonModern
              hasImage={false}
              lines={2}
              hasFooter={false}
              shimmer={shimmer}
              delay={i * staggerDelay}
            />
          )}
        </motion.div>
      ))}
    </div>
  );
}

/**
 * AvatarTextSkeleton - Estructura común: avatar + texto
 */
export interface AvatarTextSkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Tamaño del avatar */
  avatarSize?: 'sm' | 'md' | 'lg';
  /** Número de líneas de texto */
  lines?: number;
  /** Animación shimmer */
  shimmer?: boolean;
  /** Delay de animación */
  delay?: number;
}

export function AvatarTextSkeleton({
  avatarSize = 'md',
  lines = 2,
  shimmer = true,
  delay = 0,
  className,
  ...props
}: AvatarTextSkeletonProps) {
  const avatarSizes = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
  };

  return (
    <div className={cn('flex items-center gap-3', className)} {...props}>
      <SkeletonAdvanced
        variant="avatar"
        className={avatarSizes[avatarSize]}
        shimmer={shimmer}
        delay={delay}
      />
      <div className="flex-1 space-y-2">
        {lines >= 1 && (
          <SkeletonAdvanced
            variant="title"
            width="2/3"
            className="h-4"
            shimmer={shimmer}
            delay={delay + 0.05}
          />
        )}
        {lines >= 2 && (
          <SkeletonAdvanced variant="text" width="1/2" shimmer={shimmer} delay={delay + 0.1} />
        )}
      </div>
    </div>
  );
}

/**
 * BentoSkeletonAnimated - Skeleton para layouts bento
 */
export interface BentoSkeletonAnimatedProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Configuración de items: [colSpan, rowSpan][] */
  items?: Array<[number, number]>;
  /** Gap entre items */
  gap?: 4 | 6 | 8;
  /** Animación shimmer */
  shimmer?: boolean;
}

export function BentoSkeletonAnimated({
  items = [
    [2, 2],
    [1, 1],
    [1, 1],
    [2, 1],
  ],
  gap = 4,
  shimmer = true,
  className,
  ...props
}: BentoSkeletonAnimatedProps) {
  const gapClass = {
    4: 'gap-4',
    6: 'gap-6',
    8: 'gap-8',
  };

  return (
    <div
      className={cn('grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4', gapClass[gap], className)}
      {...props}
    >
      {items.map(([colSpan, rowSpan], i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: 0.4,
            delay: i * 0.1,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
          className={cn(
            'rounded-2xl overflow-hidden',
            colSpan > 1 && `sm:col-span-${colSpan}`,
            rowSpan > 1 && `row-span-${rowSpan}`
          )}
          style={{ minHeight: rowSpan * 120 }}
        >
          <CardSkeletonModern
            hasImage={rowSpan > 1}
            lines={rowSpan > 1 ? 3 : 2}
            hasFooter={false}
            shimmer={shimmer}
            delay={i * 0.1}
            className="h-full"
          />
        </motion.div>
      ))}
    </div>
  );
}

/**
 * TextSkeletonModern - Múltiples líneas de texto
 */
export interface TextSkeletonModernProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Número de líneas */
  lines?: number;
  /** Ancho de la última línea */
  lastLineWidth?: '1/4' | '1/3' | '1/2' | '2/3' | '3/4';
  /** Espaciado entre líneas */
  gap?: 2 | 3;
  /** Animación shimmer */
  shimmer?: boolean;
  /** Delay inicial */
  delay?: number;
}

export function TextSkeletonModern({
  lines = 4,
  lastLineWidth = '2/3',
  gap = 3,
  shimmer = true,
  delay = 0,
  className,
  ...props
}: TextSkeletonModernProps) {
  const gapClass = {
    2: 'space-y-2',
    3: 'space-y-3',
  };

  return (
    <div className={cn(gapClass[gap], className)} {...props}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonAdvanced
          key={i}
          variant="text"
          width={i === lines - 1 ? lastLineWidth : 'full'}
          shimmer={shimmer}
          delay={delay + i * 0.05}
        />
      ))}
    </div>
  );
}

/**
 * ImageSkeletonAdvanced - Skeleton para imágenes con ratio
 */
export interface ImageSkeletonAdvancedProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Ratio de aspecto */
  ratio?: '1:1' | '4:3' | '16:9' | '21:9';
  /** Mostrar icono placeholder */
  showIcon?: boolean;
  /** Animación shimmer */
  shimmer?: boolean;
  /** Bordes redondeados */
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

export function ImageSkeletonAdvanced({
  ratio = '16:9',
  showIcon = true,
  shimmer = true,
  rounded = 'lg',
  className,
  ...props
}: ImageSkeletonAdvancedProps) {
  const ratios = {
    '1:1': 'pb-[100%]',
    '4:3': 'pb-[75%]',
    '16:9': 'pb-[56.25%]',
    '21:9': 'pb-[42.86%]',
  };

  const roundedClasses = {
    none: 'rounded-none',
    sm: 'rounded-lg',
    md: 'rounded-xl',
    lg: 'rounded-2xl',
    xl: 'rounded-3xl',
    full: 'rounded-3xl',
  };

  return (
    <div
      className={cn(
        'relative overflow-hidden bg-slate-200/60 dark:bg-slate-700/60',
        roundedClasses[rounded],
        className
      )}
      {...props}
    >
      <div className={cn('relative w-full', ratios[ratio])}>
        {showIcon && (
          <div className="absolute inset-0 flex items-center justify-center">
            <svg
              className="h-8 w-8 text-slate-300 dark:text-slate-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}
      </div>
      {shimmer && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite',
          }}
        />
      )}
    </div>
  );
}

/**
 * StatsSkeleton - Para dashboards/stats
 */
export interface StatsSkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Número de stat cards */
  count?: number;
  /** Layout */
  layout?: 'grid' | 'row';
  /** Animación shimmer */
  shimmer?: boolean;
}

export function StatsSkeleton({
  count = 4,
  layout = 'grid',
  shimmer = true,
  className,
  ...props
}: StatsSkeletonProps) {
  return (
    <div
      className={cn(
        layout === 'grid'
          ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4'
          : 'flex flex-wrap gap-4',
        className
      )}
      {...props}
    >
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: i * 0.08 }}
          className="flex-1 min-w-[200px] rounded-xl border border-slate-200/60 dark:border-slate-700/60 bg-white/80 dark:bg-slate-900/80 p-5 space-y-3"
        >
          <div className="flex items-center gap-2">
            <SkeletonAdvanced
              variant="square"
              className="h-8 w-8 rounded-lg"
              shimmer={shimmer}
              delay={i * 0.08}
            />
            <SkeletonAdvanced
              variant="badge"
              width="1/2"
              shimmer={shimmer}
              delay={i * 0.08 + 0.05}
            />
          </div>
          <SkeletonAdvanced
            variant="heading"
            className="h-8 w-24"
            shimmer={shimmer}
            delay={i * 0.08 + 0.1}
          />
          <SkeletonAdvanced variant="text" width="3/4" shimmer={shimmer} delay={i * 0.08 + 0.15} />
        </motion.div>
      ))}
    </div>
  );
}
