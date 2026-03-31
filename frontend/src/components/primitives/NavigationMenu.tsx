/**
 * Radix UI NavigationMenu Primitive Component
 *
 * Implements Radix UI NavigationMenu primitive with Context7 patterns:
 * - Root, List, Item, Trigger, Content, Link, Viewport, Indicator
 * - Client-side routing integration via asChild composition
 * - Active state management
 * - Accessible keyboard navigation (roving tabindex)
 * - Submenu support with NavigationMenu.Sub
 *
 * Accessibility (WCAG 2.1 AAA):
 * - role="navigation" en el contenedor
 * - aria-label para el menú
 * - aria-current="page" para el item activo
 * - aria-expanded en triggers
 * - Keyboard: Arrow keys, Home/End, Escape
 *
 * Keyboard Navigation:
 * - ArrowLeft/ArrowRight: Mover entre items principales
 * - ArrowDown: Abrir submenú
 * - Escape: Cerrar submenú abierto
 * - Home: Ir al primer item
 * - End: Ir al último item
 *
 * @example
 * <NavigationMenu>
 *   <NavigationMenuList>
 *     <NavigationMenuItem>
 *       <NavigationMenuLink href="/">Home</NavigationMenuLink>
 *     </NavigationMenuItem>
 *     <NavigationMenuItem>
 *       <NavigationMenuTrigger>Products</NavigationMenuTrigger>
 *       <NavigationMenuContent>
 *         <NavigationMenuSub>
 *           <NavigationMenuItem value="p1">...</NavigationMenuItem>
 *         </NavigationMenuSub>
 *       </NavigationMenuContent>
 *     </NavigationMenuItem>
 *   </NavigationMenuList>
 *   <NavigationMenuViewport />
 * </NavigationMenu>
 */

import * as NavigationMenuPrimitive from '@radix-ui/react-navigation-menu';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { CaretDown } from '@phosphor-icons/react';

const NavigationMenu = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Root> & {
    /** Label descriptivo para screen readers */
    'aria-label'?: string;
  }
>(({ className, 'aria-label': ariaLabel, children, ...props }, ref) => (
  <NavigationMenuPrimitive.Root
    ref={ref}
    className={cn('relative z-10 flex max-w-max flex-1 items-center justify-center', className)}
    {...props}
    aria-label={ariaLabel || 'Main navigation'}
  >
    {children}
  </NavigationMenuPrimitive.Root>
));
NavigationMenu.displayName = NavigationMenuPrimitive.Root.displayName;

const NavigationMenuList = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.List>
>(({ className, ...props }, ref) => (
  <NavigationMenuPrimitive.List
    ref={ref}
    className={cn('group flex flex-1 list-none items-center justify-center space-x-1', className)}
    {...props}
  />
));
NavigationMenuList.displayName = NavigationMenuPrimitive.List.displayName;

const NavigationMenuItem = NavigationMenuPrimitive.Item;

/**
 * NavigationMenuTrigger - Botón que abre submenús
 *
 * ARIA automáticos via Radix:
 * - aria-expanded (estado del submenú)
 * - aria-controls (apunta al content)
 *
 * @param withIndicator - Mostrar flecha indicadora de dropdown
 */
const NavigationMenuTrigger = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Trigger> & {
    withIndicator?: boolean;
  }
>(({ className, children, withIndicator = true, ...props }, ref) => (
  <NavigationMenuPrimitive.Trigger
    ref={ref}
    className={cn(
      'group inline-flex h-9 w-max items-center justify-center',
      'rounded-md bg-transparent px-4 py-2 text-sm font-medium',
      'transition-colors',
      'hover:bg-gray-100 hover:text-gray-900',
      'focus-visible:bg-gray-100 focus-visible:outline-none focus-visible:ring-1',
      'focus-visible:ring-blue-500',
      'disabled:pointer-events-none disabled:opacity-50',
      'data-[active]:bg-gray-100/50 data-[state=open]:bg-gray-100/50',
      className
    )}
    {...props}
  >
    {children}
    {withIndicator && (
      <CaretDown
        className="relative top-[1px] ml-1 h-3 w-3 transition duration-300 group-data-[state=open]:rotate-180"
        weight="regular"
        aria-hidden="true"
      />
    )}
  </NavigationMenuPrimitive.Trigger>
));
NavigationMenuTrigger.displayName = NavigationMenuPrimitive.Trigger.displayName;

