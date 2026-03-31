/**
 * Radix UI Tooltip Primitive Component
 *
 * Implements Radix UI Tooltip primitive with Context7 patterns:
 * - Provider, Root, Trigger, Portal, Content, Arrow
 * - Proper positioning con side, align, collision detection
 * - Delay configurable (openDelay, closeDelay)
 * - Focus management automático
 * - Keyboard shortcuts: Space/Enter sobre trigger, Escape
 *
 * Accessibility (WCAG 2.1 AAA):
 * - aria-describedby="{tooltip-id}" en trigger (apunta al content)
 * - role="tooltip" en content
 * - Solo visible cuando el trigger tiene hover o focus
 * - No interactivo (no puede contener elementos focusables)
 * - Dismissible (Escape, click elsewhere)
 *
 * Keyboard Navigation:
 * - Focus trigger: Tooltip se muestra
 * - Escape: Tooltip se oculta
 * - Tab away from trigger: Tooltip se oculta
 *
 * Nota: Tooltip NO debe contener elementos interactivos.
 * Para contenido interactivo, usar Popover en lugar de Tooltip.
 *
 * @example
 * <TooltipProvider>
 *   <Tooltip>
 *     <TooltipTrigger>Hover me</TooltipTrigger>
 *     <TooltipContent>
 *       <p>This is a tooltip</p>
 *     </TooltipContent>
 *   </Tooltip>
 * </TooltipProvider>
 */

import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import * as React from 'react';
import { cn } from '@/lib/cn';

const TooltipProvider = TooltipPrimitive.Provider;

/**
 * Tooltip - Componente root del tooltip
 *
 * Props:
 * - open: boolean (controlled)
 * - defaultOpen: boolean (uncontrolled)
 * - onOpenChange: (open: boolean) => void
 * - delayDuration: number (ms, default: 700)
 * - disableHoverableContent: boolean (default: false)
 */
const Tooltip = TooltipPrimitive.Root;

/**
 * TooltipTrigger - Elemento que activa el tooltip
 *
 * ARIA automáticos:
 * - aria-describedby="{tooltip-id}" (apunta al content)
 * - Puede ser cualquier elemento focusable o con hover
 *
 * @param asChild - Renderizar children directamente sin wrapper (default: false)
 */
const TooltipTrigger = TooltipPrimitive.Trigger;

/**
 * TooltipContent - Contenido del tooltip
 *
 * Props de posicionamiento:
 * - side: "top" | "right" | "bottom" | "left" (default: "top")
 * - sideOffset: pixels offset (default: 4)
 * - align: "start" | "center" | "end" (default: "center")
 * - alignOffset: pixels offset (default: 0)
 * - avoidCollisions: boolean (default: true)
 * - collisionPadding: number | Padding (default: 0)
 * - arrowPadding: number (default: 0)
 * - sticky: "always" | "partial" | "none" (default: "partial")
 * - hideWhenDetached: boolean (default: false)
 *
 * Data Attributes:
 * - data-state: "instant-open" | "delayed-open" | "closed"
 * - data-side: "left" | "right" | "bottom" | "top"
 * - data-align: "start" | "end" | "center"
 *
 * ARIA:
 * - role="tooltip"
 * - id automático para aria-describedby
 */
const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> & {
    /** Mostrar flecha del tooltip */
    showArrow?: boolean;
  }
>(({ className, sideOffset = 4, showArrow = true, children, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 overflow-hidden rounded-md bg-gray-900 px-3 py-1.5',
        'text-xs text-gray-50',
        'animate-in fade-in-0 zoom-in-95',
        'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
        'data-[state=closed]:zoom-out-95 data-[state=closed]:duration-300',
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      {...props}
    >
      {children}
      {showArrow && <TooltipPrimitive.Arrow className="fill-gray-900" width={8} height={4} />}
    </TooltipPrimitive.Content>
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

/**
 * TooltipArrow - Flecha del tooltip
 *
 * @param width - Ancho de la flecha
 * @param height - Alto de la flecha
 */
const TooltipArrow = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Arrow>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Arrow>
>(({ className, width = 8, height = 4, ...props }, ref) => (
  <TooltipPrimitive.Arrow
    ref={ref}
    width={width}
    height={height}
    className={cn('fill-gray-900', className)}
    {...props}
  />
));
TooltipArrow.displayName = TooltipPrimitive.Arrow.displayName;

export { Tooltip, TooltipArrow, TooltipContent, TooltipProvider, TooltipTrigger };
