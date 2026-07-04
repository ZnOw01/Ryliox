import { cn } from '../../lib/cn';

/**
 * Loading spinner component with multiple sizes and variants.
 * Provides visual feedback for loading states.
 *
 * @example
 * ```tsx
 * // Default spinner
 * <LoadingSpinner />
 *
 * // With label
 * <LoadingSpinner label="Loading..." />
 *
 * // Different sizes
 * <LoadingSpinner size="sm" />
 * <LoadingSpinner size="lg" />
 *
 * // Different variants
 * <LoadingSpinner variant="brand" />
 * <LoadingSpinner variant="white" />
 * ```
 */

export interface LoadingSpinnerProps {
  /** Size variant of the spinner */
  size?: 'xs' | 'sm' | 'default' | 'md' | 'lg' | 'xl';
  /** Color variant */
  variant?: 'default' | 'brand' | 'white' | 'subtle';
  /** Optional label text to display below spinner */
  label?: string;
  /** Additional CSS classes */
  className?: string;
  /** Center the spinner in its container */
  centered?: boolean;
  /** Full screen overlay spinner */
  overlay?: boolean;
  /** Add backdrop blur effect */
  blur?: boolean;
}

const sizeClasses = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  default: 'h-5 w-5',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-12 w-12',
};

const strokeWidths = {
  xs: 3,
  sm: 3,
  default: 3,
  md: 3,
  lg: 3,
  xl: 2,
};

const variantClasses = {
  default: 'text-slate-400',
  brand: 'text-brand',
  white: 'text-white',
  subtle: 'text-slate-300',
};

export function LoadingSpinner({
  size = 'default',
  variant = 'default',
  label,
  className,
  centered = false,
  overlay = false,
  blur = false,
}: LoadingSpinnerProps) {
  const spinner = (
    <svg
      className={cn('animate-spin', sizeClasses[size], variantClasses[variant], className)}
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
        strokeWidth={strokeWidths[size]}
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );

  const content = (
    <>
      {spinner}
      {label && (
        <span
          className={cn(
            'mt-2 text-sm font-medium',
            variant === 'white' ? 'text-white' : 'text-slate-600'
          )}
        >
          {label}
        </span>
      )}
    </>
  );

  if (overlay) {
    return (
      <div
        className={cn(
          'fixed inset-0 z-50 flex flex-col items-center justify-center',
          blur ? 'backdrop-blur-sm bg-white/50' : 'bg-white/80'
        )}
        role="status"
        aria-live="polite"
        aria-label={label || 'Loading'}
      >
        {content}
      </div>
    );
  }

  if (centered) {
    return (
      <div
        className="flex flex-col items-center justify-center py-8"
        role="status"
        aria-live="polite"
        aria-label={label || 'Loading'}
      >
        {content}
      </div>
    );
  }

  return (
    <span
      className="inline-flex flex-col items-center"
      role="status"
      aria-live="polite"
      aria-label={label || 'Loading'}
    >
      {content}
    </span>
  );
}

/**
 * Inline loading indicator - small spinner for inline use
 */

export function InlineLoading({
  className,
  size = 'sm',
}: {
  className?: string;
  size?: 'xs' | 'sm' | 'default';
}) {
  return (
    <span className={cn('inline-flex items-center', className)}>
      <LoadingSpinner size={size} className="mr-2" />
      <span className="text-sm text-slate-600">Loading...</span>
    </span>
  );
}

/**
 * Skeleton loader wrapper with shimmer effect
 */

export function SkeletonLoader({
  children,
  className,
  isLoading,
}: {
  children: React.ReactNode;
  className?: string;
  isLoading: boolean;
}) {
  if (!isLoading) {
    return <>{children}</>;
  }

  return (
    <div className={cn('animate-pulse', className)}>
      <div className="opacity-0">{children}</div>
    </div>
  );
}

/**
 * Full page loading screen
 */

export function PageLoader({
  title = 'Loading...',
  subtitle,
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center">
      <LoadingSpinner size="xl" variant="brand" />
      <h2 className="mt-4 text-lg font-semibold text-slate-900">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
    </div>
  );
}
