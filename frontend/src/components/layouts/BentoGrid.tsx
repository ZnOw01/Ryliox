import React from 'react';
import { cn } from '../../lib/cn';
import { motion } from 'framer-motion';

/**
 * BentoGrid - Layout tipo grid irregular (Apple Style) (2026)
 *
 * Características:
 * - Grid irregular con celdas de diferentes tamaños
 * - Masonry-like layout
 * - Responsive que se adapta a mobile
 * - Soporta glassmorphism en las celdas
 * - Animaciones de entrada staggered
 *
 * @example
 * ```tsx
 * // Layout bento básico
 * <BentoGrid>
 *   <BentoItem colSpan={2} rowSpan={2}>
 *     <FeaturedCard />
 *   </BentoItem>
 *   <BentoItem>
 *     <SmallCard1 />
 *   </BentoItem>
 *   <BentoItem>
 *     <SmallCard2 />
 *   </BentoItem>
 *   <BentoItem colSpan={2}>
 *     <WideCard />
 *   </BentoItem>
 * </BentoGrid>
 *
 * // Con animaciones
 * <BentoGrid animated staggerDelay={0.1}>
 *   {items.map((item, i) => (
 *     <BentoItem key={i} animationDelay={i * 0.1}>
 *       <Card data={item} />
 *     </BentoItem>
 *   ))}
 * </BentoGrid>
 *
 * // Variante masonry
 * <BentoGrid variant="masonry" columns={3} gap={6}>
 *   {cards.map((card) => (
 *     <BentoItem key={card.id}>
 *       <Card height={card.height} />
 *     </BentoItem>
 *   ))}
 * </BentoGrid>
 * ```
 */

export interface BentoGridProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Variante del grid */
  variant?: 'default' | 'masonry' | 'featured' | 'compact';
  /** Número de columnas */
  columns?: 2 | 3 | 4 | 5 | 'auto';
  /** Espaciado entre items */
  gap?: 2 | 3 | 4 | 5 | 6 | 8;
  /** Animar items al montar */
  animated?: boolean;
  /** Delay entre animaciones (segundos) */
  staggerDelay?: number;
  /** Altura mínima de filas */
  minRowHeight?: number;
  /** Clases adicionales */
  className?: string;
}

export function BentoGrid({
  children,
  variant = 'default',
  columns = 3,
  gap = 4,
  animated = false,
  staggerDelay = 0.05,
  minRowHeight,
  className,
  ...props
}: BentoGridProps) {
  const gapClasses = {
    2: 'gap-2',
    3: 'gap-3',
    4: 'gap-4',
    5: 'gap-5',
    6: 'gap-6',
    8: 'gap-8',
  };

  const columnClasses = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5',
    auto: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-fr',
  };

  const variantClasses = {
    default: '',
    masonry: 'grid-flow-dense',
    featured: 'grid-cols-1 sm:grid-cols-3 lg:grid-cols-4',
    compact: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6',
  };

  // Si es animated, envolver children con motion
  const animatedChildren = animated
    ? React.Children.map(children, (child, index) => {
        if (React.isValidElement(child) && child.type === BentoItem) {
          return React.cloneElement(child as React.ReactElement<BentoItemProps>, {
            animated: true,
            animationDelay: index * staggerDelay,
          });
        }
        return child;
      })
    : children;

  return (
    <div
      className={cn(
        'grid',
        variant === 'masonry' ? 'grid-flow-dense' : '',
        variant === 'featured'
          ? variantClasses.featured
          : variant === 'compact'
            ? variantClasses.compact
            : columnClasses[columns],
        gapClasses[gap],
        className
      )}
      style={minRowHeight ? { gridAutoRows: `${minRowHeight}px` } : undefined}
      {...props}
    >
      {animatedChildren}
    </div>
  );
}

export interface BentoItemProps extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  'onAnimationStart' | 'onDragStart' | 'onDrag' | 'onDragEnd'
> {
  /** Número de columnas que ocupa */
  colSpan?: 1 | 2 | 3 | 4 | 'full';
  /** Número de filas que ocupa */
  rowSpan?: 1 | 2 | 3 | 4;
  /** Orden en mobile (para reordenar) */
  mobileOrder?: number;
  /** Animar item */
  animated?: boolean;
  /** Delay de animación (segundos) */
  animationDelay?: number;
  /** Tipo de animación */
  animationType?: 'fade' | 'slide' | 'scale' | 'bounce';
}

