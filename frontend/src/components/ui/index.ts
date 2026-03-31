/**
 * UI Component Library - shadcn v4 New-York Style
 *
 * A collection of reusable UI components for Ryliox.
 * Updated to shadcn v4 with Tailwind v4 support.
 */

// Base UI Components
export { Button, buttonVariants, type ButtonProps } from './Button';
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './Card';
export { Badge, type BadgeProps } from './Badge';
export { Skeleton, TextSkeleton, CardSkeleton, ListSkeleton, type SkeletonProps } from './Skeleton';
export { EmptyState, type EmptyStateProps } from './EmptyState';
export { Tooltip, type TooltipProps } from './Tooltip';
export { Icon, iconSizes, type IconProps, type IconName, type IconSize } from './Icon';

// Accessibility Components
export { VisuallyHidden, StyledVisuallyHidden } from './VisuallyHidden';

// Sonner Toast (shadcn v4 replacement for Toast)
export { Toaster, toast } from './Sonner';

// Icon shortcuts
export {
  SearchIcon,
  DownloadIcon,
  CheckIcon,
  XIcon,
  AlertIcon,
  WarningIcon,
  InfoIcon,
  LoadingIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MoreIcon,
  SettingsIcon,
  RefreshIcon,
  CopyIcon,
  ExternalLinkIcon,
  FileIcon,
  FolderIcon,
  TrashIcon,
  EditIcon,
  SaveIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  WifiIcon,
  WifiOffIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  CalendarIcon,
  UserIcon,
  UsersIcon,
  EyeIcon,
  EyeOffIcon,
  MenuIcon,
  CloseIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  PlusIcon,
  MinusIcon,
  FilterIcon,
  SortAscIcon,
  SortDescIcon,
  GridIcon,
  ListIcon,
  MoonIcon,
  SunIcon,
  GlobeIcon,
  LogoutIcon,
  LoginIcon,
  ShieldIcon,
  ShieldCheckIcon,
  HelpIcon,
  CodeIcon,
  ImageIcon,
  LinkIcon,
  UnlinkIcon,
  HashIcon,
  TagIcon,
  StarIcon,
  HeartIcon,
  BookmarkIcon,
  ShareIcon,
  UploadIcon,
  FileDownIcon,
  PrintIcon,
  RotateIcon,
  ZoomInIcon,
  ZoomOutIcon,
  SearchXIcon,
  FileQuestionIcon,
} from './Icon';

// Loading Components
export {
  LoadingSpinner,
  InlineLoading,
  SkeletonLoader,
  PageLoader,
  type LoadingSpinnerProps,
} from './LoadingSpinner';

// 2026 Modern UI Patterns
export {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
  GlassCardFooter,
  GlassCardGlow,
  type GlassCardProps,
  type GlassCardHeaderProps,
  type GlassCardTitleProps,
  type GlassCardContentProps,
  type GlassCardFooterProps,
  type GlassCardGlowProps,
} from './GlassCard';

export {
  CommandPalette,
  useCommandPalette,
  type CommandPaletteProps,
  type CommandItem,
  type CommandGroup,
} from './CommandPalette';

export {
  MagneticButton,
  MagneticIconButton,
  MagneticGroup,
  type MagneticButtonProps,
  type MagneticIconButtonProps,
  type MagneticGroupProps,
} from './MagneticButton';

export {
  SkeletonAdvanced,
  CardSkeletonModern,
  ListSkeletonAdvanced,
  AvatarTextSkeleton,
  BentoSkeletonAnimated,
  TextSkeletonModern,
  ImageSkeletonAdvanced,
  StatsSkeleton,
  type SkeletonAdvancedProps,
  type CardSkeletonModernProps,
  type ListSkeletonAdvancedProps,
  type AvatarTextSkeletonProps,
  type BentoSkeletonAnimatedProps,
  type TextSkeletonModernProps,
  type ImageSkeletonAdvancedProps,
  type StatsSkeletonProps,
} from './SkeletonAdvanced';

// 2026 UX Enhancements - Empty States, Loading, Feedback & Interactions
export {
  EnhancedEmptyState,
  type EmptyStateType,
  type EnhancedEmptyStateProps,
} from './EnhancedEmptyState';

export {
  useToastStore,
  BeautifulToastContainer,
  useToast,
  toast as beautifulToast,
  type ToastType,
  type Toast,
} from './BeautifulToast';

export {
  useKeyboardShortcuts,
  useListNavigation,
  useFocusTrap,
  ShortcutHint,
  KeyboardShortcutsModal,
  FocusRing,
  useKeyboardNavigation,
  FloatingShortcuts,
  type KeyboardShortcut,
} from './KeyboardNavigation';

export {
  LoadingFeedback,
  AnimatedProgressBar,
  ElegantSkeleton,
  LoadingOverlay,
  StaggeredLoadingList,
  ContentPlaceholder,
  type LoadingState,
} from './LoadingStates';

export {
  HoverCard,
  RippleButton,
  ClickFeedback,
  FadeTransition,
  StaggerContainer,
  StaggerItem,
  PageTransition,
  Shake,
  Pulse,
  Bounce,
  GlowEffect,
  Counter,
} from './MicroInteractions';
