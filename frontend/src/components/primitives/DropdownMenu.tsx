/**
 * Radix UI DropdownMenu Primitive Component
 *
 * Implements Radix UI DropdownMenu primitive with Context7 patterns:
 * - Root, Trigger, Content, Item, CheckboxItem, RadioItem, Group, Label, Separator, Portal, Sub, RadioGroup, Arrow
 * - Proper positioning con collision detection
 * - Focus management with roving tabindex
 * - Keyboard shortcuts: Escape, Arrow keys, Tab, Space, Enter, Home, End
 *
 * Accessibility (WCAG 2.1 AAA):
 * - aria-expanded="true|false" en trigger según estado
 * - aria-haspopup="menu" en trigger
 * - aria-controls="{content-id}" en trigger
 * - role="menu" en content
 * - role="menuitem" en items
 * - Keyboard: Arrow keys navigation, Escape to close
 * - Focus trapping within menu when open
 *
 * Keyboard Navigation:
 * - ArrowDown: Primer item o siguiente
 * - ArrowUp: Item anterior
 * - ArrowRight: Abrir submenú (si hay)
 * - ArrowLeft: Cerrar submenú y volver al padre
 * - Escape: Cerrar menú
 * - Home: Ir al primer item
 * - End: Ir al último item
 * - Space/Enter: Activar item seleccionado
 * - Tab: Cerrar menú y mover focus
 *
 * @example
 * <DropdownMenu>
 *   <DropdownMenuTrigger>Open</DropdownMenuTrigger>
 *   <DropdownMenuContent>
 *     <DropdownMenuLabel>My Account</DropdownMenuLabel>
 *     <DropdownMenuSeparator />
 *     <DropdownMenuItem>Profile</DropdownMenuItem>
 *     <DropdownMenuCheckboxItem checked={isChecked} onCheckedChange={setChecked}>
 *       Show notifications
 *     </DropdownMenuCheckboxItem>
 *     <DropdownMenuRadioGroup value={value} onValueChange={setValue}>
 *       <DropdownMenuRadioItem value="one">Option One</DropdownMenuRadioItem>
 *     </DropdownMenuRadioGroup>
 *   </DropdownMenuContent>
 * </DropdownMenu>
 */

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { Check, CaretRight, Circle } from '@phosphor-icons/react';

const DropdownMenu = DropdownMenuPrimitive.Root;

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuGroup = DropdownMenuPrimitive.Group;

const DropdownMenuPortal = DropdownMenuPrimitive.Portal;

const DropdownMenuSub = DropdownMenuPrimitive.Sub;

const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup;

/**
 * DropdownMenuSubTrigger - Trigger para submenús
 *
 * ARIA automáticos:
 * - aria-expanded (estado del submenú)
 * - aria-haspopup="menu"
 */
const DropdownMenuSubTrigger = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.SubTrigger>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubTrigger> & {
    inset?: boolean;
  }
>(({ className, inset, children, ...props }, ref) => (
  <DropdownMenuPrimitive.SubTrigger
    ref={ref}
    className={cn(
      'flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm',
      'outline-none transition-colors',
      'focus:bg-gray-100 focus:text-gray-900',
      'data-[state=open]:bg-gray-100 data-[state=open]:text-gray-900',
      inset && 'pl-8',
      className
    )}
    {...props}
  >
    {children}
    <CaretRight className="ml-auto h-4 w-4" weight="regular" aria-hidden="true" />
  </DropdownMenuPrimitive.SubTrigger>
));
DropdownMenuSubTrigger.displayName = DropdownMenuPrimitive.SubTrigger.displayName;

/**
 * DropdownMenuSubContent - Contenido del submenú
 *
 * Posicionamiento automático con collision detection
 * ARIA: role="menu" y aria-orientation="vertical"
 */
const DropdownMenuSubContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.SubContent>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubContent>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.SubContent
    ref={ref}
    className={cn(
      'z-50 min-w-[8rem] overflow-hidden rounded-md border bg-white p-1',
      'text-gray-900 shadow-lg',
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
  />
));
DropdownMenuSubContent.displayName = DropdownMenuPrimitive.SubContent.displayName;

