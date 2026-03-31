import { cn } from '../../lib/cn';
import { cva, type VariantProps } from 'class-variance-authority';
import { motion } from 'framer-motion';
import React from 'react';

/**
 * GlassCard - Componente de card con glassmorphism avanzado (2026)
 *
 * Características:
 * - Backdrop blur con diferentes intensidades
 * - Semi-transparent backgrounds
 * - Layered shadows sutiles
 * - Efectos de hover con lift
 * - Soporta dark mode automáticamente
 *
 * @example
 * ```tsx
 * // Glass card básico
 * <GlassCard>
 *   <GlassCardHeader>
 *     <GlassCardTitle>Título</GlassCardTitle>
 *   </GlassCardHeader>
 *   <GlassCardContent>Contenido</GlassCardContent>
 * </GlassCard>
 *
 * // Con gradiente y hover effect
 * <GlassCard
 *   variant="gradient"
 *   blur="heavy"
 *   hover="lift"
 *   glow="brand"
 * >
 *   Contenido premium
 * </GlassCard>
 *
 * // Neobrutalist style
 * <GlassCard variant="brutalist" hover="magnetic">
 *   Contenido bold
 * </GlassCard>
 * ```
 */

const glassCardVariants = cva('relative overflow-hidden transition-all duration-300 ease-out', {
  variants: {
    variant: {
      default: 'bg-card/70 dark:bg-card/70',
      frosted: 'bg-card/60 dark:bg-card/60',
      crystal: 'bg-card/40 dark:bg-card/40',
      gradient: 'bg-gradient-to-br from-card/80 to-card/40 dark:from-card/80 dark:to-card/40',
      neon: 'bg-card/75 dark:bg-card/75 ring-1 ring-inset',
      brutalist: 'bg-card dark:bg-card border-[3px] border-border dark:border-border',
    },
    blur: {
      none: '',
      light: 'backdrop-blur-sm',
      default: 'backdrop-blur-md',
      heavy: 'backdrop-blur-lg',
      extreme: 'backdrop-blur-xl backdrop-saturate-150',
    },
    radius: {
      none: 'rounded-none',
      sm: 'rounded-lg',
      default: 'rounded-2xl',
      lg: 'rounded-3xl',
      xl: 'rounded-[2rem]',
      full: 'rounded-3xl',
    },
    border: {
      none: '',
      subtle: 'border border-white/30 dark:border-white/10',
      default: 'border border-white/40 dark:border-white/20',
      prominent: 'border-2 border-white/50 dark:border-white/30',
      glow: 'border border-white/20 dark:border-white/10 shadow-[0_0_20px_rgba(255,255,255,0.1)]',
    },
    shadow: {
      none: '',
      sm: 'shadow-sm',
      default: 'shadow-lg shadow-black/5 dark:shadow-black/20',
      lg: 'shadow-xl shadow-black/10 dark:shadow-black/30',
      xl: 'shadow-2xl shadow-black/15 dark:shadow-black/40',
      layered:
        'shadow-[0_2px_8px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.2),0_8px_24px_rgba(0,0,0,0.3)]',
    },
    hover: {
      none: '',
      glow: 'hover:shadow-[0_0_30px_rgba(var(--brand-500)/0.15)] dark:hover:shadow-[0_0_30px_rgba(var(--brand-400)/0.2)] transition-shadow duration-500',
      lift: 'hover:-translate-y-1 hover:shadow-xl',
      scale: 'hover:scale-[1.02]',
      magnetic: 'hover:-translate-y-0.5 hover:shadow-lg',
      shine:
        'before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_2s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent',
    },
    glow: {
      none: '',
      brand:
        'shadow-[0_0_40px_rgba(var(--brand-500)/0.1)] dark:shadow-[0_0_40px_rgba(var(--brand-400)/0.15)]',
      subtle: 'shadow-[0_0_30px_rgba(0,0,0,0.05)] dark:shadow-[0_0_30px_rgba(255,255,255,0.05)]',
      colored: 'shadow-[0_8px_32px_rgba(99,102,241,0.15)]',
    },
    padding: {
      none: '',
      sm: 'p-3',
      default: 'p-5',
      lg: 'p-6',
      xl: 'p-8',
    },
  },
  defaultVariants: {
    variant: 'default',
    blur: 'default',
    radius: 'default',
    border: 'default',
    shadow: 'layered',
    hover: 'lift',
    glow: 'none',
    padding: 'default',
  },
});

