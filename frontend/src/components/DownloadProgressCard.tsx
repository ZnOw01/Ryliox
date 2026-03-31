import { useDownloadManager } from '../hooks/useDownloadManager';
import { ChapterSelector } from './download-progress/ChapterSelector';
import { DownloadActions } from './download-progress/DownloadActions';
import { ErrorNotice } from './download-progress/ErrorNotice';
import { FormatSelector } from './download-progress/FormatSelector';
import { ProgressStatus } from './download-progress/ProgressStatus';
import { SseStatusBadge } from './download-progress/SseStatusBadge';
import { cn } from '../lib/cn';
import { DownloadSimple, BookOpen, Warning } from '@phosphor-icons/react';
import { OptimizedFadeIn } from './motion/OptimizedAppear';
import { useTranslation } from 'react-i18next';

export function DownloadProgressCard() {
  const { t } = useTranslation();
  const manager = useDownloadManager();
  const canForceReconnect = manager.sseStatus === 'error';
  const formatDescriptions = manager.formatsQuery.data?.descriptions;
  const chapters = manager.chaptersQuery.data?.chapters ?? [];
  // Formats that can only download the full book (e.g. epub) cannot use chapter selection
  const chapterSelectable = !manager.bookOnlyFormats.has(manager.format);

  return (
    <OptimizedFadeIn direction="up" delay={150}>
      <section
        id="download-section"
        className="soft-rise flex min-w-0 scroll-mt-28 flex-col overflow-visible rounded-2xl border border-border bg-card/90 shadow-panel backdrop-blur-sm"
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
            <SseStatusBadge status={manager.sseStatus} />
          </div>

          <div className="mb-4 grid gap-4 sm:grid-cols-2">
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
                    : 'border-border bg-muted/50 text-muted-foreground italic'
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
            error={manager.chaptersQuery.error}
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
                {t('download.chapters.not_selectable', { format: manager.format.toUpperCase() })}
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
            canForceReconnect={canForceReconnect}
            onForceReconnect={manager.forceReconnect}
          />

          {manager.formatsQuery.error ? <ErrorNotice error={manager.formatsQuery.error} /> : null}
          {manager.progressQuery.error ? <ErrorNotice error={manager.progressQuery.error} /> : null}
          {manager.startMutation.error ? <ErrorNotice error={manager.startMutation.error} /> : null}
          {manager.cancelMutation.error ? (
            <ErrorNotice error={manager.cancelMutation.error} />
          ) : null}

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
