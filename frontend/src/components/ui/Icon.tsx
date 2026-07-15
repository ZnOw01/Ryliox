import { cn } from '../../lib/cn';
import type { LucideIcon, LucideProps } from 'lucide-react';
import {
  // Navigation & Actions
  Search,
  X,
  Plus,
  Minus,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  RotateCw,
  RotateCcw,
  // Books & Content
  BookMarked,
  BookOpen,
  Library,
  BookmarkCheck,
  FileText,
  Files,
  Folder,
  FolderOpen,
  Bookmark,
  BookmarkMinus,
  Tag,
  Hash,
  // Media
  Image,
  ImageOff,
  Play,
  Pause,
  Square as StopIconBase,
  // Status & Feedback
  Check,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  HelpCircle,
  Loader2,
  Ban,
  // UI Elements
  List,
  LayoutGrid,
  Rows3,
  SlidersHorizontal,
  SlidersVertical,
  ZoomIn,
  ZoomOut,
  // Actions
  Download,
  Upload,
  Copy,
  Trash2,
  Pencil,
  PenLine,
  Settings,
  MoreHorizontal,
  MoreVertical,
  // Communication
  ExternalLink,
  Share2,
  Link,
  Unlink,
  Globe,
  // User & Account
  User,
  Users,
  LogIn,
  LogOut,
  Shield,
  ShieldCheck,
  // Layout
  PanelLeft,
  PanelLeftClose,
  LayoutDashboard,
  // Time
  Clock,
  Calendar,
  Timer,
  // System
  Moon,
  Sun,
  Monitor,
  Smartphone,
  Wifi,
  WifiOff,
  // Misc
  Terminal,
  Printer,
  FileType,
  FileDown,
  Archive,
  Star,
  Heart,
  Eye,
  EyeOff,
  Building2,
  Command,
  BarChart3,
  Rocket,
  Bell,
  Mail,
  Lock,
  Unlock,
  NotebookPen,
  ScrollText,
  Layers,
  Inbox,
  Wrench,
  Smile,
  Frown,
  Meh,
  Newspaper,
} from 'lucide-react';

export type IconName =
  // Navigation & Actions
  | 'search'
  | 'close'
  | 'plus'
  | 'minus'
  | 'arrow-left'
  | 'arrow-right'
  | 'arrow-up'
  | 'arrow-down'
  | 'caret-left'
  | 'caret-right'
  | 'caret-up'
  | 'caret-down'
  | 'caret-double-left'
  | 'caret-double-right'
  | 'refresh'
  | 'undo'
  | 'redo'
  // Books & Content
  | 'book'
  | 'book-open'
  | 'books'
  | 'book-bookmark'
  | 'article'
  | 'file'
  | 'files'
  | 'folder'
  | 'folder-open'
  | 'bookmark'
  | 'bookmark-simple'
  | 'tag'
  | 'hash'
  // Media
  | 'image'
  | 'image-broken'
  | 'play'
  | 'pause'
  | 'stop'
  // Status & Feedback
  | 'check'
  | 'check-circle'
  | 'warning'
  | 'warning-circle'
  | 'info'
  | 'question'
  | 'loader'
  | 'prohibit'
  // UI Elements
  | 'list'
  | 'grid'
  | 'grid-four'
  | 'rows'
  | 'filter'
  | 'filter-horizontal'
  | 'zoom-in'
  | 'zoom-out'
  | 'zoom-reset'
  // Actions
  | 'download'
  | 'upload'
  | 'copy'
  | 'trash'
  | 'edit'
  | 'edit-simple'
  | 'settings'
  | 'gear'
  | 'more'
  | 'more-vertical'
  // Communication
  | 'export'
  | 'share'
  | 'link'
  | 'unlink'
  | 'globe'
  // User & Account
  | 'user'
  | 'users'
  | 'login'
  | 'logout'
  | 'shield'
  | 'shield-check'
  // Layout
  | 'sidebar'
  | 'sidebar-simple'
  | 'squares'
  // Time
  | 'clock'
  | 'calendar'
  | 'timer'
  // System
  | 'moon'
  | 'sun'
  | 'desktop'
  | 'mobile'
  | 'wifi'
  | 'wifi-off'
  // Misc
  | 'terminal'
  | 'print'
  | 'file-pdf'
  | 'file-down'
  | 'archive'
  | 'star'
  | 'heart'
  | 'eye'
  | 'eye-off'
  | 'building'
  | 'buildings'
  | 'command'
  | 'chart'
  | 'rocket'
  | 'bell'
  | 'mail'
  | 'lock'
  | 'unlock'
  | 'notepad'
  | 'scroll'
  | 'stack'
  | 'tray'
  | 'wrench'
  | 'smile'
  | 'sad'
  | 'meh'
  | 'search-x';