export interface GlassCardProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof glassCardVariants> {
  /** Activar animación de entrada */
  animated?: boolean;
  /** Delay de animación en ms */
  animationDelay?: number;
  /** Mostrar patrón de fondo sutil */
  pattern?: boolean;
  /** Color del patrón */
  patternColor?: string;
}

export function GlassCard({
  className,
  variant,
  blur,
  radius,
  border,
  shadow,
  hover,
  glow,
  padding,
  animated = false,
  animationDelay = 0,
  pattern = false,
  children,
  ...props
}: GlassCardProps) {
  const cardContent = (
    <div
      className={cn(
        glassCardVariants({
          variant,
          blur,
          radius,
          border,
          shadow,
          hover,
          glow,
          padding,
        }),
        className
      )}
      {...props}
    >
      {pattern && (
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      )}
      {children}
    </div>
  );

  if (animated) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.4,
          delay: animationDelay / 1000,
          ease: [0.25, 0.46, 0.45, 0.94],
        }}
      >
        {cardContent}
      </motion.div>
    );
  }

  return cardContent;
}

// Sub-componentes
export interface GlassCardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Alineación del contenido */
  align?: 'start' | 'center' | 'between';
  /** Añadir separador inferior */
  divider?: boolean;
}

export function GlassCardHeader({
  className,
  align = 'between',
  divider = false,
  children,
  ...props
}: GlassCardHeaderProps) {
  const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    between: 'items-start sm:items-center justify-between',
  };

  return (
    <div
      className={cn(
        'flex flex-wrap gap-3 mb-4',
        alignClasses[align],
        divider && 'pb-4 border-b border-white/20 dark:border-white/10',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export interface GlassCardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  /** Nivel de heading */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  /** Tamaño del título */
  size?: 'sm' | 'default' | 'lg' | 'xl';
  /** Aplicar efecto de gradiente al texto */
  gradient?: boolean;
}

export function GlassCardTitle({
  className,
  as: Component = 'h2',
  size = 'default',
  gradient = false,
  children,
  ...props
}: GlassCardTitleProps) {
  const sizeClasses = {
    sm: 'text-sm font-semibold',
    default: 'text-base font-semibold',
    lg: 'text-lg font-semibold',
    xl: 'text-xl font-bold',
  };

  return (
    <Component
      className={cn(
        sizeClasses[size],
        'text-foreground tracking-tight',
        gradient &&
          'bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent',
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export interface GlassCardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Reducir espaciado */
  compact?: boolean;
}

export function GlassCardContent({
  className,
  compact = false,
  children,
  ...props
}: GlassCardContentProps) {
  return (
    <div className={cn('text-muted-foreground', !compact && 'space-y-3', className)} {...props}>
      {children}
    </div>
  );
}

export interface GlassCardFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Alineación del contenido */
  align?: 'start' | 'center' | 'end' | 'between';
  /** Añadir separador superior */
  divider?: boolean;
}

export function GlassCardFooter({
  className,
  align = 'between',
  divider = false,
  children,
  ...props
}: GlassCardFooterProps) {
  const alignClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
  };

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 mt-4',
        alignClasses[align],
        divider && 'pt-4 border-t border-white/20 dark:border-white/10',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// Variante especial con efecto de borde brillante
export interface GlassCardGlowProps extends Omit<GlassCardProps, 'glow' | 'variant'> {
  /** Color del glow */
  glowColor?: 'brand' | 'blue' | 'purple' | 'emerald' | 'amber';
}

export function GlassCardGlow({
  className,
  glowColor = 'brand',
  children,
  ...props
}: GlassCardGlowProps) {
  const glowColors = {
    brand: 'from-brand/20 to-brand/20',
    blue: 'from-info/20 to-info/20',
    purple: 'from-accent/20 to-accent/20',
    emerald: 'from-success/20 to-success/20',
    amber: 'from-warning/20 to-warning/20',
  };

  return (
    <div className={cn('relative group', className)}>
      {/* Efecto de glow animado */}
      <div
        className={cn(
          'absolute -inset-0.5 rounded-2xl bg-gradient-to-r opacity-0 group-hover:opacity-100 transition duration-500 blur',
          glowColors[glowColor]
        )}
      />
      <GlassCard variant="frosted" className="relative" {...props}>
        {children}
      </GlassCard>
    </div>
  );
}