/**
 * DropdownMenuContent - Contenido principal del dropdown
 *
 * Props de posicionamiento:
 * - side: "top" | "right" | "bottom" | "left"
 * - sideOffset: pixels offset
 * - align: "start" | "center" | "end"
 * - alignOffset: pixels offset
 * - avoidCollisions: boolean
 *
 * ARIA automáticos via Radix:
 * - role="menu"
 * - aria-orientation="vertical"
 */
const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 min-w-[8rem] overflow-hidden rounded-md border bg-white p-1',
        'text-gray-900 shadow-md',
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
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

/**
 * DropdownMenuItem - Item de menú seleccionable
 *
 * ARIA:
 * - role="menuitem"
 * - tabIndex="-1" (gestionado por Radix roving tabindex)
 * - disabled: aria-disabled="true"
 *
 * @param inset - Agregar padding-left para alineación
 * @param insetLeft - Valor del padding-left cuando inset=true (default: 32px = 2rem)
 */
const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {
    inset?: boolean;
    insetLeft?: number;
  }
>(({ className, inset, insetLeft = 8, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5',
      'text-sm outline-none transition-colors',
      'focus:bg-gray-100 focus:text-gray-900',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      inset && `pl-${insetLeft}`,
      className
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

/**
 * DropdownMenuCheckboxItem - Item con checkbox
 *
 * ARIA:
 * - role="menuitemcheckbox"
 * - aria-checked="true|false|mixed"
 * - tabIndex="-1"
 */
const DropdownMenuCheckboxItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.CheckboxItem>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.CheckboxItem>
>(({ className, children, checked, ...props }, ref) => (
  <DropdownMenuPrimitive.CheckboxItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2',
      'text-sm outline-none transition-colors',
      'focus:bg-gray-100 focus:text-gray-900',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className
    )}
    checked={checked}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <DropdownMenuPrimitive.ItemIndicator>
        <Check className="h-4 w-4" weight="bold" aria-hidden="true" />
      </DropdownMenuPrimitive.ItemIndicator>
    </span>
    {children}
  </DropdownMenuPrimitive.CheckboxItem>
));
DropdownMenuCheckboxItem.displayName = DropdownMenuPrimitive.CheckboxItem.displayName;

/**
 * DropdownMenuRadioItem - Item de opción de radio
 *
 * ARIA:
 * - role="menuitemradio"
 * - aria-checked="true|false"
 * - tabIndex="-1"
 */
const DropdownMenuRadioItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.RadioItem>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.RadioItem>
>(({ className, children, ...props }, ref) => (
  <DropdownMenuPrimitive.RadioItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2',
      'text-sm outline-none transition-colors',
      'focus:bg-gray-100 focus:text-gray-900',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <DropdownMenuPrimitive.ItemIndicator>
        <Circle className="h-2 w-2 fill-current" weight="fill" aria-hidden="true" />
      </DropdownMenuPrimitive.ItemIndicator>
    </span>
    {children}
  </DropdownMenuPrimitive.RadioItem>
));
DropdownMenuRadioItem.displayName = DropdownMenuPrimitive.RadioItem.displayName;

/**
 * DropdownMenuLabel - Etiqueta de sección
 *
 * ARIA: role="group" y aria-label en el grupo contenedor
 */
const DropdownMenuLabel = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label> & {
    inset?: boolean;
  }
>(({ className, inset, ...props }, ref) => (
  <DropdownMenuPrimitive.Label
    ref={ref}
    className={cn('px-2 py-1.5 text-sm font-semibold', inset && 'pl-8', className)}
    {...props}
  />
));
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName;

/**
 * DropdownMenuSeparator - Separador visual
 *
 * ARIA: role="separator"
 */
const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={cn('-mx-1 my-1 h-px bg-gray-200', className)}
    role="separator"
    {...props}
  />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

/**
 * DropdownMenuShortcut - Atajo de teclado (decorativo)
 *
 * ARIA: aria-hidden="true" porque es solo visual
 */
const DropdownMenuShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => {
  return (
    <span
      className={cn('ml-auto text-xs tracking-widest opacity-60', className)}
      aria-hidden="true"
      {...props}
    />
  );
};
DropdownMenuShortcut.displayName = 'DropdownMenuShortcut';

/**
 * DropdownMenuArrow - Flecha indicadora del dropdown
 *
 * Posicionada automáticamente según el lado
 */
const DropdownMenuArrow = DropdownMenuPrimitive.Arrow;

export {
  DropdownMenu,
  DropdownMenuArrow,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
};
