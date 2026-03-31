import { cn } from '../../lib/cn';

/**
 * Skeleton loading placeholder component.
 * Provides visual feedback during content loading states.
 *
 * @example
 * ```tsx
 * // Simple skeleton
 * <Skeleton className="h-4 w-[200px]" />
 *
 * // Card skeleton with multiple elements
 * <div className="space-y-3">
 *   <Skeleton className="h-5 w-3/4" />
 *   <Skeleton className="h-4 w-full" />
 *   <Skeleton className="h-4 w-2/3" />
 * </div>
 * ```
 */

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Show shimmer animation effect */
  shimmer?: boolean;
}

export function Skeleton({ className, shimmer = true, ...props }: SkeletonProps) {
  return (
    <div
      className={cn('rounded-md bg-slate-200', shimmer && 'animate-pulse', className)}
      {...props}
    />
  );
}

/**
 * Pre-built skeleton layouts for common patterns
 */

export function TextSkeleton({
  lines = 1,
  className,
  lastLineWidth = '75%',
}: {
  lines?: number;
  className?: string;
  lastLineWidth?: string;
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn('h-4', i === lines - 1 ? lastLineWidth : 'w-full')} />
      ))}
    </div>
  );
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-slate-200 bg-white p-4', className)}>
      <div className="flex gap-3">
        <Skeleton className="h-16 w-12 shrink-0 rounded-md" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
    </div>
  );
}

export function ListSkeleton({ count = 3, className }: { count?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-lg" />
      ))}
    </div>
  );
}
