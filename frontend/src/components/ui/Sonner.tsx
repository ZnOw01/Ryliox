import { Toaster as Sonner, toast } from 'sonner';
import type { ToasterProps } from 'sonner';

/**
 * Sonner Toast Component - shadcn v4 replacement for Toast
 *
 * @example
 * ```tsx
 * // Success toast
 * toast.success("Changes saved successfully!")
 *
 * // Error toast
 * toast.error("Something went wrong")
 *
 * // Info toast with action
 * toast("File deleted", {
 *   action: { label: "Undo", onClick: () => undoDelete() }
 * })
 * ```
 */

interface SonnerToasterProps extends ToasterProps {
  position?:
    | 'top-left'
    | 'top-right'
    | 'bottom-left'
    | 'bottom-right'
    | 'top-center'
    | 'bottom-center';
  richColors?: boolean;
  expand?: boolean;
  duration?: number;
  closeButton?: boolean;
  invert?: boolean;
  pauseWhenPageIsHidden?: boolean;
}

function Toaster({
  position = 'bottom-right',
  richColors = true,
  expand = false,
  duration = 5000,
  closeButton = true,
  invert = false,
  pauseWhenPageIsHidden = true,
  ...props
}: SonnerToasterProps) {
  return (
    <Sonner
      theme="system"
      position={position}
      richColors={richColors}
      expand={expand}
      duration={duration}
      closeButton={closeButton}
      invert={invert}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-muted-foreground',
          actionButton: 'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
          cancelButton: 'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
        },
      }}
      {...props}
    />
  );
}

export { Toaster, toast };
