import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

/**
 * Badge component for displaying status indicators, labels, and counts.
 *
 * @example
 * ```tsx
 * <Badge variant="default">New</Badge>
 * <Badge variant="success" size="lg">Completed</Badge>
 * <Badge variant="outline" className="ml-2">Draft</Badge>
 * ```
 */

const badgeVariants = cva(
  'inline-flex items-center justify-center gap-1.5 font-medium leading-tight transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'bg-brand/10 text-brand-deep border border-brand/20',
        secondary: 'bg-muted text-muted-foreground border border-border',
        success: 'bg-success/10 text-success border border-success/20',
        warning: 'bg-warning/10 text-warning border border-warning/20',
        error: 'bg-destructive/10 text-destructive border border-destructive/20',
        info: 'bg-info/10 text-info border border-info/20',
        outline: 'bg-transparent border border-border text-foreground',
        ghost: 'bg-transparent text-muted-foreground hover:bg-accent',
      },
      size: {
        sm: 'px-2 py-0.5 text-xs rounded-md',
        default: 'px-2.5 py-1 text-xs rounded-full',
        lg: 'px-3 py-1 text-sm rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  /** Dot indicator for animated status */
  pulse?: boolean;
  /** Icon element to display before text */
  icon?: React.ReactNode;
}

export function Badge({
  className,
  variant,
  size,
  pulse = false,
  icon,
  children,
  ...props
}: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, size }), className)} {...props}>
      {pulse && (
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            variant === 'success' && 'bg-success',
            variant === 'warning' && 'bg-warning',
            variant === 'error' && 'bg-destructive',
            variant === 'default' && 'bg-brand',
            variant === 'info' && 'bg-info',
            (variant === 'secondary' || variant === 'outline' || variant === 'ghost') &&
              'bg-muted-foreground',
            pulse && 'animate-pulse'
          )}
        />
      )}
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
}
