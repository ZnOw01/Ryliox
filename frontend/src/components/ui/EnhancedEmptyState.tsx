import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import type { Icon as PhosphorIcon } from '@phosphor-icons/react';
import {
  MagnifyingGlass,
  FileX,
  FolderOpen,
  WifiSlash,
  BookOpen,
  Cookie,
  DownloadSimple,
  Compass,
  Sparkle,
  ArrowRight,
} from '@phosphor-icons/react';

export type EmptyStateVariant = 'default' | 'compact' | 'inline' | 'inspirational';
export type EmptyStateType = 'search' | 'cookies' | 'downloads' | 'book' | 'offline' | 'generic';

export interface EmptyStateProps {
  /** Tipo de empty state para contenido predefinido */
  type?: EmptyStateType;
  /** Phosphor icon component o icon name string */
  icon?: PhosphorIcon | keyof typeof iconMap;
  /** Título principal */
  title?: string;
  /** Descripción secundaria */
  description?: string;
  /** Variante visual */
  variant?: EmptyStateVariant;
  /** Acción principal */
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary' | 'ghost';
    icon?: PhosphorIcon;
  };
  /** Acción secundaria */
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  /** Pasos guiados (para empty states educativos) */
  steps?: string[];
  /** Ilustración SVG personalizada */
  illustration?: React.ReactNode;
  /** Clases adicionales */
  className?: string;
  /** Texto inspirador corto (variante inspirational) */
  quote?: string;
}

const iconMap: Record<string, PhosphorIcon> = {
  search: MagnifyingGlass,
  file: FileX,
  folder: FolderOpen,
  offline: WifiSlash,
  book: BookOpen,
  cookie: Cookie,
  download: DownloadSimple,
  compass: Compass,
  sparkle: Sparkle,
};

// Contenido predefinido por tipo
const defaultContent: Record<
  EmptyStateType,
  { title: string; description: string; icon: PhosphorIcon; quote?: string; steps?: string[] }
> = {
  search: {
    title: 'Comienza tu búsqueda',
    description: 'Explora miles de libros técnicos y recursos de aprendizaje.',
    icon: Compass,
    quote: 'El conocimiento es el único tesoro que crece al compartirse.',
  },
  cookies: {
    title: 'Configura tu acceso',
    description: 'Necesitas configurar cookies válidas para acceder al contenido.',
    icon: Cookie,
    steps: [
      'Copia las cookies de tu navegador',
      'Pégala en el editor de cookies',
      'Guarda y empieza a descargar',
    ],
  },
  downloads: {
    title: 'Aún no hay descargas',
    description: 'Selecciona un libro y elige los capítulos que quieres descargar.',
    icon: DownloadSimple,
    steps: ['Busca un libro', 'Selecciona los capítulos', 'Elige el formato y descarga'],
  },
  book: {
    title: 'Ningún libro seleccionado',
    description: 'Elige un libro de la lista para ver sus capítulos disponibles.',
    icon: BookOpen,
  },
  offline: {
    title: 'Sin conexión',
    description: 'Parece que no hay conexión a internet. Verifica tu red.',
    icon: WifiSlash,
  },
  generic: {
    title: 'No hay contenido',
    description: 'No se encontró información para mostrar.',
    icon: FolderOpen,
  },
};

// Ilustraciones SVG integradas
function SearchIllustration({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <motion.circle
        cx="55"
        cy="55"
        r="35"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <motion.path
        d="M82 82L102 102"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.4, ease: 'easeOut' }}
      />
      <motion.circle
        cx="55"
        cy="55"
        r="25"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="4 4"
        opacity="0.3"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 0.3 }}
        transition={{ duration: 1, delay: 0.6 }}
      />
    </svg>
  );
}

function CookieIllustration({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <motion.circle
        cx="60"
        cy="60"
        r="40"
        stroke="currentColor"
        strokeWidth="3"
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, type: 'spring', stiffness: 200 }}
      />
      {/* Cookie chunks */}
      {[
        { cx: 45, cy: 50, r: 4 },
        { cx: 65, cy: 45, r: 3 },
        { cx: 70, cy: 65, r: 5 },
        { cx: 50, cy: 70, r: 3.5 },
        { cx: 55, cy: 55, r: 3 },
      ].map((chunk, i) => (
        <motion.circle
          key={i}
          cx={chunk.cx}
          cy={chunk.cy}
          r={chunk.r}
          fill="currentColor"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.3 + i * 0.1, type: 'spring', stiffness: 300 }}
        />
      ))}
      {/* Key icon overlay */}
      <motion.path
        d="M85 35L95 25M90 30L100 20"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        initial={{ opacity: 0, x: -5 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.8 }}
      />
    </svg>
  );
}

