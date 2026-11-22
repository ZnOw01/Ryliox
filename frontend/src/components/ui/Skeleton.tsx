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
