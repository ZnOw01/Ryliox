import React, { useRef, useState, useCallback } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { cn } from '../../lib/cn';
import { cva, type VariantProps } from 'class-variance-authority';

/**
 * MagneticButton - Botón con efecto magnético de atracción al hover (2026)
 *
 * Características:
 * - Efecto magnético que atrae el cursor al acercarse
 * - Ripple effects en click
 * - Spring physics para animaciones suaves
 * - Soporta diferentes variantes y tamaños
 * - Fully accessible
 *
 * @example
 * ```tsx
 * // Botón magnético básico
 * <MagneticButton>Click me</MagneticButton>
 *
 * // Con fuerza personalizada
 * <MagneticButton strength={0.8} radius={150}>
 *   Fuerte atracción
 * </MagneticButton>
 *
 * // Con ripple effect
 * <MagneticButton ripple variant="primary">
 *   Con ondas
 * </MagneticButton>
 *
 * // Variante neobrutalist
 * <MagneticButton variant="brutalist" strength={0.3}>
 *   Bold Design
 * </MagneticButton>
 * ```
 */

const magneticButtonVariants = cva(
  'relative inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-60 overflow-hidden',
  {
    variants: {
      variant: {
        primary: 'bg-brand text-white shadow-sm hover:bg-brand-deep focus:ring-brand',
        secondary:
          'border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50 focus:ring-slate-400 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200',
        ghost:
          'bg-transparent text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus:ring-slate-400 dark:text-slate-300 dark:hover:bg-slate-800',
        glass:
          'bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border border-white/20 dark:border-white/10 text-slate-900 dark:text-slate-100 hover:bg-white/90 dark:hover:bg-slate-900/90',
        neon: 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)]',
        brutalist:
          'bg-white dark:bg-slate-900 border-[3px] border-slate-900 dark:border-white text-slate-900 dark:text-white font-bold shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)] hover:translate-x-[2px] hover:translate-y-[2px]',
      },
      size: {
        sm: 'px-3 py-1.5 text-xs rounded-lg',
        default: 'px-4 py-2 text-sm rounded-xl',
        md: 'px-5 py-2.5 text-sm rounded-xl',
        lg: 'px-6 py-3 text-base rounded-2xl',
        xl: 'px-8 py-4 text-lg rounded-2xl',
        icon: 'h-10 w-10 rounded-xl',
      },
      fullWidth: {
        true: 'w-full',
        false: '',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
      fullWidth: false,
    },
  }
);

export interface MagneticButtonProps
  extends
    Omit<
      React.ButtonHTMLAttributes<HTMLButtonElement>,
      'onAnimationStart' | 'onDragStart' | 'onDrag' | 'onDragEnd'
    >,
    VariantProps<typeof magneticButtonVariants> {
  /** Fuerza del efecto magnético (0-1) */
  strength?: number;
  /** Radio de atracción en píxeles */
  radius?: number;
  /** Activar ripple effect en click */
  ripple?: boolean;
  /** Si el contenido se mueve con el efecto */
  moveContent?: boolean;
  /** Icono izquierdo */
  icon?: React.ReactNode;
  /** Icono derecho */
  iconRight?: React.ReactNode;
  /** Estado de carga */
  isLoading?: boolean;
  /** Clases adicionales */
  className?: string;
}

interface Ripple {
  id: number;
  x: number;
  y: number;
}

