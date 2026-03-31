import { cn } from '../../lib/cn';
import {
  type Icon as PhosphorIcon,
  type IconProps as PhosphorIconProps,
  // Navigation & Actions
  MagnifyingGlass,
  X,
  Plus,
  Minus,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  CaretLeft,
  CaretRight,
  CaretUp,
  CaretDown,
  CaretDoubleLeft,
  CaretDoubleRight,
  ArrowClockwise,
  ArrowCounterClockwise,
  // Books & Content
  Book,
  BookOpen,
  Books,
  BookBookmark,
  Article,
  FileText,
  Files,
  Folder,
  FolderOpen,
  BookmarkSimple,
  Bookmark,
  Tag,
  Hash,
  // Media
  Image,
  ImageBroken,
  Play,
  Pause,
  Stop,
  // Status & Feedback
  Check,
  CheckCircle,
  Warning,
  WarningCircle,
  Info,
  Question,
  Spinner,
  Prohibit,
  // UI Elements
  List,
  GridFour,
  Rows,
  Faders,
  FadersHorizontal,
  MagnifyingGlassPlus,
  MagnifyingGlassMinus,
  // Actions
  DownloadSimple,
  UploadSimple,
  Copy,
  Trash,
  PencilSimple,
  Pencil,
  Gear,
  DotsThree,
  DotsThreeVertical,
  // Communication
  Export,
  ShareNetwork,
  Link,
  LinkBreak,
  Globe,
  // User & Account
  User,
  Users,
  SignIn,
  SignOut,
  Shield,
  ShieldCheck,
  // Layout
  SidebarSimple,
  Sidebar,
  SquaresFour,
  // Time
  Clock,
  Calendar,
  Timer,
  // System
  Moon,
  Sun,
  Desktop,
  DeviceMobile,
  WifiHigh,
  WifiSlash,
  // Misc
  Terminal,
  Printer,
  FilePdf,
  FileArrowDown,
  Archive,
  Star,
  Heart,
  Eye,
  EyeSlash,
  Buildings,
  Command,
  // New additions for better coverage
  ChartBar,
  Rocket,
  Bell,
  EnvelopeSimple,
  Lock,
  LockOpen,
  Notepad,
  Scroll,
  Stack,
  Tray,
  Wrench,
  Smiley,
  SmileySad,
  SmileyMeh,
} from '@phosphor-icons/react';

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