export function BentoItem({
  children,
  colSpan = 1,
  rowSpan,
  mobileOrder,
  animated = false,
  animationDelay = 0,
  animationType = 'fade',
  className,
  ...props
}: BentoItemProps) {
  const colSpanClasses = {
    1: '',
    2: 'sm:col-span-2',
    3: 'sm:col-span-2 lg:col-span-3',
    4: 'sm:col-span-2 lg:col-span-4',
    full: 'col-span-full',
  };

  const rowSpanClasses = {
    1: '',
    2: 'row-span-2',
    3: 'row-span-3',
    4: 'row-span-4',
  };

  const variants = {
    fade: {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
    },
    slide: {
      initial: { opacity: 0, y: 20 },
      animate: { opacity: 1, y: 0 },
    },
    scale: {
      initial: { opacity: 0, scale: 0.9 },
      animate: { opacity: 1, scale: 1 },
    },
    bounce: {
      initial: { opacity: 0, scale: 0.8 },
      animate: { opacity: 1, scale: 1 },
    },
  };

  const transition = {
    duration: 0.4,
    delay: animationDelay,
    ease: 'easeOut' as const,
  };

  const content = (
    <div
      className={cn(
        'h-full',
        colSpanClasses[colSpan],
        rowSpan && rowSpanClasses[rowSpan],
        mobileOrder !== undefined && `order-${mobileOrder}`,
        className
      )}
      style={mobileOrder !== undefined ? { order: mobileOrder } : undefined}
      {...props}
    >
      {children}
    </div>
  );

  if (animated) {
    return (
      <motion.div
        initial={variants[animationType].initial}
        animate={variants[animationType].animate}
        transition={transition}
        className={cn(
          'h-full',
          colSpanClasses[colSpan],
          rowSpan && rowSpanClasses[rowSpan],
          className
        )}
        style={mobileOrder !== undefined ? { order: mobileOrder } : undefined}
        {...props}
      >
        {children}
      </motion.div>
    );
  }

  return content;
}

/**
 * BentoFeatured - Item destacado que ocupa más espacio
 */
export interface BentoFeaturedProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Posición del item destacado */
  position?: 'left' | 'right' | 'top' | 'center';
  /** Tamaño del item */
  size?: 'large' | 'medium' | 'small';
}

export function BentoFeatured({
  children,
  position = 'left',
  size = 'large',
  className,
  ...props
}: BentoFeaturedProps) {
  const positionClasses = {
    left: 'sm:col-span-2 sm:row-span-2 lg:col-span-2 lg:row-span-2',
    right: 'sm:col-span-2 sm:row-span-2 lg:col-span-2 lg:row-span-2 sm:col-start-1 lg:col-start-3',
    top: 'col-span-full sm:col-span-3 lg:col-span-4',
    center: 'sm:col-span-2 sm:row-span-2 lg:col-start-2',
  };

  return (
    <div className={cn('h-full', positionClasses[position], className)} {...props}>
      {children}
    </div>
  );
}

/**
 * BentoSection - Agrupa items con título
 */
export interface BentoSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Título de la sección */
  title?: string;
  /** Descripción de la sección */
  description?: string;
  /** Número de columnas del grid interno */
  columns?: 2 | 3 | 4;
  /** Espaciado */
  gap?: 2 | 3 | 4 | 5 | 6;
}

export function BentoSection({
  title,
  description,
  children,
  columns = 3,
  gap = 4,
  className,
  ...props
}: BentoSectionProps) {
  return (
    <div className={cn('space-y-4', className)} {...props}>
      {(title || description) && (
        <div className="space-y-1">
          {title && (
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
          )}
          {description && (
            <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
          )}
        </div>
      )}
      <BentoGrid columns={columns} gap={gap}>
        {children}
      </BentoGrid>
    </div>
  );
}
