import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { X } from '@phosphor-icons/react';

/**
 * Radix UI Dialog Primitive Component
 *
 * Implements Radix UI Dialog primitive with proper structure following Context7 patterns:
 * - Root, Trigger, Portal, Overlay, Content, Title, Description, Close
 * - Automatic ARIA attributes (aria-labelledby, aria-describedby, role="dialog")
 * - Focus trapping integrado via Radix
 * - Escape key handling for closing
 * - Click outside to close
 *
 * Accessibility (WCAG 2.1 AAA):
 * - aria-modal="true" cuando está activo
 * - Focus se mueve automáticamente al primer elemento focusable
 * - Focus se restaura al elemento que abrió el diálogo
 * - role="dialog" para semántica correcta
 *
 * @example
 * <Dialog>
 *   <DialogTrigger>Open Dialog</DialogTrigger>
 *   <DialogContent>
 *     <DialogHeader>
 *       <DialogTitle>Title</DialogTitle>
 *       <DialogDescription>Description</DialogDescription>
 *     </DialogHeader>
 *     <DialogFooter>
 *       <DialogClose>Cancel</DialogClose>
 *     </DialogFooter>
 *   </DialogContent>
 * </Dialog>
 */

const Dialog = DialogPrimitive.Root;

const DialogTrigger = DialogPrimitive.Trigger;

const DialogPortal = DialogPrimitive.Portal;

const DialogClose = DialogPrimitive.Close;

/**
 * DialogOverlay - El fondo semitransparente del diálogo
 *
 * Animación: fade in/out
 * ARIA: role="presentation" ya que es decorativo
 */
const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/60 backdrop-blur-sm',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className
    )}
    {...props}
    role="presentation"
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

interface DialogContentProps extends React.ComponentPropsWithoutRef<
  typeof DialogPrimitive.Content
> {
  /** Tamaño del diálogo: sm | md | lg | xl | full */
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  /** Mostrar botón de cerrar (X) */
  showCloseButton?: boolean;
  /** Callback cuando el diálogo se abre automáticamente */
  onOpenAutoFocus?: (event: Event) => void;
  /** Callback cuando el diálogo se cierra */
  onCloseAutoFocus?: (event: Event) => void;
}

/**
 * DialogContent - Contenedor principal del diálogo
 *
 * Props adicionales:
 * - onEscapeKeyDown: Callback cuando se presiona Escape
 * - onPointerDownOutside: Callback cuando se hace click fuera
 * - onInteractOutside: Callback cuando hay interacción fuera
 *
 * ARIA automáticos via Radix:
 * - aria-labelledby="{title-id}"
 * - aria-describedby="{description-id}"
 * - role="dialog"
 * - aria-modal="true"
 */
const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(
  (
    {
      className,
      children,
      size = 'md',
      showCloseButton = true,
      onOpenAutoFocus,
      onCloseAutoFocus,
      onEscapeKeyDown,
      onPointerDownOutside,
      onInteractOutside,
      ...props
    },
    ref
  ) => {
    const sizes = {
      sm: 'max-w-sm',
      md: 'max-w-lg',
      lg: 'max-w-2xl',
      xl: 'max-w-4xl',
      full: 'max-w-[95vw]',
    };

    return (
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          ref={ref}
          className={cn(
            'fixed left-[50%] top-[50%] z-50 w-full translate-x-[-50%] translate-y-[-50%]',
            'grid gap-4 border bg-white p-6 shadow-xl',
            'rounded-lg duration-200',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]',
            'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]',
            sizes[size],
            className
          )}
          onOpenAutoFocus={onOpenAutoFocus}
          onCloseAutoFocus={onCloseAutoFocus}
          onEscapeKeyDown={onEscapeKeyDown}
          onPointerDownOutside={onPointerDownOutside}
          onInteractOutside={onInteractOutside}
          {...props}
        >
          {children}
          {showCloseButton && (
            <DialogPrimitive.Close
              asChild
              className={cn(
                'absolute right-4 top-4 rounded-sm opacity-70',
                'ring-offset-white transition-opacity',
                'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-offset-2',
                'focus-visible:ring-blue-500',
                'disabled:pointer-events-none',
                'data-[state=open]:bg-gray-100 data-[state=open]:text-gray-500'
              )}
            >
              <button
                type="button"
                aria-label="Close dialog"
                className="p-1 focus-visible:outline-none"
              >
                <X className="h-4 w-4" weight="regular" aria-hidden="true" />
                <VisuallyHidden.Root>Close dialog</VisuallyHidden.Root>
              </button>
            </DialogPrimitive.Close>
          )}
        </DialogPrimitive.Content>
      </DialogPortal>
    );
  }
);
DialogContent.displayName = DialogPrimitive.Content.displayName;

/**
 * DialogHeader - Sección de encabezado del diálogo
 *
 * Contiene típicamente DialogTitle y DialogDescription
 */
const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col space-y-1.5 text-center sm:text-left', className)} {...props} />
);
DialogHeader.displayName = 'DialogHeader';

/**
 * DialogFooter - Sección de pie del diálogo
 *
 * Contiene típicamente botones de acción
 */
const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2', className)}
    {...props}
  />
);
DialogFooter.displayName = 'DialogFooter';

/**
 * DialogTitle - Título del diálogo
 *
 * ARIA: as="h2" por defecto, aria-labelledby en el content
 */
const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    asChild
    className={cn('text-lg font-semibold leading-none tracking-tight', className)}
  >
    <h2 {...props} />
  </DialogPrimitive.Title>
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

/**
 * DialogDescription - Descripción del diálogo
 *
 * ARIA: aria-describedby en el content apunta a este elemento
 */
const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-gray-600', className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
