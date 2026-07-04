import { useDownloadManager } from '../hooks/useDownloadManager';
import { ChapterSelector } from './download-progress/ChapterSelector';
import { DownloadActions } from './download-progress/DownloadActions';
import { ErrorNotice } from './download-progress/ErrorNotice';
import { FormatSelector } from './download-progress/FormatSelector';
import { ProgressStatus } from './download-progress/ProgressStatus';
import { SseStatusBadge } from './download-progress/SseStatusBadge';
import { cn } from '../lib/cn';
import { DownloadSimple, BookOpen, Warning, ArrowClockwise } from '@phosphor-icons/react';
import { OptimizedFadeIn } from './motion/OptimizedAppear';
import { useTranslation } from 'react-i18next';
import { useMemo } from 'react';
import { parseApiError } from '../lib/api-error';

export function DownloadProgressCard() {
  const { t } = useTranslation();
  const manager = useDownloadManager();
  const canForceReconnect = manager.sseStatus === 'error';
  const formatDescriptions = manager.formatsQuery.data?.descriptions;
  const chapters = manager.chaptersQuery.data?.chapters ?? [];
  // Formats that can only download the full book (e.g. epub) cannot use chapter selection
  const chapterSelectable = !manager.bookOnlyFormats.has(manager.format);

  const errors = useMemo(() => {
    return [
      manager.formatsQuery.error,
      manager.chaptersQuery.error,
      manager.progressQuery.error,
      manager.startMutation.error,
      manager.cancelMutation.error,
    ].filter(Boolean);
  }, [
    manager.formatsQuery.error,
    manager.chaptersQuery.error,
    manager.progressQuery.error,
    manager.startMutation.error,
    manager.cancelMutation.error,
  ]);

  const uniqueErrorMessages = useMemo(() => {
    const messages = new Set<string>();
    const unique: unknown[] = [];
    errors.forEach(err => {
      const parsed = parseApiError(err);
      if (!messages.has(parsed.message)) {
        messages.add(parsed.message);
        unique.push(err);
      }
    });
    return unique;
  }, [errors]);

  return (
    <OptimizedFadeIn direction="up" delay={150}>
      <section
        id="download-section"
        className="premium-card flex min-w-0 scroll-mt-28 flex-col overflow-visible"
      >
        <div className="flex flex-col p-4 sm:p-5">
          <div className="mb-4 flex flex-shrink-0 flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <DownloadSimple
                className="h-5 w-5 text-primary"
                weight="regular"
                aria-hidden="true"
              />
              <h2 className="text-base font-semibold leading-tight text-foreground sm:text-lg">
                {t('download.title')}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <SseStatusBadge status={manager.sseStatus} />
              {canForceReconnect ? (
                <button
                  type="button"
                  onClick={manager.forceReconnect}
                  className="rounded-full border border-warning/30 bg-warning/10 hover:bg-warning/20 px-2.5 py-0.5 text-xs font-semibold text-warning-foreground transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-warning"
                  title={t('download.sse.reconnect')}
                >
                  <ArrowClockwise className="h-3 w-3" weight="bold" />
                  <span>Reintentar</span>
                </button>
              ) : null}
            </div>
          </div>

          <div className="mb-4 grid gap-4 @md:grid-cols-2">
            <div className="min-w-0 text-sm leading-tight">
              <span className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <BookOpen className="h-4 w-4" weight="regular" aria-hidden="true" />
                {t('download.book.label')}
              </span>
              <div
                role="status"
                aria-live="polite"
                className={cn(
                  'mobile-full w-full min-w-0 truncate rounded-lg border px-3 py-2.5 text-sm leading-tight transition-colors',
                  manager.selectedBook
                    ? 'border-input bg-muted text-foreground'
                    : 'border-border bg-muted/50 text-neutral-500 dark:text-neutral-400 font-medium'
                )}
              >
                {manager.selectedBook ? manager.selectedBook.title : t('download.book.placeholder')}
              </div>
            </div>

            <FormatSelector
              format={manager.format}
              formats={manager.formats}
              descriptions={formatDescriptions}
              selectedFormatDescription={manager.selectedFormatDescription}
              hasChapterSelection={manager.hasChapterSelection}
              bookOnlyFormats={manager.bookOnlyFormats}
              isLoading={manager.formatsQuery.isLoading}
              onChange={newFormat => {
                manager.setFormat(newFormat);
                // Switching to a book-only format makes chapter selection invalid — clear it immediately
                if (manager.bookOnlyFormats.has(newFormat)) {
                  manager.clearSelectedChapters();
                }
              }}
            />
          </div>

          <ChapterSelector
            chapters={chapters}
            error={null}
            hasData={Boolean(manager.chaptersQuery.data)}
            isLoading={manager.chaptersLoading}
            isFetching={manager.chaptersRefreshing}
            onSelectAll={manager.selectAllChapters}
            onClear={manager.clearSelectedChapters}
            onToggleChapter={manager.toggleChapter}
            selectedBook={manager.selectedBook}
            selectedChapterIndexes={manager.selectedChapterIndexes}
            selectedChapterSet={manager.selectedChapterSet}
            selectable={chapterSelectable}
            totalChapters={manager.totalChapters}
          />

          {manager.invalidFormatWithChapterSelection ? (
            <div className="mb-4 flex items-start gap-3 rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm leading-tight text-warning-foreground">
              <Warning className="mt-0.5 h-4 w-4 shrink-0" weight="regular" aria-hidden="true" />
              <span>
                {t('download.chapters.not_selectable', {
                  format: manager.format.toUpperCase(),
                })}
              </span>
            </div>
          ) : null}

          <DownloadActions
            selectedBook={Boolean(manager.selectedBook)}
            skipImages={manager.skipImages}
            onSkipImagesChange={manager.setSkipImages}
            onStart={() => manager.startMutation.mutate()}
            onCancel={() => manager.cancelMutation.mutate()}
            startDisabledReason={manager.startDisabledReason}
            startPending={manager.startMutation.isPending}
            cancelPending={manager.cancelMutation.isPending}
            active={manager.active}
            invalidFormatWithChapterSelection={manager.invalidFormatWithChapterSelection}
            formatsDisabled={manager.formatsDisabled}
          />

          {uniqueErrorMessages.map((err, idx) => (
            <ErrorNotice key={idx} error={err} />
          ))}

          <ProgressStatus
            currentLabel={manager.currentLabel}
            progressPercent={manager.progressPercent}
            progress={manager.progressQuery.data}
          />
        </div>
      </section>
    </OptimizedFadeIn>
  );
}