const iconMap: Record<IconName, LucideIcon> = {
  // Navigation & Actions
  search: Search,
  close: X,
  plus: Plus,
  minus: Minus,
  'arrow-left': ArrowLeft,
  'arrow-right': ArrowRight,
  'arrow-up': ArrowUp,
  'arrow-down': ArrowDown,
  'caret-left': ChevronLeft,
  'caret-right': ChevronRight,
  'caret-up': ChevronUp,
  'caret-down': ChevronDown,
  'caret-double-left': ChevronsLeft,
  'caret-double-right': ChevronsRight,
  refresh: RotateCw,
  undo: RotateCcw,
  redo: RotateCw,

  // Books & Content
  book: BookMarked,
  'book-open': BookOpen,
  books: Library,
  'book-bookmark': BookmarkCheck,
  article: Newspaper,
  file: FileText,
  files: Files,
  folder: Folder,
  'folder-open': FolderOpen,
  bookmark: Bookmark,
  'bookmark-simple': BookmarkMinus,
  tag: Tag,
  hash: Hash,

  // Media
  image: Image,
  'image-broken': ImageOff,
  play: Play,
  pause: Pause,
  stop: StopIconBase,

  // Status & Feedback
  check: Check,
  'check-circle': CheckCircle,
  warning: AlertTriangle,
  'warning-circle': AlertCircle,
  info: Info,
  question: HelpCircle,
  loader: Loader2,
  prohibit: Ban,

  // UI Elements
  list: List,
  grid: LayoutGrid,
  'grid-four': LayoutGrid,
  rows: Rows3,
  filter: SlidersVertical,
  'filter-horizontal': SlidersHorizontal,
  'zoom-in': ZoomIn,
  'zoom-out': ZoomOut,
  'zoom-reset': Search,

  // Actions
  download: Download,
  upload: Upload,
  copy: Copy,
  trash: Trash2,
  edit: Pencil,
  'edit-simple': PenLine,
  settings: Settings,
  gear: Settings,
  more: MoreHorizontal,
  'more-vertical': MoreVertical,

  // Communication
  export: ExternalLink,
  share: Share2,
  link: Link,
  unlink: Unlink,
  globe: Globe,

  // User & Account
  user: User,
  users: Users,
  login: LogIn,
  logout: LogOut,
  shield: Shield,
  'shield-check': ShieldCheck,

  // Layout
  sidebar: PanelLeft,
  'sidebar-simple': PanelLeftClose,
  squares: LayoutDashboard,

  // Time
  clock: Clock,
  calendar: Calendar,
  timer: Timer,

  // System
  moon: Moon,
  sun: Sun,
  desktop: Monitor,
  mobile: Smartphone,
  wifi: Wifi,
  'wifi-off': WifiOff,

  // Misc
  terminal: Terminal,
  print: Printer,
  'file-pdf': FileType,
  'file-down': FileDown,
  archive: Archive,
  star: Star,
  heart: Heart,
  eye: Eye,
  'eye-off': EyeOff,
  building: Building2,
  buildings: Building2,
  command: Command,
  chart: BarChart3,
  rocket: Rocket,
  bell: Bell,
  mail: Mail,
  lock: Lock,
  unlock: Unlock,
  notepad: NotebookPen,
  scroll: ScrollText,
  stack: Layers,
  tray: Inbox,
  wrench: Wrench,
  smile: Smile,
  sad: Frown,
  meh: Meh,
  'search-x': X,
};

export const iconSizes = {
  xs: 12,
  sm: 14,
  default: 16,
  md: 20,
  lg: 24,
  xl: 32,
  '2xl': 48,
} as const;

export type IconSize = keyof typeof iconSizes;

export interface IconProps extends Omit<LucideProps, 'size'> {
  icon: LucideIcon | IconName;
  size?: IconSize | number;
  spin?: boolean;
  className?: string;
}

export function Icon({ icon, size = 'md', spin = false, className, ...props }: IconProps) {
  const IconComponent: LucideIcon = typeof icon === 'string' ? iconMap[icon as IconName] : icon;

  if (!IconComponent) {
    console.warn(`Icon "${icon}" not found in icon map`);
    return null;
  }

  const sizeValue = typeof size === 'number' ? size : iconSizes[size];

  return (
    <IconComponent
      size={sizeValue}
      strokeWidth={1.75}
      className={cn('shrink-0', spin && 'animate-spin', className)}
      {...props}
    />
  );
}

