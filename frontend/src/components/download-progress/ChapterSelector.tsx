import type { ChapterSummary, SearchBook } from '../../lib/types';
import { ErrorNotice } from './ErrorNotice';
import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../lib/cn';
import {
  CheckSquare,
  Square,
  Info,
  FileText,
  Spinner,
  Rows,
  BookOpen,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '../ui/Badge';
import { EnhancedEmptyState } from '../ui/EnhancedEmptyState';
import { Skeleton } from '../ui/Skeleton';
import {
  AnimatedLayoutGroup,
  StaggeredLayoutContainer,
  StaggeredLayoutItem,
} from '../motion/LayoutAnimations';
import { OptimizedFadeIn } from '../motion/OptimizedAppear';
import { useTranslation } from 'react-i18next';

type ChapterRowProps = {
  index: number;
  style?: React.CSSProperties;
  chapter: ChapterSummary;
  selectable: boolean;
  selectedChapterSet: Set<number>;
  onToggleChapter: (chapterIndex: number) => void;
};

// Componente memoizado para renderizar cada fila (compatible con react-window cuando se instale)
const ChapterRow = React.memo(function ChapterRow({
  index,
  style,
  chapter,
  selectable,
  selectedChapterSet,
  onToggleChapter,
}: ChapterRowProps) {
  const { t } = useTranslation();

  if (!chapter) return null;

  const checked = selectable && selectedChapterSet.has(chapter.index);

  if (!selectable) {
    // Fila de solo lectura — sin checkbox, sin interacción
    return (
      <motion.div
        layout
        style={style}
        className="flex min-h-touch min-w-0 items-center gap-3 rounded-lg px-3 py-2"
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.03, duration: 0.2 }}
      >
        <FileText
          className="h-4 w-4 shrink-0 text-muted-foreground"
          weight="regular"
          aria-hidden="true"
        />
        <span className="block min-w-0 truncate text-sm leading-tight text-muted-foreground">
          {chapter.title}
        </span>
      </motion.div>
    );
  }

  return (
    <motion.label
      layout
      layoutId={`chapter-${chapter.index}`}
      style={style}
      className={cn(
        'group flex min-h-touch min-w-0 cursor-pointer items-start gap-3 rounded-lg px-3 py-2 text-sm leading-tight transition-all duration-150 hover:bg-background focus-within:ring-2 focus-within:ring-ring',
        checked ? 'bg-primary/5' : 'hover:shadow-sm'
      )}
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03, duration: 0.2 }}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      <motion.div
        layoutId={`checkbox-${chapter.index}`}
        className={cn(
          'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
          checked
            ? 'border-primary bg-primary text-primary-foreground'
            : 'border-input bg-background text-transparent group-hover:border-muted-foreground'
        )}
        initial={checked ? { scale: 1 } : { scale: 1 }}
        animate={checked ? { scale: [1, 1.15, 1] } : { scale: 1 }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
      >
        <CheckSquare className="h-3.5 w-3.5" weight="regular" aria-hidden="true" />
      </motion.div>
      <input
        type="checkbox"
        checked={checked}
        onChange={() => onToggleChapter(chapter.index)}
        className="sr-only"
        aria-label={t('download.chapters.select_chapter_aria', { title: chapter.title })}
      />
      <motion.span layoutId={`title-${chapter.index}`} className="min-w-0 overflow-hidden">
        <span
          className={cn(
            'block truncate leading-relaxed',
            checked ? 'font-medium text-primary' : 'text-foreground'
          )}
        >
          {chapter.title}
        </span>
      </motion.span>
    </motion.label>
  );
});

type ChapterSelectorProps = {
  chapters: ChapterSummary[];
  error: unknown;
  hasData: boolean;
  isFetching: boolean;
  isLoading: boolean;
  onClear: () => void;
  onSelectAll: () => void;
  onToggleChapter: (chapterIndex: number) => void;
  selectedBook: SearchBook | null;
  selectedChapterIndexes: number[];
  selectedChapterSet: Set<number>;
  /** When false the current format downloads the whole book — checkboxes and action buttons are hidden. */
  selectable: boolean;
  totalChapters: number;
  /** Accessible label for the chapter selector region */
  ariaLabel?: string;
};

