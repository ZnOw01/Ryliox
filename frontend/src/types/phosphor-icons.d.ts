import type { FC, SVGProps } from 'react';

declare module '@phosphor-icons/react' {
  export interface IconProps extends SVGProps<SVGSVGElement> {
    size?: number | string;
    weight?: 'thin' | 'light' | 'regular' | 'bold' | 'fill' | 'duotone';
    color?: string;
    mirrored?: boolean;
    alt?: string;
    className?: string;
  }

  export type IconWeight = 'thin' | 'light' | 'regular' | 'bold' | 'fill' | 'duotone';

  export type PhosphorIconType = FC<IconProps>;
  export type Icon = FC<IconProps>;
  export type IconProps = import('react').SVGProps<SVGSVGElement> & {
    size?: number | string;
    weight?: IconWeight;
    color?: string;
    mirrored?: boolean;
    alt?: string;
  };

  export function IconContext(props: { value: Record<string, unknown> }): null;
  export function IconBase(props: Record<string, unknown>): null;

  // Navigation & Actions
  export const MagnifyingGlass: FC<IconProps>;
  export const X: FC<IconProps>;
  export const Plus: FC<IconProps>;
  export const Minus: FC<IconProps>;
  export const ArrowLeft: FC<IconProps>;
  export const ArrowRight: FC<IconProps>;
  export const ArrowUp: FC<IconProps>;
  export const ArrowDown: FC<IconProps>;
  export const CaretLeft: FC<IconProps>;
  export const CaretRight: FC<IconProps>;
  export const CaretUp: FC<IconProps>;
  export const CaretDown: FC<IconProps>;
  export const CaretDoubleLeft: FC<IconProps>;
  export const CaretDoubleRight: FC<IconProps>;
  export const ArrowClockwise: FC<IconProps>;
  export const ArrowCounterClockwise: FC<IconProps>;

  // Books & Content
  export const Book: FC<IconProps>;
  export const BookOpen: FC<IconProps>;
  export const BookOpenText: FC<IconProps>;
  export const BookBookmark: FC<IconProps>;
  export const Books: FC<IconProps>;
  export const Article: FC<IconProps>;
  export const FileText: FC<IconProps>;
  export const Files: FC<IconProps>;
  export const FileX: FC<IconProps>;
  export const FileArrowDown: FC<IconProps>;
  export const FilePdf: FC<IconProps>;
  export const Folder: FC<IconProps>;
  export const FolderOpen: FC<IconProps>;
  export const BookmarkSimple: FC<IconProps>;
  export const Bookmark: FC<IconProps>;
  export const Tag: FC<IconProps>;
  export const Hash: FC<IconProps>;

  // Media
  export const Image: FC<IconProps>;
  export const ImageBroken: FC<IconProps>;
  export const Play: FC<IconProps>;
  export const Pause: FC<IconProps>;
  export const Stop: FC<IconProps>;

  // Status & Feedback
  export const Check: FC<IconProps>;
  export const CheckCircle: FC<IconProps>;
  export const CheckSquare: FC<IconProps>;
  export const Square: FC<IconProps>;
  export const Circle: FC<IconProps>;
  export const XCircle: FC<IconProps>;
  export const Warning: FC<IconProps>;
  export const WarningOctagon: FC<IconProps>;
  export const WarningCircle: FC<IconProps>;
  export const Info: FC<IconProps>;
  export const Question: FC<IconProps>;
  export const Spinner: FC<IconProps>;
  export const SpinnerGap: FC<IconProps>;
  export const Prohibit: FC<IconProps>;

  // UI Elements
  export const List: FC<IconProps>;
  export const GridFour: FC<IconProps>;
  export const Rows: FC<IconProps>;
  export const Faders: FC<IconProps>;
  export const FadersHorizontal: FC<IconProps>;
  export const MagnifyingGlassPlus: FC<IconProps>;
  export const MagnifyingGlassMinus: FC<IconProps>;

  // Actions
  export const Download: FC<IconProps>;
  export const DownloadSimple: FC<IconProps>;
  export const Upload: FC<IconProps>;
  export const UploadSimple: FC<IconProps>;
  export const Copy: FC<IconProps>;
  export const CopySimple: FC<IconProps>;
  export const Trash: FC<IconProps>;
  export const PencilSimple: FC<IconProps>;
  export const Pencil: FC<IconProps>;
  export const Gear: FC<IconProps>;
  export const DotsThree: FC<IconProps>;
  export const DotsThreeVertical: FC<IconProps>;

  // Communication
  export const Export: FC<IconProps>;
  export const ShareNetwork: FC<IconProps>;
  export const Link: FC<IconProps>;
  export const LinkBreak: FC<IconProps>;
  export const Globe: FC<IconProps>;

  // User & Account
  export const User: FC<IconProps>;
  export const Users: FC<IconProps>;
  export const SignIn: FC<IconProps>;
  export const SignOut: FC<IconProps>;
  export const Shield: FC<IconProps>;
  export const ShieldCheck: FC<IconProps>;

  // Layout
  export const SidebarSimple: FC<IconProps>;
  export const Sidebar: FC<IconProps>;
  export const SquaresFour: FC<IconProps>;

  // Time
  export const Clock: FC<IconProps>;
  export const Calendar: FC<IconProps>;
  export const Timer: FC<IconProps>;

  // System
  export const Moon: FC<IconProps>;
  export const Sun: FC<IconProps>;
  export const Desktop: FC<IconProps>;
  export const DeviceMobile: FC<IconProps>;
  export const WifiHigh: FC<IconProps>;
  export const WifiSlash: FC<IconProps>;

  // Misc
  export const Terminal: FC<IconProps>;
  export const TerminalWindow: FC<IconProps>;
  export const Printer: FC<IconProps>;
  export const Star: FC<IconProps>;
  export const Heart: FC<IconProps>;
  export const Eye: FC<IconProps>;
  export const EyeSlash: FC<IconProps>;
  export const Buildings: FC<IconProps>;
  export const Command: FC<IconProps>;
  export const ChartBar: FC<IconProps>;
  export const Rocket: FC<IconProps>;
  export const Bell: FC<IconProps>;
  export const EnvelopeSimple: FC<IconProps>;
  export const Lock: FC<IconProps>;
  export const LockOpen: FC<IconProps>;
  export const Notepad: FC<IconProps>;
  export const Scroll: FC<IconProps>;
  export const Stack: FC<IconProps>;
  export const Tray: FC<IconProps>;
  export const Wrench: FC<IconProps>;
  export const Smiley: FC<IconProps>;
  export const SmileySad: FC<IconProps>;
  export const SmileyMeh: FC<IconProps>;
  export const Sparkle: FC<IconProps>;
  export const Keyboard: FC<IconProps>;
  export const Building: FC<IconProps>;
  export const Archive: FC<IconProps>;
  export const TextAa: FC<IconProps>;
  export const Cookie: FC<IconProps>;
  export const Compass: FC<IconProps>;
  export const CompassRose: FC<IconProps>;
  export const PencilSimpleLine: FC<IconProps>;
  export const Rss: FC<IconProps>;
  export const RssSimple: FC<IconProps>;
}