/**
 * NavigationMenuContent - Contenido del submenú
 *
 * ARIA:
 * - id automático para aria-controls del trigger
 *
 * Keyboard: Items dentro son navegables con Arrow keys
 */
const NavigationMenuContent = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Content>
>(({ className, ...props }, ref) => (
  <NavigationMenuPrimitive.Content
    ref={ref}
    className={cn(
      'left-0 top-0 w-full data-[motion=from-start]:animate-enterFromLeft',
      'data-[motion=from-end]:animate-enterFromRight',
      'data-[motion=to-start]:animate-exitToLeft data-[motion=to-end]:animate-exitToRight',
      'md:absolute md:w-auto',
      className
    )}
    {...props}
  />
));
NavigationMenuContent.displayName = NavigationMenuPrimitive.Content.displayName;

/**
 * NavigationMenuLink - Enlace del menú
 *
 * ARIA:
 * - aria-current="page" cuando está activo
 * - data-[active] para styling
 *
 * @example
 * <NavigationMenuLink asChild active={isActive}>
 *   <NextLink href="/about">About</NextLink>
 * </NavigationMenuLink>
 */
const NavigationMenuLink = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Link>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Link>
>(({ className, ...props }, ref) => (
  <NavigationMenuPrimitive.Link
    ref={ref}
    className={cn(
      'group inline-flex h-9 w-max items-center justify-center',
      'rounded-md bg-transparent px-4 py-2 text-sm font-medium',
      'transition-colors',
      'hover:bg-gray-100 hover:text-gray-900',
      'focus-visible:bg-gray-100 focus-visible:outline-none focus-visible:ring-1',
      'focus-visible:ring-blue-500',
      'disabled:pointer-events-none disabled:opacity-50',
      'data-[active]:bg-gray-100/50 data-[state=open]:text-gray-900',
      className
    )}
    {...props}
  />
));
NavigationMenuLink.displayName = NavigationMenuPrimitive.Link.displayName;

/**
 * NavigationMenuViewport - Viewport del menú
 *
 * Contiene la posición y animación del submenú desplegado
 */
const NavigationMenuViewport = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Viewport>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Viewport>
>(({ className, ...props }, ref) => (
  <div className={cn('absolute left-0 top-full flex justify-center')}>
    <NavigationMenuPrimitive.Viewport
      className={cn(
        'origin-top-center relative mt-1.5 h-[var(--radix-navigation-menu-viewport-height)]',
        'w-full overflow-hidden rounded-md border bg-white text-gray-900 shadow-md',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-90',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2',
        'md:w-[var(--radix-navigation-menu-viewport-width)]',
        className
      )}
      ref={ref}
      {...props}
    />
  </div>
));
NavigationMenuViewport.displayName = NavigationMenuPrimitive.Viewport.displayName;

/**
 * NavigationMenuIndicator - Indicador visual del item activo
 *
 * Visual feedback del item seleccionado
 */
const NavigationMenuIndicator = React.forwardRef<
  React.ElementRef<typeof NavigationMenuPrimitive.Indicator>,
  React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Indicator>
>(({ className, ...props }, ref) => (
  <NavigationMenuPrimitive.Indicator
    ref={ref}
    className={cn(
      'top-full z-[1] flex h-1.5 items-end justify-center overflow-hidden',
      'data-[state=visible]:animate-in data-[state=hidden]:animate-out',
      'data-[state=hidden]:fade-out data-[state=visible]:fade-in',
      className
    )}
    {...props}
  >
    <div className="relative top-[60%] h-2 w-2 rotate-45 rounded-tl-sm bg-white shadow-md" />
  </NavigationMenuPrimitive.Indicator>
));
NavigationMenuIndicator.displayName = NavigationMenuPrimitive.Indicator.displayName;

/**
 * NavigationMenuSub - Submenú anidado
 *
 * Para crear submenús dentro de un NavigationMenu.Content
 * Requiere defaultValue para establecer el item activo por defecto
 *
 * @example
 * <NavigationMenuSub defaultValue="sub1">
 *   <NavigationMenuList>
 *     <NavigationMenuItem value="sub1">...</NavigationMenuItem>
 *     <NavigationMenuItem value="sub2">...</NavigationMenuItem>
 *   </NavigationMenuList>
 * </NavigationMenuSub>
 */
const NavigationMenuSub = NavigationMenuPrimitive.Sub;

export {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuIndicator,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuSub,
  NavigationMenuTrigger,
  NavigationMenuViewport,
};