export function MagneticButton({
  children,
  className,
  variant,
  size,
  fullWidth,
  strength = 0.3,
  radius = 100,
  ripple = true,
  moveContent = true,
  icon,
  iconRight,
  isLoading = false,
  disabled,
  onClick,
  ...props
}: MagneticButtonProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const rippleId = useRef(0);

  // Motion values para el efecto magnético
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  // Spring config para suavidad
  const springConfig = { stiffness: 150, damping: 15, mass: 0.1 };
  const springX = useSpring(x, springConfig);
  const springY = useSpring(y, springConfig);

  // Transformar el movimiento para el contenido (efecto opuesto sutil)
  const contentX = useTransform(springX, val => val * 0.2);
  const contentY = useTransform(springY, val => val * 0.2);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      if (!buttonRef.current || disabled) return;

      const rect = buttonRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const distanceX = e.clientX - centerX;
      const distanceY = e.clientY - centerY;

      const distance = Math.sqrt(distanceX ** 2 + distanceY ** 2);

      if (distance < radius) {
        const factor = (1 - distance / radius) * strength;
        x.set(distanceX * factor);
        y.set(distanceY * factor);
      }
    },
    [radius, strength, x, y, disabled]
  );

  const handleMouseLeave = useCallback(() => {
    x.set(0);
    y.set(0);
  }, [x, y]);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      if (ripple && buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const newRipple: Ripple = {
          id: rippleId.current++,
          x,
          y,
        };

        setRipples(prev => [...prev, newRipple]);

        // Remover ripple después de la animación
        setTimeout(() => {
          setRipples(prev => prev.filter(r => r.id !== newRipple.id));
        }, 600);
      }

      onClick?.(e);
    },
    [ripple, onClick]
  );

  const isDisabled = disabled || isLoading;

  return (
    <motion.button
      ref={buttonRef}
      className={cn(magneticButtonVariants({ variant, size, fullWidth }), className)}
      style={{
        x: springX,
        y: springY,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      disabled={isDisabled}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      {...props}
    >
      {/* Ripple effects */}
      {ripples.map(ripple => (
        <span
          key={ripple.id}
          className="absolute rounded-full bg-white/30 pointer-events-none animate-ripple"
          style={{
            left: ripple.x,
            top: ripple.y,
            transform: 'translate(-50%, -50%)',
          }}
        />
      ))}

      {/* Contenido que se mueve sutilmente */}
      <motion.span
        className="flex items-center gap-2"
        style={moveContent ? { x: contentX, y: contentY } : undefined}
      >
        {isLoading ? (
          <>
            <svg
              className="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            {children}
          </>
        ) : (
          <>
            {icon && <span className="shrink-0">{icon}</span>}
            {children}
            {iconRight && <span className="shrink-0">{iconRight}</span>}
          </>
        )}
      </motion.span>
    </motion.button>
  );
}

/**
 * MagneticIconButton - Versión solo icono
 */
export interface MagneticIconButtonProps extends Omit<
  MagneticButtonProps,
  'icon' | 'iconRight' | 'children' | 'size'
> {
  /** El icono a mostrar */
  icon: React.ReactNode;
  /** Label accesible (requerido para icon-only) */
  'aria-label': string;
  /** Tamaño del icono */
  size?: 'sm' | 'default' | 'lg';
}

export function MagneticIconButton({
  icon,
  size = 'default',
  className,
  ...props
}: MagneticIconButtonProps) {
  const sizeMap = {
    sm: 'h-8 w-8',
    default: 'h-10 w-10',
    lg: 'h-12 w-12',
  };

  return (
    <MagneticButton className={cn('p-0', sizeMap[size], className)} {...props}>
      {icon}
    </MagneticButton>
  );
}

/**
 * MagneticGroup - Grupo de botones magnéticos
 */
export interface MagneticGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Espaciado entre botones */
  gap?: 2 | 3 | 4;
  /** Alineación */
  align?: 'start' | 'center' | 'end';
}

export function MagneticGroup({
  children,
  gap = 3,
  align = 'center',
  className,
  ...props
}: MagneticGroupProps) {
  const gapClasses = {
    2: 'gap-2',
    3: 'gap-3',
    4: 'gap-4',
  };

  const alignClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
  };

  return (
    <div
      className={cn('flex flex-wrap', gapClasses[gap], alignClasses[align], className)}
      {...props}
    >
      {children}
    </div>
  );
}