function DownloadIllustration({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Book */}
      <motion.rect
        x="35"
        y="20"
        width="50"
        height="65"
        rx="3"
        stroke="currentColor"
        strokeWidth="3"
        initial={{ y: -10, opacity: 0 }}
        animate={{ y: 20, opacity: 1 }}
        transition={{ duration: 0.5 }}
      />
      <motion.path
        d="M48 35H72M48 45H72M48 55H60"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.5 }}
        transition={{ delay: 0.3 }}
      />
      {/* Download arrow */}
      <motion.path
        d="M60 75V95M60 95L52 87M60 95L68 87"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ y: -5, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.5, type: 'spring' }}
      />
      {/* Sparkles */}
      {[
        { cx: 25, cy: 85 },
        { cx: 95, cy: 75 },
        { cx: 90, cy: 40 },
      ].map((pos, i) => (
        <motion.path
          key={i}
          d={`M${pos.cx} ${pos.cy - 4}V${pos.cy + 4}M${pos.cx - 4} ${pos.cy}H${pos.cx + 4}`}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 0.6 }}
          transition={{ delay: 0.7 + i * 0.15, type: 'spring' }}
        />
      ))}
    </svg>
  );
}

function BookIllustration({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <motion.path
        d="M30 30C30 25 35 20 45 20H75C85 20 90 25 90 30V90C90 95 85 100 75 100H45C35 100 30 95 30 90V30Z"
        stroke="currentColor"
        strokeWidth="3"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.8 }}
      />
      <motion.path
        d="M45 20V100"
        stroke="currentColor"
        strokeWidth="2"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.4, duration: 0.4 }}
      />
      <motion.path
        d="M55 40H75M55 55H75M55 70H65"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.5"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.5 }}
        transition={{ delay: 0.6 }}
      />
    </svg>
  );
}

const illustrationMap: Record<EmptyStateType, React.FC<{ className?: string }>> = {
  search: SearchIllustration,
  cookies: CookieIllustration,
  downloads: DownloadIllustration,
  book: BookIllustration,
  offline: SearchIllustration,
  generic: BookIllustration,
};

