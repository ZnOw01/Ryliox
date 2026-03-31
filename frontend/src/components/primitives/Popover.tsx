/**
 * Radix UI Popover Primitive Component
 *
 * Implements Radix UI Popover primitive with Context7 patterns:
 * - Root, Trigger, Anchor, Portal, Content, Close, Arrow
 * - Proper positioning con side, align, collision detection
 * - Focus management automático
 * - Keyboard shortcuts: Escape
 *
 * Accessibility (WCAG 2.1 AAA):
 * - aria-expanded="true|false" en trigger según estado
 * - aria-haspopup="dialog"
 * - aria-controls="{content-id}" en trigger
 * - role="dialog" en content
 * - aria-modal="false" (non-modal by default)
 * - Keyboard: Escape para cerrar
 * - Focus se mueve al primer elemento focusable en content
 * - Focus se restaura al trigger al cerrar
 *
 * Keyboard Navigation:
 * - Escape: Cerrar popover
 * - Tab: Navegar dentro del popover
 * - Click outside: Cerrar popover
 *
 * @example
 * <Popover>
 *   <PopoverTrigger>Trigger</PopoverTrigger>
 *   <PopoverContent>
 *     <PopoverClose>Close</PopoverClose>
 *   </PopoverContent>
 * </Popover>
 */

import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { X } from '@phosphor-icons/react';

const Popover = PopoverPrimitive.Root;

const PopoverTrigger = PopoverPrimitive.Trigger;

const PopoverAnchor = PopoverPrimitive.Anchor;

const PopoverPortal = PopoverPrimitive.Portal;

const PopoverClose = PopoverPrimitive.Close;

/**
 * PopoverContent - Contenido del popover
 *
 * Props de posicionamiento (según Context7 patterns):
 * - side: "top" | "right" | "bottom" | "left" (default: "bottom")
 * - sideOffset: pixels offset (default: 4)
 * - align: "start" | "center" | "end" (default: "center")
 * - alignOffset: pixels offset (default: 0)
 * - avoidCollisions: boolean (default: true)
 * - collisionBoundary: Boundary (default: [])
 * - collisionPadding: number | Padding (default: 0)
 * - arrowPadding: number (default: 0)
 * - sticky: "always" | "partial" | "none" (default: "partial")
 * - hideWhenDetached: boolean (default: false)
 *
 * Props de comportamiento:
 * - onOpenAutoFocus: callback cuando se abre
 * - onCloseAutoFocus: callback cuando se cierra
 * - onEscapeKeyDown: callback cuando se presiona Escape
 * - onPointerDownOutside: callback cuando se hace click fuera
 * - onFocusOutside: callback cuando el focus sale
 * - onInteractOutside: callback cuando hay interacción fuera
 * - forceMount: boolean (default: false)
 *
 * CSS Variables automáticos:
 * --radix-popover-content-transform-origin
 * --radix-popover-content-available-width
 * --radix-popover-content-available-height
 * --radix-popover-trigger-width
 * --radix-popover-trigger-height
 *
 * Data Attributes:
 * - data-state: "open" | "closed"
 * - data-side: "left" | "right" | "bottom" | "top"
 * - data-align: "start" | "end" | "center"
 */
interface PopoverContentProps extends React.ComponentPropsWithoutRef<
  typeof PopoverPrimitive.Content
> {
  /** Mostrar botón de cerrar (X) en la esquina */
  showCloseButton?: boolean;
  /** Mostrar flecha del popover */
  showArrow?: boolean;
}

const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  PopoverContentProps
>(
  (
    {
      className,
      align = 'center',
      sideOffset = 4,
      showCloseButton = false,
      showArrow = false,
      children,
      ...props
    },
    ref
  ) => (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 w-72 rounded-md border bg-white p-4 text-gray-900 shadow-md',
          'outline-none',
          'data-[state=open]:animate-in data-[state=closed]:animate-out',
          'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
          'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          'data-[side=bottom]:slide-in-from-top-2',
          'data-[side=left]:slide-in-from-right-2',
          'data-[side=right]:slide-in-from-left-2',
          'data-[side=top]:slide-in-from-bottom-2',
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <PopoverPrimitive.Close
            className={cn(
              'absolute right-2 top-2 rounded-sm opacity-70',
              'ring-offset-white transition-opacity',
              'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-offset-2',
              'focus-visible:ring-blue-500',
              'disabled:pointer-events-none'
            )}
            aria-label="Close"
          >
            <X className="h-4 w-4" weight="regular" aria-hidden="true" />
          </PopoverPrimitive.Close>
        )}
        {showArrow && <PopoverPrimitive.Arrow className="fill-white" width={12} height={6} />}
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  )
);
PopoverContent.displayName = PopoverPrimitive.Content.displayName;

/**
 * PopoverArrow - Flecha del popover
 *
 * @param width - Ancho de la flecha (default: 10)
 * @param height - Alto de la flecha (default: 5)
 * @param asChild - Renderizar como child element
 */
const PopoverArrow = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Arrow>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Arrow>
>(({ className, width = 12, height = 6, ...props }, ref) => (
  <PopoverPrimitive.Arrow
    ref={ref}
    width={width}
    height={height}
    className={cn('fill-white', className)}
    {...props}
  />
));
PopoverArrow.displayName = PopoverPrimitive.Arrow.displayName;

export {
  Popover,
  PopoverAnchor,
  PopoverArrow,
  PopoverClose,
  PopoverContent,
  PopoverPortal,
  PopoverTrigger,
};