// Pre-built icon shortcuts for common use cases
export const SearchIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Search} {...props} />;
export const DownloadIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Download} {...props} />;
export const CheckIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Check} {...props} />;
export const XIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const AlertIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={AlertCircle} {...props} />;
export const WarningIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={AlertTriangle} {...props} />
);
export const InfoIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Info} {...props} />;
export const LoadingIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Loader2} spin {...props} />
);
export const ChevronDownIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ChevronDown} {...props} />
);
export const ChevronUpIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ChevronUp} {...props} />
);
export const ChevronLeftIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ChevronLeft} {...props} />
);
export const ChevronRightIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ChevronRight} {...props} />
);
export const MoreIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={MoreHorizontal} {...props} />
);
export const MoreVerticalIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={MoreVertical} {...props} />
);
export const SettingsIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Settings} {...props} />;
export const RefreshIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={RotateCw} {...props} />;
export const CopyIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Copy} {...props} />;
export const ExternalLinkIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ExternalLink} {...props} />
);
export const FileIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={FileText} {...props} />;
export const FolderIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Folder} {...props} />;
export const TrashIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Trash2} {...props} />;
export const EditIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Pencil} {...props} />;
export const EditSimpleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={PenLine} {...props} />
);
export const SaveIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Check} {...props} />;
export const PlayIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Play} {...props} />;
export const PauseIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Pause} {...props} />;
export const StopIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={StopIconBase} {...props} />;
export const WifiIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Wifi} {...props} />;
export const WifiOffIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={WifiOff} {...props} />;
export const CheckCircleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CheckCircle} {...props} />
);
export const XCircleIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Ban} {...props} />;
export const ClockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Clock} {...props} />;
export const CalendarIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Calendar} {...props} />;
export const UserIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={User} {...props} />;
export const UsersIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Users} {...props} />;
export const EyeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Eye} {...props} />;
export const EyeOffIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={EyeOff} {...props} />;
export const MenuIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={List} {...props} />;
export const CloseIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const ArrowRightIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ArrowRight} {...props} />
);
export const ArrowLeftIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ArrowLeft} {...props} />
);
export const PlusIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Plus} {...props} />;
export const MinusIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Minus} {...props} />;
export const FilterIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={SlidersVertical} {...props} />
);
export const SortAscIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={ChevronUp} {...props} />;
export const SortDescIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ChevronDown} {...props} />
);
export const GridIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={LayoutGrid} {...props} />;
export const ListIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Rows3} {...props} />;
export const MoonIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Moon} {...props} />;
export const SunIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Sun} {...props} />;
export const GlobeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Globe} {...props} />;
export const LogoutIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={LogOut} {...props} />;
export const LoginIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={LogIn} {...props} />;
export const ShieldIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Shield} {...props} />;
export const ShieldCheckIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ShieldCheck} {...props} />
);
export const HelpIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={HelpCircle} {...props} />;
export const CodeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Terminal} {...props} />;
export const ImageIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Image} {...props} />;
export const ImageBrokenIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ImageOff} {...props} />
);
export const LinkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Link} {...props} />;
export const UnlinkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Unlink} {...props} />;
export const HashIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Hash} {...props} />;
export const TagIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Tag} {...props} />;
export const StarIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Star} {...props} />;
export const HeartIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Heart} {...props} />;
export const BookmarkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Bookmark} {...props} />;
export const BookmarkSimpleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={BookmarkMinus} {...props} />
);
export const ShareIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Share2} {...props} />;
export const UploadIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Upload} {...props} />;
export const FileDownIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={FileDown} {...props} />;
export const PrintIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Printer} {...props} />;
export const RotateIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={RotateCw} {...props} />;
export const ZoomInIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={ZoomIn} {...props} />;
export const ZoomOutIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={ZoomOut} {...props} />;
export const ZoomResetIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const SearchXIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const FileQuestionIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={HelpCircle} {...props} />
);
export const BuildingIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Building2} {...props} />
);
export const BuildingsIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Building2} {...props} />
);
export const CommandIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Command} {...props} />;
export const ChartIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={BarChart3} {...props} />;
export const RocketIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Rocket} {...props} />;
export const BellIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Bell} {...props} />;
export const MailIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Mail} {...props} />;
export const LockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Lock} {...props} />;
export const UnlockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Unlock} {...props} />;
export const NotepadIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={NotebookPen} {...props} />
);
export const ScrollIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={ScrollText} {...props} />;
export const StackIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Layers} {...props} />;
export const TrayIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Inbox} {...props} />;
export const WrenchIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Wrench} {...props} />;
export const SmileIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Smile} {...props} />;
export const SadIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Frown} {...props} />;
export const MehIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Meh} {...props} />;
export const BooksIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Library} {...props} />;
export const BookOpenIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={BookOpen} {...props} />;
export const ArticleIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Newspaper} {...props} />;

export {
  BookMarked as Book,
  BookOpen,
  Library as Books,
  Search as MagnifyingGlass,
  Download as DownloadSimple,
  Check,
  X,
};
