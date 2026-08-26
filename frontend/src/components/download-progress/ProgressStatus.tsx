import { useId, useState } from 'react';
import type { TFunction } from 'i18next';
import {
  CheckCircle,
  Clock,
  FileText,
  FolderOpen,
  Copy,
  AlertCircle,
  Loader2,
  ChevronRight,
  BookOpen,
  Check,
} from 'lucide-react';

import { revealFile } from '../../lib/api';
import type { ProgressResponse } from '../../lib/types';
import { formatEta, formatStatusLabel } from './utils';
import { Badge } from '../ui/Badge';
import { toast } from '../ui/BeautifulToast';
import { cn } from '../../lib/cn';
import { useTranslation } from 'react-i18next';

type ProgressStatusProps = {
  currentLabel: string;
  progress: ProgressResponse | undefined;
  progressPercent: number;
};

export function ProgressStatus({ currentLabel, progress, progressPercent }: ProgressStatusProps) {
  const { t } = useTranslation();
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [revealingPath, setRevealingPath] = useState<string | null>(null);
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const idPrefix = useId().replace(/:/g, '');
  const etaLabel = formatEta(progress?.eta_seconds);
  const statusLabel = formatStatusLabel(currentLabel, t);
  const epubName = outputFileNames(progress?.epub);
  const pdfName = outputFileNames(progress?.pdf);
  const shouldShowSummaryMessage = Boolean(
    progress?.message && progress.message.toLowerCase() !== 'completed'
  );
  const hasTechnicalDetails = Boolean(progress?.details || progress?.code || progress?.error);
  const chapterProgress =
    typeof progress?.current_chapter === 'number' &&
    typeof progress?.total_chapters === 'number' &&
    progress.total_chapters > 0
      ? `${progress.current_chapter}/${progress.total_chapters}`
      : null;
  const isActive = progress?.status === 'running';
  const isQueued = progress?.status === 'queued';
  const isCompleted = progress?.status === 'completed';
  const isError = progress?.status === 'error';

  const progressToneClass = isCompleted
    ? 'bg-emerald-500'
    : isError
      ? 'bg-destructive'
      : isActive
        ? 'bg-primary'
        : 'bg-muted-foreground/30';

  const revealTargets = [
    ...(progress?.epub ? [progress.epub] : []),
    ...(progress?.pdf ? (Array.isArray(progress.pdf) ? progress.pdf : [progress.pdf]) : []),
    ...(progress?.trace_log ? [progress.trace_log] : []),
  ].filter(
    (value, index, array): value is string => Boolean(value) && array.indexOf(value) === index
  );

  async function handleReveal(path: string) {
    setActionMessage(null);
    setActionError(null);
    setRevealingPath(path);
    try {
      await revealFile(path);
      setActionMessage(t('download.progress.location_opened'));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t('errors.unknown_description'));
    } finally {
      setRevealingPath(null);
    }
  }

  async function handleCopy(value: string) {
    setActionMessage(null);
    setActionError(null);
    try {
      await navigator.clipboard.writeText(value);
      setCopiedPath(value);
      toast.success(t('download.progress.path_copied'));
      setTimeout(() => setCopiedPath(null), 2000);
    } catch {
      setActionError(t('download.progress.copy_failed'));
    }
  }

  // Active steps calculation for visual stepper
  const currentStep = isCompleted ? 4 : progressPercent > 80 ? 3 : isActive ? 2 : isQueued ? 1 : 0;

  return (
    <div className="mt-4 rounded-xl border border-border bg-card/60 p-4 shadow-xs">
      {/* Visual Stepper when download is started or completed */}
      {currentStep > 0 && (
        <div className="mb-4 grid grid-cols-4 gap-1 sm:gap-2">
          {[
            { step: 1, label: t('download.progress.steps.queued') || '1. En cola' },
            { step: 2, label: t('download.progress.steps.downloading') || '2. Descarga' },
            { step: 3, label: t('download.progress.steps.compiling') || '3. Empaque' },
            { step: 4, label: t('download.progress.steps.done') || '4. Listo' },
          ].map(s => {
            const isDone = currentStep > s.step || isCompleted;
            const isCurrent = currentStep === s.step && !isCompleted;
            return (
              <div
                key={s.step}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium transition-colors',
                  isDone
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold'
                    : isCurrent
                      ? 'bg-primary/10 text-primary font-semibold'
                      : 'bg-muted/40 text-muted-foreground/60'
                )}
              >
                <div
                  className={cn(
                    'flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px]',
                    isDone
                      ? 'bg-emerald-500 text-white'
                      : isCurrent
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                  )}
                >
                  {isDone ? <Check className="h-2.5 w-2.5 stroke-[3]" /> : s.step}
                </div>
                <span className="truncate hidden sm:inline">{s.label}</span>
              </div>
            );
          })}
        </div>
      )}

      <div
        className="mb-2 flex min-w-0 items-center justify-between gap-2 text-sm text-foreground"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span className="min-w-0 break-words font-semibold text-xs sm:text-sm">
          {t('download.progress.status_label')}: {statusLabel}
        </span>
        <Badge
          variant={isCompleted ? 'success' : isError ? 'error' : isActive ? 'default' : 'secondary'}
          size="sm"
        >
          {t('download.progress.percentage', { percent: progressPercent })}
        </Badge>
      </div>

      <div
        className="h-2.5 overflow-hidden rounded-full bg-muted shadow-inner"
        role="progressbar"
        aria-label={t('download.progress.aria_label')}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressPercent}
        aria-valuetext={t('download.progress.percentage_aria', {
          percent: progressPercent,
          status: statusLabel,
        })}
      >
        <div
          className={cn(
            'h-full transition-all duration-500 ease-out rounded-full',
            progressToneClass,
            isActive && 'progress-bar-active'
          )}
          style={{ width: `${progressPercent}%` }}
          aria-hidden="true"
        />
      </div>

      <div className="mt-3 space-y-2 text-sm text-foreground">
        {isCompleted ? (
          <div
            className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-950/20 px-3.5 py-2.5 text-sm font-semibold text-emerald-800 dark:text-emerald-300"
            role="status"
            aria-live="polite"
          >
            <CheckCircle
              className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400"
              strokeWidth={2}
              aria-hidden="true"
            />
            <span>{t('download.progress.completed_message')}</span>
          </div>
        ) : null}

        {typeof progress?.queue_position === 'number' && progress.queue_position > 0 ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/70 dark:border-amber-900/30 dark:bg-amber-950/20 px-3 py-2 text-xs font-medium text-amber-800 dark:text-amber-300"
            role="status"
            aria-live="polite"
          >
            <Clock className="h-3.5 w-3.5 shrink-0" strokeWidth={2} aria-hidden="true" />
            <span>
              {t('download.progress.queue_position', {
                position: progress.queue_position,
              })}
            </span>
          </div>
        ) : null}

        {chapterProgress ? (
          <div className="flex items-center gap-2 rounded-lg bg-muted/40 px-3 py-2 text-xs text-foreground">
            <FileText
              className="h-3.5 w-3.5 shrink-0 text-primary"
              strokeWidth={2}
              aria-hidden="true"
            />
            <span className="truncate">
              <span className="font-semibold text-primary">
                {t('download.progress.chapter_label')} {chapterProgress}
              </span>
              {progress?.chapter_title ? `: ${progress.chapter_title}` : ''}
            </span>
          </div>
        ) : null}

        {etaLabel ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5 text-primary/70" aria-hidden="true" />
            <span>
              {t('download.progress.time_remaining')}:{' '}
              <span className="font-semibold text-foreground">{etaLabel}</span>
            </span>
          </div>
        ) : null}

        {!chapterProgress && shouldShowSummaryMessage ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{progress?.message}</p>
        ) : null}

        {epubName ? (
          <div className="flex items-start gap-2 text-xs">
            <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
            <p className="break-all text-xs leading-tight text-foreground">
              <span className="text-muted-foreground">
                {t('download.progress.file_generated', { format: 'EPUB' })}:
              </span>{' '}
              <span className="font-semibold font-mono text-foreground">{epubName}</span>
            </p>
          </div>
        ) : null}

        {pdfName ? (
          <div className="flex items-start gap-2 text-xs">
            <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
            <p className="break-all text-xs leading-tight text-foreground">
              <span className="text-muted-foreground">
                {t('download.progress.file_generated', { format: 'PDF' })}:
              </span>{' '}
              <span className="font-semibold font-mono text-foreground">{pdfName}</span>
            </p>
          </div>
        ) : null}

        {revealTargets.length > 0 ? (
          <div className="mt-4 rounded-xl border border-border bg-card/80 p-3.5 shadow-xs">
            <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-foreground">
              <FolderOpen className="h-4 w-4 text-primary" strokeWidth={1.75} aria-hidden="true" />
              {t('download.progress.files_generated')}
            </div>
            <div className="space-y-2">
              {revealTargets.map((path, index) => {
                const pathId = `${idPrefix}-file-path-${index}`;
                return (
                  <div
                    key={path}
                    className="rounded-lg border border-border bg-background/50 p-2.5"
                  >
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
                        {getFriendlyTypeName(path, t)}
                      </span>
                      <p
                        className="break-all font-mono text-[11px] leading-relaxed text-muted-foreground"
                        id={pathId}
                      >
                        {path.split(/[/\\]/).pop() || path}
                      </p>
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleReveal(path)}
                        disabled={revealingPath === path}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-describedby={pathId}
                      >
                        {revealingPath === path ? (
                          <>
                            <Loader2
                              className="h-3.5 w-3.5 animate-spin"
                              strokeWidth={2.5}
                              aria-hidden="true"
                            />
                            {t('common.opening')}
                          </>
                        ) : (
                          <>
                            <FolderOpen
                              className="h-3.5 w-3.5 text-primary"
                              strokeWidth={1.75}
                              aria-hidden="true"
                            />
                            {t('download.progress.open_location')}
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleCopy(path)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-describedby={pathId}
                      >
                        {copiedPath === path ? (
                          <>
                            <Check
                              className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 stroke-[2.5]"
                              aria-hidden="true"
                            />
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                              {t('download.progress.path_copied')}
                            </span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                            {t('download.progress.copy_path')}
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {actionMessage ? (
          <div
            className="flex items-center gap-2 text-xs font-medium text-emerald-600 dark:text-emerald-400"
            role="status"
            aria-live="polite"
          >
            <CheckCircle className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
            {actionMessage}
          </div>
        ) : null}

        {actionError ? (
          <div
            className="flex items-start gap-2 text-xs text-destructive"
            role="alert"
            aria-live="assertive"
          >
            <AlertCircle
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
              strokeWidth={2}
              aria-hidden="true"
            />
            {actionError}
          </div>
        ) : null}

        {hasTechnicalDetails ? (
          <details className="mt-3 rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
            <summary className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <ChevronRight className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
              {t('download.progress.technical_details')}
            </summary>
            <div className="mt-2.5 space-y-2 text-xs text-foreground">
              {progress?.message ? (
                <p>
                  <span className="font-semibold">{t('common.message')}:</span> {progress.message}
                </p>
              ) : null}
              {progress?.error ? (
                <p className="text-destructive font-medium">
                  <span className="font-semibold">{t('common.error')}:</span> {progress.error}
                </p>
              ) : null}
              {progress?.code ? (
                <p className="text-destructive">
                  <span className="font-semibold">{t('common.code')}:</span> {progress.code}
                </p>
              ) : null}
              {progress?.details ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-destructive/20 bg-destructive/5 p-2.5 font-mono text-[11px] leading-relaxed text-destructive">
                  {JSON.stringify(progress.details, null, 2)}
                </pre>
              ) : null}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function outputFileNames(value: string | string[] | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const values = Array.isArray(value) ? value : [value];
  const names = values.map(item => {
    const normalized = String(item).replace(/\\/g, '/');
    const parts = normalized.split('/');
    return parts[parts.length - 1] || normalized;
  });
  return names.join(' | ');
}

function getFriendlyTypeName(filePath: string, t: TFunction): string {
  const lower = String(filePath).toLowerCase();
  if (lower.endsWith('.epub')) {
    return t('download.progress.file_types.epub');
  }
  if (lower.endsWith('.pdf')) {
    return t('download.progress.file_types.pdf');
  }
  if (lower.endsWith('.log') || lower.includes('trace')) {
    return t('download.progress.file_types.log');
  }
  return t('download.progress.file_types.file');
}
