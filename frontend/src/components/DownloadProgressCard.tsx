import { TERMINAL_DOWNLOAD_STATES, useDownloadManager } from '../hooks/useDownloadManager';
import { ChapterSelector } from './download-progress/ChapterSelector';
import { DownloadActions } from './download-progress/DownloadActions';
import { ErrorNotice } from './download-progress/ErrorNotice';
import { FormatSelector } from './download-progress/FormatSelector';
import { ProgressStatus } from './download-progress/ProgressStatus';
import { SseStatusBadge } from './download-progress/SseStatusBadge';
import { cn } from '../lib/cn';
import { Download, BookOpen, AlertTriangle, RotateCw, CheckCircle2 } from 'lucide-react';
import { OptimizedFadeIn } from './motion/OptimizedAppear';
import { useTranslation } from 'react-i18next';
import { useEffect, useMemo, useRef } from 'react';
import { parseApiError } from '../lib/api-error';
import { announce } from './AriaLiveRegion';
import { toast } from './ui/BeautifulToast';
import { BookCover } from './ui/BookCover';

export function DownloadProgressCard() {
  const { t } = useTranslation();
  const manager = useDownloadManager();
  const canForceReconnect = manager.sseStatus === 'error';
  const formatDescriptions = manager.formatsQuery.data?.descriptions;
  const chapters = manager.chaptersQuery.data?.chapters ?? [];
  // Formats that can only download the full book (e.g. epub) cannot use chapter selection
  const chapterSelectable = !manager.bookOnlyFormats.has(manager.format);
  const notifiedTerminalRef = useRef<string | null>(null);

  useEffect(() => {
    const progress = manager.progressQuery.data;
    const status = progress?.status ?? '';
    if (!TERMINAL_DOWNLOAD_STATES.has(status)) {
      return;
    }

    const notificationKey = `${progress?.job_id ?? 'local'}:${status}`;
    if (notifiedTerminalRef.current === notificationKey) {
      return;
    }
    notifiedTerminalRef.current = notificationKey;

    if (status === 'completed') {
      const message = t('download.notifications.download_completed');
      toast.success(message);
      announce(message);
    } else if (status === 'error') {
      const message = progress?.error || t('download.notifications.download_error');
      toast.error(message);
      announce(message, 'assertive');
    } else {
      const message = t('download.notifications.download_cancelled');
      toast.info(message);
      announce(message);
    }
  }, [manager.progressQuery.data, t]);

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
        <div className="flex flex-col p-6">
          <div className="mb-5 flex flex-shrink-0 flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Download className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
              </div>
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
                  className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800 transition hover:bg-amber-100 flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
                  title={t('download.sse.reconnect')}
                >
                  <RotateCw className="h-3 w-3" strokeWidth={2.5} />
                  <span>{t('common.retry')}</span>
                </button>
              ) : null}
            </div>
          </div>

          {/* Selected Book Banner */}
          <div className="mb-4">
            <span className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5 text-primary" strokeWidth={2} aria-hidden="true" />
              {t('download.book.label')}
            </span>
            <div
              role="status"
              aria-live="polite"
              className={cn(
                'w-full min-w-0 rounded-xl border p-3 text-sm leading-tight transition-all',
                manager.selectedBook
                  ? 'border-primary/30 bg-primary/5 shadow-xs'
                  : 'border-border bg-muted/40 text-muted-foreground font-medium'
              )}
            >
              {manager.selectedBook ? (
                <div className="flex items-center gap-3">
                  <BookCover
                    src={manager.selectedBook.cover_url}
                    alt={manager.selectedBook.title}
                    size="sm"
                    aspectRatio="book"
                    showPlaceholderText={false}
                    className="shrink-0 rounded-md shadow-xs"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-foreground text-sm">
                      {manager.selectedBook.title}
                    </p>
                    {manager.selectedBook.authors && manager.selectedBook.authors.length > 0 && (
                      <p className="truncate text-xs text-muted-foreground mt-0.5">
                        {manager.selectedBook.authors.join(', ')}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0">
                    <CheckCircle2 className="h-5 w-5 text-primary fill-primary/10" />
                  </div>
                </div>
              ) : (
                <span className="text-muted-foreground">{t('download.book.placeholder')}</span>
              )}
            </div>
          </div>

          {/* Format Selector */}
          <div className="mb-4">
            <FormatSelector
              format={manager.format}
              formats={manager.formats}
              descriptions={formatDescriptions}
              hasChapterSelection={manager.hasChapterSelection}
              bookOnlyFormats={manager.bookOnlyFormats}
              isLoading={manager.formatsQuery.isLoading}
              onChange={newFormat => {
                manager.setFormat(newFormat);
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
            <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/80 dark:border-amber-900/30 dark:bg-amber-950/20 p-3.5 text-xs font-medium leading-relaxed text-amber-900 dark:text-amber-200">
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
                strokeWidth={2}
                aria-hidden="true"
              />
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