export function ChapterSelector({
  chapters,
  error,
  hasData,
  isFetching,
  isLoading,
  onClear,
  onSelectAll,
  onToggleChapter,
  selectedBook,
  selectedChapterIndexes,
  selectedChapterSet,
  selectable,
  totalChapters,
  ariaLabel,
}: ChapterSelectorProps) {
  const { t } = useTranslation();
  // Altura por capítulo: ~44px (padding + línea de texto)
  const ITEM_HEIGHT = 44;
  const MAX_LIST_HEIGHT = 224; // max-h-56 = 14rem = 224px

  return (
    <OptimizedFadeIn direction="up" delay={100}>
      <div
        className="mb-4 overflow-hidden rounded-xl border border-border bg-muted/50"
        role="region"
        aria-label={ariaLabel || t('download.chapters.aria_label')}
      >
        {/* ── Encabezado ── */}
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3">
          <div className="flex items-center gap-2">
            <Rows className="h-4 w-4 text-muted-foreground" weight="regular" aria-hidden="true" />
            <p
              className="text-sm font-semibold leading-tight text-foreground"
              id="chapter-selector-heading"
            >
              {t('download.chapters.title')}
            </p>
          </div>
          {selectable ? (
            <Badge
              variant={selectedChapterIndexes.length > 0 ? 'default' : 'secondary'}
              size="sm"
              aria-live="polite"
              aria-atomic="true"
              aria-describedby="chapter-selector-heading"
            >
              {t('download.chapters.selected_count', { count: selectedChapterIndexes.length })}/
              {totalChapters}
            </Badge>
          ) : (
            <Badge variant="secondary" size="sm">
              {t('download.chapters.total_count', { count: totalChapters })}
            </Badge>
          )}
        </div>

        {/* ── Aviso de libro completo ── */}
        {!selectable && (
          <div
            className="flex items-start gap-3 border-b border-border bg-info/10 px-4 py-3"
            role="note"
          >
            <Info
              className="mt-0.5 h-4 w-4 shrink-0 text-info"
              weight="regular"
              aria-hidden="true"
            />
            <p className="text-xs leading-relaxed text-info-foreground">
              {t('download.chapters.full_book_notice')}
            </p>
          </div>
        )}

        {/* ── Estado vacío mejorado ── */}
        {!selectedBook ? (
          <EnhancedEmptyState type="book" variant="compact" className="py-8" />
        ) : null}

        {/* ── Esqueleto de carga ── */}
        {selectedBook && isLoading ? (
          <div className="space-y-3 p-4" role="status" aria-live="polite" aria-busy="true">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Spinner className="h-4 w-4 animate-spin" weight="bold" aria-hidden="true" />
              {t('download.chapters.loading')}
            </div>
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-11 w-full rounded-lg" />
              ))}
            </div>
          </div>
        ) : null}
        {selectedBook && !isLoading && isFetching ? (
          <div
            className="flex items-center gap-2 px-4 py-3 text-xs text-muted-foreground"
            role="status"
            aria-live="polite"
          >
            <Spinner className="h-4 w-4 animate-spin" weight="bold" aria-hidden="true" />
            {t('download.chapters.updating')}
          </div>
        ) : null}

        {/* ── Lista de capítulos ── */}
        {selectedBook && hasData ? (
          <>
            {/* Botones de acción — solo cuando es seleccionable */}
            {selectable && (
              <div
                className="grid gap-3 p-3 sm:grid-cols-2"
                role="group"
                aria-label={t('download.chapters.title')}
              >
                <button
                  type="button"
                  onClick={onSelectAll}
                  disabled={chapters.length === 0 || isLoading}
                  className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2.5 text-sm font-medium text-foreground transition hover:border-primary/30 hover:bg-primary/5 hover:text-primary disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <CheckSquare className="h-4 w-4" weight="regular" aria-hidden="true" />
                  {t('download.chapters.select_all')}
                </button>
                <button
                  type="button"
                  onClick={onClear}
                  disabled={selectedChapterIndexes.length === 0 || isLoading}
                  className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2.5 text-sm font-medium text-foreground transition hover:border-primary/30 hover:bg-primary/5 hover:text-primary disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Square className="h-4 w-4" weight="regular" aria-hidden="true" />
                  {t('download.chapters.clear_selection')}
                </button>
              </div>
            )}

            <div className="chapter-scroll overflow-x-hidden overflow-y-auto">
              <AnimatedLayoutGroup className="space-y-1 p-3">
                {chapters.map((chapter, index) => (
                  <ChapterRow
                    key={chapter.index}
                    index={index}
                    chapter={chapter}
                    selectable={selectable}
                    selectedChapterSet={selectedChapterSet}
                    onToggleChapter={onToggleChapter}
                  />
                ))}
              </AnimatedLayoutGroup>
            </div>
          </>
        ) : null}

        {error ? <ErrorNotice error={error} /> : null}
      </div>
    </OptimizedFadeIn>
  );
}
