import {
  CheckSquare,
  FileText,
  Rows3,
  Loader2,
  Square,
  Search,
  ArrowDownUp,
  Clock,
  Info,
} from 'lucide-react';
import { motion } from 'framer-motion';
import React, { memo, useId, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import type { ChapterSummary, SearchBook } from '../../lib/types';
import { AnimatedLayoutGroup } from '../motion/LayoutAnimations';
import { OptimizedFadeIn } from '../motion/OptimizedAppear';
import { Badge } from '../ui/Badge';
import { EnhancedEmptyState } from '../ui/EnhancedEmptyState';
import { Skeleton } from '../ui/Skeleton';
import { ErrorNotice } from './ErrorNotice';
import { formatReadingMinutes, formatTotalReadingTime } from './utils';

type ChapterRowProps = {
  style?: React.CSSProperties;
  chapter: ChapterSummary;
  selectable: boolean;
  selectedChapterSet: Set<number>;
  onToggleChapter: (chapterIndex: number) => void;
};

// Componente memoizado para renderizar cada fila
const ChapterRow = memo(function ChapterRow({
  style,
  chapter,
  selectable,
  selectedChapterSet,
  onToggleChapter,
}: ChapterRowProps) {
  const { t } = useTranslation();

  if (!chapter) return null;

  const checked = selectable && selectedChapterSet.has(chapter.index);
  const readingTime = formatReadingMinutes(chapter.minutes, t);
  const formattedIndex = String(chapter.index + 1).padStart(2, '0');

  if (!selectable) {
    // Fila de solo lectura — sin checkbox
    return (
      <motion.div
        layout
        style={style}
        className="flex min-h-touch min-w-0 items-center justify-between gap-3 rounded-lg border border-transparent px-3 py-2 text-sm transition-colors hover:bg-muted/40"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-5 w-6 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-mono font-medium text-muted-foreground">
            {formattedIndex}
          </span>
          <FileText
            className="h-4 w-4 shrink-0 text-muted-foreground"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <span className="block min-w-0 truncate text-sm leading-tight text-muted-foreground">
            {chapter.title}
          </span>
        </div>
        {readingTime && (
          <span className="shrink-0 text-[10px] text-muted-foreground">{readingTime}</span>
        )}
      </motion.div>
    );
  }

  return (
    <motion.label
      layout
      layoutId={`chapter-${chapter.index}`}
      style={style}
      className={cn(
        'group flex min-h-touch min-w-0 cursor-pointer items-center justify-between gap-3 rounded-xl border p-2.5 sm:px-3 text-sm leading-tight transition-all duration-150 focus-within:ring-2 focus-within:ring-ring',
        checked
          ? 'border-primary/40 bg-primary/5 shadow-xs'
          : 'border-border bg-card/60 hover:border-border hover:bg-accent/40'
      )}
    >
      <div className="flex min-w-0 items-center gap-3 flex-1">
        <motion.div
          layoutId={`checkbox-${chapter.index}`}
          className={cn(
            'flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
            checked
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-input bg-background text-transparent group-hover:border-muted-foreground'
          )}
          initial={{ scale: 1 }}
          animate={checked ? { scale: [1, 1.15, 1] } : { scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        >
          <CheckSquare className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
        </motion.div>

        <span
          className={cn(
            'flex h-5 w-6 shrink-0 items-center justify-center rounded text-[10px] font-mono font-semibold transition-colors',
            checked ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
          )}
        >
          {formattedIndex}
        </span>

        <input
          type="checkbox"
          checked={checked}
          onChange={() => onToggleChapter(chapter.index)}
          className="sr-only"
          aria-label={t('download.chapters.select_chapter_aria', {
            title: chapter.title,
          })}
        />
        <motion.span layoutId={`title-${chapter.index}`} className="min-w-0 flex-1 overflow-hidden">
          <span
            className={cn(
              'block truncate font-medium',
              checked ? 'text-primary' : 'text-foreground'
            )}
          >
            {chapter.title}
          </span>
        </motion.span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {readingTime && (
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            {readingTime}
          </span>
        )}
        {chapter.pages && (
          <Badge variant="outline" size="sm" className="text-[10px] px-1.5 py-0">
            {chapter.pages}p
          </Badge>
        )}
      </div>
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
  const idPrefix = useId().replace(/:/g, '');
  const headingId = `${idPrefix}-heading`;
  const filterId = `${idPrefix}-filter`;
  const rangeStartId = `${idPrefix}-range-start`;
  const rangeEndId = `${idPrefix}-range-end`;

  const [showAllChapters, setShowAllChapters] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');
  const [rangeStart, setRangeStart] = useState<number | ''>('');
  const [rangeEnd, setRangeEnd] = useState<number | ''>('');

  const filteredChapters = useMemo(() => {
    if (!filterQuery) return chapters;
    const q = filterQuery.toLowerCase();
    return chapters.filter(c => c.title.toLowerCase().includes(q));
  }, [chapters, filterQuery]);

  const selectedStats = useMemo(() => {
    if (selectedChapterIndexes.length === 0) return null;
    let totalMinutes = 0;
    let totalPages = 0;
    let hasMinutes = false;
    let hasPages = false;

    chapters.forEach(c => {
      if (selectedChapterSet.has(c.index)) {
        if (typeof c.minutes === 'number' && c.minutes > 0) {
          totalMinutes += c.minutes;
          hasMinutes = true;
        }
        if (typeof c.pages === 'number' && c.pages > 0) {
          totalPages += c.pages;
          hasPages = true;
        }
      }
    });

    return {
      time: hasMinutes ? formatTotalReadingTime(totalMinutes) : null,
      pages: hasPages ? totalPages : null,
    };
  }, [chapters, selectedChapterIndexes, selectedChapterSet]);

  const handleSelectFiltered = () => {
    filteredChapters.forEach(c => {
      if (!selectedChapterSet.has(c.index)) {
        onToggleChapter(c.index);
      }
    });
  };

  const handleApplyRange = () => {
    if (rangeStart === '' || rangeEnd === '') return;
    const start = Math.min(Number(rangeStart), Number(rangeEnd));
    const end = Math.max(Number(rangeStart), Number(rangeEnd));

    chapters.forEach(c => {
      const humanIndex = c.index + 1;
      if (humanIndex >= start && humanIndex <= end) {
        if (!selectedChapterSet.has(c.index)) {
          onToggleChapter(c.index);
        }
      }
    });
  };

  const handleInvertSelection = () => {
    chapters.forEach(c => {
      onToggleChapter(c.index);
    });
  };

  const handleSelectFirstN = (n: number) => {
    chapters.slice(0, n).forEach(c => {
      if (!selectedChapterSet.has(c.index)) {
        onToggleChapter(c.index);
      }
    });
  };

  const handleSelectLastN = (n: number) => {
    const total = chapters.length;
    chapters.slice(Math.max(0, total - n)).forEach(c => {
      if (!selectedChapterSet.has(c.index)) {
        onToggleChapter(c.index);
      }
    });
  };

  const visibleChapters = useMemo(() => {
    if (selectable) return filteredChapters;
    if (showAllChapters) return chapters;
    return chapters.slice(0, 3);
  }, [selectable, filteredChapters, chapters, showAllChapters]);

  return (
    <OptimizedFadeIn direction="up" delay={100}>
      <div
        className="mb-4 overflow-hidden rounded-xl border border-border bg-card/40"
        role="region"
        aria-labelledby={ariaLabel ? undefined : headingId}
        aria-label={ariaLabel}
      >
        {/* ── Encabezado ── */}
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <Rows3 className="h-4 w-4 text-primary" strokeWidth={1.75} aria-hidden="true" />
            <p className="text-sm font-semibold leading-tight text-foreground" id={headingId}>
              {t('download.chapters.title')}
            </p>
          </div>
          {selectable ? (
            <div className="flex items-center gap-2">
              {selectedStats && (selectedStats.time || selectedStats.pages) && (
                <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                  {selectedStats.time && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-primary" />
                      {selectedStats.time}
                    </span>
                  )}
                  {selectedStats.time && selectedStats.pages && <span>•</span>}
                  {selectedStats.pages && (
                    <span>
                      {selectedStats.pages} {t('common.pages')}
                    </span>
                  )}
                </span>
              )}
              <Badge
                variant={selectedChapterIndexes.length > 0 ? 'default' : 'secondary'}
                size="sm"
                aria-live="polite"
                aria-atomic="true"
                aria-describedby={headingId}
              >
                {t('download.chapters.selected_count', {
                  count: selectedChapterIndexes.length,
                })}
                /{totalChapters}
              </Badge>
            </div>
          ) : (
            <Badge variant="secondary" size="sm">
              {t('download.chapters.total_count', { count: totalChapters })}
            </Badge>
          )}
        </div>

        {/* ── Aviso de libro completo ── */}
        {!selectable && (
          <div
            className="flex items-start gap-3 border-b border-blue-100 bg-blue-50/60 dark:border-blue-900/30 dark:bg-blue-950/20 px-4 py-3"
            role="note"
          >
            <Info
              className="mt-0.5 h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            <p className="text-xs leading-relaxed text-blue-900 dark:text-blue-200">
              {t('download.chapters.full_book_notice')}
            </p>
          </div>
        )}

        {/* ── Estado vacío mejorado ── */}
        {!selectedBook ? (
          <EnhancedEmptyState type="book" variant="compact" steps={[]} className="py-4" />
        ) : null}

        {/* ── Esqueleto de carga ── */}
        {selectedBook && isLoading ? (
          <div className="space-y-3 p-4" role="status" aria-live="polite" aria-busy="true">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2
                className="h-4 w-4 animate-spin text-primary"
                strokeWidth={2.5}
                aria-hidden="true"
              />
              {t('download.chapters.loading')}
            </div>
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-11 w-full rounded-xl" />
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
            <Loader2
              className="h-4 w-4 animate-spin text-primary"
              strokeWidth={2.5}
              aria-hidden="true"
            />
            {t('download.chapters.updating')}
          </div>
        ) : null}

        {/* ── Lista de capítulos ── */}
        {selectedBook && hasData ? (
          <>
            {/* Controles avanzados para PDF */}
            {selectable && (
              <div className="border-b border-border bg-muted/20 p-3 space-y-3">
                {/* Botones de acción principales */}
                <div className="grid gap-2 sm:grid-cols-3">
                  <button
                    type="button"
                    onClick={onSelectAll}
                    disabled={chapters.length === 0 || isLoading}
                    className="mobile-full min-h-touch inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <CheckSquare
                      className="h-3.5 w-3.5 text-primary"
                      strokeWidth={2}
                      aria-hidden="true"
                    />
                    {t('download.chapters.select_all')}
                  </button>
                  <button
                    type="button"
                    onClick={onClear}
                    disabled={selectedChapterIndexes.length === 0 || isLoading}
                    className="mobile-full min-h-touch inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Square className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                    {t('download.chapters.clear_selection')}
                  </button>
                  <button
                    type="button"
                    onClick={handleInvertSelection}
                    disabled={chapters.length === 0 || isLoading}
                    className="mobile-full min-h-touch inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <ArrowDownUp className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                    {t('download.chapters.invert_selection') || 'Invertir'}
                  </button>
                </div>

                {/* Búsqueda de capítulos y Selección por Rango */}
                <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                  {/* Búsqueda */}
                  <div className="relative">
                    <label htmlFor={filterId} className="sr-only">
                      {t('download.chapters.search_label')}
                    </label>
                    <input
                      id={filterId}
                      type="text"
                      value={filterQuery}
                      onChange={e => setFilterQuery(e.target.value)}
                      placeholder={t('download.chapters.search_placeholder')}
                      className="min-h-touch w-full rounded-lg border border-input bg-background pl-8 pr-8 py-2 text-xs text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring"
                    />
                    <div className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                      <Search className="h-3.5 w-3.5" strokeWidth={2.5} />
                    </div>
                    {filterQuery && (
                      <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                        <button
                          type="button"
                          onClick={handleSelectFiltered}
                          className="text-[10px] bg-primary/10 text-primary font-semibold px-1.5 py-0.5 rounded hover:bg-primary/20 transition"
                          title={t('download.chapters.select_matching')}
                        >
                          +{filteredChapters.length}
                        </button>
                        <button
                          type="button"
                          onClick={() => setFilterQuery('')}
                          className="text-muted-foreground hover:text-foreground text-sm font-bold px-1"
                          aria-label={t('download.chapters.clear_search')}
                        >
                          ×
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Rango */}
                  <div className="flex items-center gap-2 justify-end sm:justify-start">
                    <label htmlFor={rangeStartId} className="sr-only">
                      {t('download.chapters.range_start')}
                    </label>
                    <input
                      id={rangeStartId}
                      type="number"
                      value={rangeStart}
                      onChange={e => setRangeStart(e.target.value ? parseInt(e.target.value) : '')}
                      placeholder={t('download.chapters.range_from')}
                      min="1"
                      max={chapters.length}
                      className="w-14 rounded-lg border border-input bg-background px-2 py-2 text-xs text-center text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring"
                    />
                    <span className="text-xs text-muted-foreground">-</span>
                    <label htmlFor={rangeEndId} className="sr-only">
                      {t('download.chapters.range_end')}
                    </label>
                    <input
                      id={rangeEndId}
                      type="number"
                      value={rangeEnd}
                      onChange={e => setRangeEnd(e.target.value ? parseInt(e.target.value) : '')}
                      placeholder={t('download.chapters.range_to')}
                      min="1"
                      max={chapters.length}
                      className="w-14 rounded-lg border border-input bg-background px-2 py-2 text-xs text-center text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring"
                    />
                    <button
                      type="button"
                      onClick={handleApplyRange}
                      disabled={rangeStart === '' || rangeEnd === ''}
                      className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {t('download.chapters.apply_range')}
                    </button>
                  </div>
                </div>

                {/* Presets */}
                <div className="flex flex-wrap items-center gap-2 border-t border-border/50 pt-2">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mr-1">
                    {t('download.chapters.presets')}:
                  </span>
                  <button
                    type="button"
                    onClick={() => handleSelectFirstN(5)}
                    className="rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition"
                  >
                    {t('download.chapters.first_n', { count: 5 })}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelectFirstN(10)}
                    className="rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition"
                  >
                    {t('download.chapters.first_n', { count: 10 })}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelectLastN(5)}
                    className="rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition"
                  >
                    {t('download.chapters.last_n', { count: 5 })}
                  </button>
                </div>
              </div>
            )}

            <div className="chapter-scroll overflow-x-hidden overflow-y-auto max-h-[320px] p-2">
              <AnimatedLayoutGroup className="space-y-1.5">
                {visibleChapters.map(chapter => (
                  <ChapterRow
                    key={chapter.index}
                    chapter={chapter}
                    selectable={selectable}
                    selectedChapterSet={selectedChapterSet}
                    onToggleChapter={onToggleChapter}
                  />
                ))}
              </AnimatedLayoutGroup>
            </div>

            {/* Mostrar botón para expandir/colapsar en EPUB/HTML */}
            {!selectable && chapters.length > 3 && (
              <div className="flex justify-center border-t border-border bg-muted/20 p-2.5">
                <button
                  type="button"
                  onClick={() => setShowAllChapters(!showAllChapters)}
                  className="text-xs font-semibold text-primary hover:text-primary-foreground hover:bg-primary px-3 py-1.5 rounded-lg border border-primary/30 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {showAllChapters
                    ? t('download.chapters.view_less')
                    : t('download.chapters.view_all', {
                        count: chapters.length,
                      })}
                </button>
              </div>
            )}
          </>
        ) : null}

        {error ? <ErrorNotice error={error} /> : null}
      </div>
    </OptimizedFadeIn>
  );
}