const iconMap: Record<IconName, PhosphorIcon> = {
  // Navigation & Actions
  search: MagnifyingGlass,
  close: X,
  plus: Plus,
  minus: Minus,
  'arrow-left': ArrowLeft,
  'arrow-right': ArrowRight,
  'arrow-up': ArrowUp,
  'arrow-down': ArrowDown,
  'caret-left': CaretLeft,
  'caret-right': CaretRight,
  'caret-up': CaretUp,
  'caret-down': CaretDown,
  'caret-double-left': CaretDoubleLeft,
  'caret-double-right': CaretDoubleRight,
  refresh: ArrowClockwise,
  undo: ArrowCounterClockwise,
  redo: ArrowClockwise,

  // Books & Content
  book: Book,
  'book-open': BookOpen,
  books: Books,
  'book-bookmark': BookBookmark,
  article: Article,
  file: FileText,
  files: Files,
  folder: Folder,
  'folder-open': FolderOpen,
  bookmark: Bookmark,
  'bookmark-simple': BookmarkSimple,
  tag: Tag,
  hash: Hash,

  // Media
  image: Image,
  'image-broken': ImageBroken,
  play: Play,
  pause: Pause,
  stop: Stop,

  // Status & Feedback
  check: Check,
  'check-circle': CheckCircle,
  warning: Warning,
  'warning-circle': WarningCircle,
  info: Info,
  question: Question,
  loader: Spinner,
  prohibit: Prohibit,

  // UI Elements
  list: List,
  grid: GridFour,
  'grid-four': GridFour,
  rows: Rows,
  filter: Faders,
  'filter-horizontal': FadersHorizontal,
  'zoom-in': MagnifyingGlassPlus,
  'zoom-out': MagnifyingGlassMinus,
  'zoom-reset': MagnifyingGlass,

  // Actions
  download: DownloadSimple,
  upload: UploadSimple,
  copy: Copy,
  trash: Trash,
  edit: Pencil,
  'edit-simple': PencilSimple,
  settings: Gear,
  gear: Gear,
  more: DotsThree,
  'more-vertical': DotsThreeVertical,

  // Communication
  export: Export,
  share: ShareNetwork,
  link: Link,
  unlink: LinkBreak,
  globe: Globe,

  // User & Account
  user: User,
  users: Users,
  login: SignIn,
  logout: SignOut,
  shield: Shield,
  'shield-check': ShieldCheck,

  // Layout
  sidebar: Sidebar,
  'sidebar-simple': SidebarSimple,
  squares: SquaresFour,

  // Time
  clock: Clock,
  calendar: Calendar,
  timer: Timer,

  // System
  moon: Moon,
  sun: Sun,
  desktop: Desktop,
  mobile: DeviceMobile,
  wifi: WifiHigh,
  'wifi-off': WifiSlash,

  // Misc
  terminal: Terminal,
  print: Printer,
  'file-pdf': FilePdf,
  'file-down': FileArrowDown,
  archive: Archive,
  star: Star,
  heart: Heart,
  eye: Eye,
  'eye-off': EyeSlash,
  building: Buildings,
  buildings: Buildings,
  command: Command,
  chart: ChartBar,
  rocket: Rocket,
  bell: Bell,
  mail: EnvelopeSimple,
  lock: Lock,
  unlock: LockOpen,
  notepad: Notepad,
  scroll: Scroll,
  stack: Stack,
  tray: Tray,
  wrench: Wrench,
  smile: Smiley,
  sad: SmileySad,
  meh: SmileyMeh,
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

export interface IconProps extends Omit<PhosphorIconProps, 'size' | 'weight'> {
  icon: PhosphorIcon | IconName;
  size?: IconSize | number;
  weight?: 'thin' | 'light' | 'regular' | 'bold' | 'fill' | 'duotone';
  spin?: boolean;
  className?: string;
}

export function Icon({
  icon,
  size = 'md',
  weight = 'regular',
  spin = false,
  className,
  ...props
}: IconProps) {
  const IconComponent: PhosphorIcon = typeof icon === 'string' ? iconMap[icon as IconName] : icon;

  if (!IconComponent) {
    console.warn(`Icon "${icon}" not found in icon map`);
    return null;
  }

  const sizeValue = typeof size === 'number' ? size : iconSizes[size];

  return (
    <IconComponent
      size={sizeValue}
      weight={weight}
      className={cn('shrink-0', spin && 'animate-spin', className)}
      {...props}
    />
  );
}

// Pre-built icon shortcuts for common use cases
export const SearchIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={MagnifyingGlass} {...props} />
);
export const DownloadIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={DownloadSimple} {...props} />
);
export const CheckIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Check} {...props} />;
export const XIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const AlertIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={WarningCircle} {...props} />
);
export const WarningIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Warning} {...props} />;
export const InfoIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Info} {...props} />;
export const LoadingIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Spinner} weight="bold" spin {...props} />
);
export const ChevronDownIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CaretDown} {...props} />
);
export const ChevronUpIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={CaretUp} {...props} />;
export const ChevronLeftIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CaretLeft} {...props} />
);
export const ChevronRightIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CaretRight} {...props} />
);
export const MoreIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={DotsThree} {...props} />;
export const MoreVerticalIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={DotsThreeVertical} {...props} />
);
export const SettingsIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Gear} {...props} />;
export const RefreshIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ArrowClockwise} {...props} />
);
export const CopyIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Copy} {...props} />;
export const ExternalLinkIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Export} {...props} />
);
export const FileIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={FileText} {...props} />;
export const FolderIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Folder} {...props} />;
export const TrashIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Trash} {...props} />;
export const EditIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Pencil} {...props} />;
export const EditSimpleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={PencilSimple} {...props} />
);
export const SaveIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Check} {...props} />;
export const PlayIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Play} {...props} />;
export const PauseIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Pause} {...props} />;
export const StopIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Stop} {...props} />;
export const WifiIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={WifiHigh} {...props} />;
export const WifiOffIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={WifiSlash} {...props} />;
export const CheckCircleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CheckCircle} {...props} />
);
export const XCircleIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Prohibit} {...props} />;
export const ClockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Clock} {...props} />;
export const CalendarIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Calendar} {...props} />;
export const UserIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={User} {...props} />;
export const UsersIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Users} {...props} />;
export const EyeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Eye} {...props} />;
export const EyeOffIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={EyeSlash} {...props} />;
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
export const FilterIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Faders} {...props} />;
export const SortAscIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={CaretUp} {...props} />;
export const SortDescIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={CaretDown} {...props} />
);
export const GridIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={GridFour} {...props} />;
export const ListIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Rows} {...props} />;
export const MoonIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Moon} {...props} />;
export const SunIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Sun} {...props} />;
export const GlobeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Globe} {...props} />;
export const LogoutIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={SignOut} {...props} />;
export const LoginIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={SignIn} {...props} />;
export const ShieldIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Shield} {...props} />;
export const ShieldCheckIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ShieldCheck} {...props} />
);
export const HelpIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Question} {...props} />;
export const CodeIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Terminal} {...props} />;
export const ImageIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Image} {...props} />;
export const ImageBrokenIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ImageBroken} {...props} />
);
export const LinkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Link} {...props} />;
export const UnlinkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={LinkBreak} {...props} />;
export const HashIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Hash} {...props} />;
export const TagIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Tag} {...props} />;
export const StarIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Star} {...props} />;
export const HeartIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Heart} {...props} />;
export const BookmarkIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Bookmark} {...props} />;
export const BookmarkSimpleIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={BookmarkSimple} {...props} />
);
export const ShareIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ShareNetwork} {...props} />
);
export const UploadIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={UploadSimple} {...props} />
);
export const FileDownIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={FileArrowDown} {...props} />
);
export const PrintIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Printer} {...props} />;
export const RotateIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={ArrowClockwise} {...props} />
);
export const ZoomInIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={MagnifyingGlassPlus} {...props} />
);
export const ZoomOutIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={MagnifyingGlassMinus} {...props} />
);
export const ZoomResetIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const SearchXIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={X} {...props} />;
export const FileQuestionIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Question} {...props} />
);
export const BuildingIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Buildings} {...props} />
);
export const BuildingsIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={Buildings} {...props} />
);
export const CommandIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Command} {...props} />;
export const ChartIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={ChartBar} {...props} />;
export const RocketIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Rocket} {...props} />;
export const BellIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Bell} {...props} />;
export const MailIcon = (props: Omit<IconProps, 'icon'>) => (
  <Icon icon={EnvelopeSimple} {...props} />
);
export const LockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Lock} {...props} />;
export const UnlockIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={LockOpen} {...props} />;
export const NotepadIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Notepad} {...props} />;
export const ScrollIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Scroll} {...props} />;
export const StackIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Stack} {...props} />;
export const TrayIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Tray} {...props} />;
export const WrenchIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Wrench} {...props} />;
export const SmileIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Smiley} {...props} />;
export const SadIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={SmileySad} {...props} />;
export const MehIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={SmileyMeh} {...props} />;
export const BooksIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Books} {...props} />;
export const BookOpenIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={BookOpen} {...props} />;
export const ArticleIcon = (props: Omit<IconProps, 'icon'>) => <Icon icon={Article} {...props} />;

export { Book, BookOpen, Books, MagnifyingGlass, DownloadSimple, Check, X };
