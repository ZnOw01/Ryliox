/**
 * Radix UI Primitives - Barrel Export
 *
 * Modern Radix UI primitives implementation following Context7 patterns 2025-2026.
 * All components include WCAG 2.1 AAA accessibility features.
 */

// Dialog - Modal dialogs with focus trapping
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
} from './Dialog';

// DropdownMenu - Context menus with keyboard navigation
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
} from './DropdownMenu';

// NavigationMenu - Navigation with submenus
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
} from './NavigationMenu';

// Popover - Non-modal popovers with positioning
export {
  Popover,
  PopoverAnchor,
  PopoverArrow,
  PopoverClose,
  PopoverContent,
  PopoverPortal,
  PopoverTrigger,
} from './Popover';

// Tooltip - Hover/focus tooltips
export { Tooltip, TooltipArrow, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';
