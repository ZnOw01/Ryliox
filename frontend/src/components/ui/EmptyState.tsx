import { cn } from '../../lib/cn';
import type { Icon as PhosphorIcon } from '@phosphor-icons/react';
import { MagnifyingGlass, FileX, FolderOpen, WifiSlash } from '@phosphor-icons/react';

/**
 * Empty state component for displaying when no content is available.
 * Provides visual feedback and optional action buttons.
 *
 * @example
 * ```tsx
 * // Simple empty state
 * <EmptyState
 *   icon="search"
 *   title="No results found"
 *   description="Try adjusting your search terms."
 * />
 *
 * // With action button
 * <EmptyState
 *   icon="folder"
 *   title="No books selected"
 *   description="Search for a book to get started."
 *   action={{
 *     label: "Search Books",
 *     onClick: () => setSearchOpen(true)
 *   }}
 * />
 * ```
 */

const iconMap: Record<string, PhosphorIcon> = {
  search: MagnifyingGlass,
  file: FileX,
  folder: FolderOpen,
  offline: WifiSlash,
};

export interface EmptyStateProps {
  /** Phosphor icon component or icon name string */
  icon?: PhosphorIcon | keyof typeof iconMap;
  /** Main title text */
  title: string;
  /** Secondary description text */
  description?: string;
  /** Optional action button configuration */
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary';
  };
  /** Visual style variant */
  variant?: 'default' | 'compact' | 'inline';
  /** Additional CSS classes */
  className?: string;
}

export function EmptyState({
  icon: IconProp,
  title,
  description,
  action,
  variant = 'default',
  className,
}: EmptyStateProps) {
  const Icon: PhosphorIcon | null =
    typeof IconProp === 'string' ? iconMap[IconProp] || MagnifyingGlass : IconProp || null;

  const variants = {
    default: 'py-8 px-4',
    compact: 'py-6 px-4',
    inline: 'py-3',
  };

  const iconSizes = {
    default: 'h-12 w-12',
    compact: 'h-8 w-8',
    inline: 'h-5 w-5',
  };

  return (
    <div className={cn('flex flex-col items-center text-center', variants[variant], className)}>
      {Icon && (
        <div
          className={cn(
            'mb-4 rounded-full bg-muted p-3 text-muted-foreground',
            variant === 'compact' && 'mb-3 p-2',
            variant === 'inline' && 'mb-2 p-1.5'
          )}
        >
          <Icon className={cn(iconSizes[variant])} weight="regular" />
        </div>
      )}

      <h3
        className={cn(
          'font-semibold text-foreground leading-tight',
          variant === 'default' && 'text-base',
          variant === 'compact' && 'text-sm',
          variant === 'inline' && 'text-sm'
        )}
      >
        {title}
      </h3>

      {description && (
        <p
          className={cn(
            'mt-2 text-muted-foreground leading-relaxed',
            variant === 'default' && 'text-sm max-w-[280px]',
            variant === 'compact' && 'text-xs max-w-[220px]',
            variant === 'inline' && 'text-xs'
          )}
        >
          {description}
        </p>
      )}

      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className={cn(
            'mt-4 rounded-lg px-4 py-2.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2',
            action.variant === 'primary' || !action.variant
              ? 'bg-primary text-primary-foreground hover:bg-primary/90 focus:ring-primary'
              : 'border border-border bg-background text-foreground hover:bg-accent focus:ring-ring'
          )}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