export function EnhancedEmptyState({
  type,
  icon: IconProp,
  title: titleProp,
  description: descriptionProp,
  variant = 'default',
  action,
  secondaryAction,
  steps,
  illustration,
  className,
  quote,
}: EmptyStateProps) {
  const { t } = useTranslation();
  const localizedContent = type
    ? {
        search: {
          ...defaultContent.search,
          title: t('search.start_search_title'),
          description: t('search.start_search'),
          quote: t('search.start_search_quote'),
        },
        cookies: {
          ...defaultContent.cookies,
          title: t('auth.cookies.empty_title'),
          description: t('auth.cookies.empty_description'),
          steps: t('auth.cookies.empty_steps', { returnObjects: true }) as string[],
        },
        downloads: {
          ...defaultContent.downloads,
          title: t('download.progress.empty_title'),
          description: t('download.progress.empty_description'),
          steps: t('download.progress.empty_steps', { returnObjects: true }) as string[],
        },
        book: {
          ...defaultContent.book,
          title: t('download.chapters.no_book_title'),
          description: t('download.chapters.no_book_description'),
          steps: t('download.chapters.no_book_steps', { returnObjects: true }) as string[],
        },
        offline: {
          ...defaultContent.offline,
          title: t('errors.network'),
          description: t('errors.network_description'),
        },
        generic: {
          ...defaultContent.generic,
          title: t('search.no_results_title', { defaultValue: 'No content' }),
          description: t('search.no_results_description', { defaultValue: 'Nothing to display.' }),
        },
      }[type]
    : null;
  const content = localizedContent ?? (type ? defaultContent[type] : null);
  const Icon: PhosphorIcon | null =
    typeof IconProp === 'string'
      ? iconMap[IconProp] || content?.icon || FolderOpen
      : IconProp || content?.icon || null;
  const title =
    titleProp ||
    content?.title ||
    t('search.no_results_title', { defaultValue: 'No content' });
  const description = descriptionProp || content?.description || '';
  const finalSteps = steps || content?.steps;
  const finalQuote = quote || content?.quote;

  const IllustrationComponent = type ? illustrationMap[type] : null;

  const variants = {
    default: 'py-12 px-6',
    compact: 'py-8 px-4',
    inline: 'py-4 px-3',
    inspirational: 'py-16 px-8',
  };

  return (
    <motion.div
      className={cn('flex flex-col items-center text-center', variants[variant], className)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {/* Ilustración animada */}
      {IllustrationComponent && !illustration && (
        <motion.div
          className={cn(
            'mb-6 text-muted-foreground/60',
            variant === 'compact' && 'mb-4',
            variant === 'inline' && 'mb-3'
          )}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
        >
          <IllustrationComponent className="h-24 w-24" />
        </motion.div>
      )}

      {illustration && (
        <div
          className={cn('mb-6', variant === 'compact' && 'mb-4', variant === 'inline' && 'mb-3')}
        >
          {illustration}
        </div>
      )}

      {/* Icono de respaldo */}
      {!IllustrationComponent && Icon && (
        <motion.div
          className={cn(
            'mb-4 rounded-2xl bg-gradient-to-br from-muted to-muted/50 p-4 text-muted-foreground',
            variant === 'compact' && 'mb-3 p-3',
            variant === 'inline' && 'mb-2 p-2',
            variant === 'inspirational' && 'mb-6 p-5'
          )}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, type: 'spring' }}
          whileHover={{ scale: 1.05 }}
        >
          <Icon
            className={cn(
              'h-10 w-10',
              variant === 'compact' && 'h-7 w-7',
              variant === 'inline' && 'h-5 w-5',
              variant === 'inspirational' && 'h-12 w-12'
            )}
            weight="regular"
          />
        </motion.div>
      )}

      {/* Título */}
      <motion.h3
        className={cn(
          'font-semibold text-foreground leading-tight',
          variant === 'default' && 'text-lg',
          variant === 'compact' && 'text-base',
          variant === 'inline' && 'text-sm',
          variant === 'inspirational' && 'text-xl'
        )}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        {title}
      </motion.h3>

      {/* Descripción */}
      {description && (
        <motion.p
          className={cn(
            'mt-2 text-muted-foreground leading-relaxed',
            variant === 'default' && 'text-sm max-w-[320px]',
            variant === 'compact' && 'text-xs max-w-[260px]',
            variant === 'inline' && 'text-xs max-w-[200px]',
            variant === 'inspirational' && 'text-sm max-w-[380px]'
          )}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {description}
        </motion.p>
      )}

      {/* Quote inspiracional */}
      {finalQuote && variant === 'inspirational' && (
        <motion.blockquote
          className="mt-4 text-sm italic text-muted-foreground/80 max-w-[340px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
        >
          &ldquo;{finalQuote}&rdquo;
        </motion.blockquote>
      )}

      {/* Pasos guiados */}
      {finalSteps && finalSteps.length > 0 && (
        <motion.div
          className={cn('mt-6 w-full max-w-[320px]', variant === 'compact' && 'mt-4 max-w-[260px]')}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t('common.how_to_start')}
          </p>
          <ol className="space-y-2 text-left">
            {finalSteps.map((step, i) => (
              <motion.li
                key={i}
                className="flex items-start gap-3 text-sm"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.1 }}
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                  {i + 1}
                </span>
                <span className="text-muted-foreground">{step}</span>
              </motion.li>
            ))}
          </ol>
        </motion.div>
      )}

      {/* Acciones */}
      {(action || secondaryAction) && (
        <motion.div
          className={cn(
            'mt-6 flex flex-wrap items-center justify-center gap-3',
            variant === 'compact' && 'mt-4',
            variant === 'inline' && 'mt-3'
          )}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          {action && (
            <motion.button
              type="button"
              onClick={action.onClick}
              className={cn(
                'group inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-all duration-200',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                action.variant === 'secondary' || !action.variant
                  ? 'border border-border bg-background text-foreground hover:bg-accent hover:border-primary/30 focus-visible:ring-ring'
                  : action.variant === 'ghost'
                    ? 'text-primary hover:bg-primary/5 focus-visible:ring-primary/30'
                    : 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-md hover:shadow-lg hover:-translate-y-0.5 focus-visible:ring-primary'
              )}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {action.label}
              {action.icon && (
                <action.icon
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  weight="regular"
                />
              )}
              {!action.icon && action.variant !== 'ghost' && (
                <ArrowRight
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  weight="regular"
                />
              )}
            </motion.button>
          )}

          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline transition-colors"
            >
              {secondaryAction.label}
            </button>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

// Exportar tipos para usar en otros componentes
export type { EmptyStateProps as EnhancedEmptyStateProps };
