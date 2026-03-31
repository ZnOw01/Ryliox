import * as React from 'react';
import {
  Tooltip as TooltipPrimitive,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../primitives/Tooltip';

/**
 * Enhanced Tooltip Component - Radix UI Primitives (2025-2026)
 *
 * This is a backwards-compatible wrapper around the new Radix-based Tooltip primitive.
 * Maintains the same API as the original while providing improved accessibility.
 *
 * Migration path:
 * - Old: <Tooltip content="...">...</Tooltip>
 * - New: <Tooltip content="...">...</Tooltip> (same API, better a11y)
 *
 * For advanced use cases, use the primitives directly:
 * <TooltipProvider>
 *   <TooltipPrimitive>
 *     <TooltipTrigger>...</TooltipTrigger>
 *     <TooltipContent>...</TooltipContent>
 *   </TooltipPrimitive>
 * </TooltipProvider>
 *
 * Accessibility (WCAG 2.1 AAA):
 * - aria-describedby on trigger (automatic)
 * - role="tooltip" on content
 * - Keyboard dismissible (Escape)
 * - Focus management automático
 * - Collision detection para no salirse de viewport
 *
 * @example
 * // Basic usage (backwards compatible)
 * <Tooltip content="Helpful information">
 *   <button>Hover me</button>
 * </Tooltip>
 *
 * // With positioning
 * <Tooltip content="Delete" position="left">
 *   <button>Delete</button>
 * </Tooltip>
 */

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right';

export interface TooltipProps {
  /** Content to display in the tooltip */
  content: React.ReactNode;
  /** The element that triggers the tooltip */
  children: React.ReactElement<{ className?: string }>;
  /** Position of the tooltip relative to the trigger */
  position?: TooltipPosition;
  /** Delay before showing tooltip (in ms) */
  delay?: number;
  /** Additional CSS classes for the tooltip */
  className?: string;
  /** Disable the tooltip */
  disabled?: boolean;
  /** Maximum width of the tooltip */
  maxWidth?: number;
}

// Track if provider is already mounted
let providerMounted = false;

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className,
  disabled = false,
  maxWidth = 250,
}: TooltipProps) {
  if (disabled) {
    return children;
  }

  // Position mapping to Radix side
  const sideMap: Record<TooltipPosition, 'top' | 'bottom' | 'left' | 'right'> = {
    top: 'top',
    bottom: 'bottom',
    left: 'left',
    right: 'right',
  };

  const tooltipContent = (
    <TooltipPrimitive delayDuration={delay}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent
        side={sideMap[position]}
        sideOffset={4}
        showArrow={true}
        style={{ maxWidth }}
        className={className}
      >
        {content}
      </TooltipContent>
    </TooltipPrimitive>
  );

  // Only wrap with provider on first mount
  if (!providerMounted) {
    providerMounted = true;
    return <TooltipProvider>{tooltipContent}</TooltipProvider>;
  }

  return tooltipContent;
}

/**
 * TooltipProvider - Required wrapper for tooltips
 *
 * Should be placed at the root of your app or at a high level.
 * Only one provider is needed per app.
 *
 * @example
 * function App() {
 *   return (
 *     <TooltipProvider>
 *       <YourApp />
 *     </TooltipProvider>
 *   );
 * }
 */
export { TooltipProvider };

/**
 * Use this if you need direct access to Radix primitives
 */
export { TooltipPrimitive, TooltipContent, TooltipTrigger };
