import { useId, useState } from 'react';
import type { TFunction } from 'i18next';
import {
  CheckCircle,
  Clock,
  FileText,
  FolderOpen,
  Copy,
  AlertCircle as WarningCircle,
  Loader2 as Spinner,
  ChevronRight as CaretRight,
} from 'lucide-react';

import { revealFile } from '../../lib/api';
import type { ProgressResponse } from '../../lib/types';
import { formatEta, formatStatusLabel } from './utils';
import { Badge } from '../ui/Badge';
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
  const progressToneClass =
    progress?.status === 'completed'
      ? 'bg-green-600'
      : progress?.status === 'error'
        ? 'bg-red-600'
        : progress?.status === 'running'
          ? 'bg-primary'
          : 'bg-gray-300';
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
      setActionMessage(t('download.progress.path_copied'));
    } catch {
      setActionError(t('download.progress.copy_failed'));
    }
  }

  return (
    <>
      <div
        className="mb-2 flex min-w-0 items-center justify-between gap-2 text-sm text-foreground"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span className="min-w-0 break-words font-medium">
          {t('download.progress.status_label')}: {statusLabel}
        </span>
        <Badge variant={progressPercent === 100 ? 'success' : 'default'} size="sm">
          {t('download.progress.percentage', { percent: progressPercent })}
        </Badge>
      </div>

      <div
        className="h-3 overflow-hidden rounded-full bg-gray-200 dark:bg-neutral-800"
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
            'h-full transition-all duration-500 ease-out',
            progressToneClass,
            isActive && 'progress-bar-active animate-pulse'
          )}
          style={{ width: `${progressPercent}%` }}
          aria-hidden="true"
        />
      </div>

      <div className="mt-3 space-y-2 text-sm text-foreground">
        {progress?.status === 'completed' ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-800"
            role="status"
            aria-live="polite"
          >
            <CheckCircle className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            <span>{t('download.progress.completed_message')}</span>
          </div>
        ) : null}

        {typeof progress?.queue_position === 'number' && progress.queue_position > 0 ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-tight text-amber-800"
            role="status"
            aria-live="polite"
          >
            <Clock className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            <span>
              {t('download.progress.queue_position', {
                position: progress.queue_position,
              })}
            </span>
          </div>
        ) : null}

        {chapterProgress ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <FileText className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            <span>
              {t('download.progress.chapter_label')} {chapterProgress}
              {progress?.chapter_title ? `: ${progress.chapter_title}` : ''}
            </span>
          </div>
        ) : null}

        {etaLabel ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-4 w-4" aria-hidden="true" />
            <span>
              {t('download.progress.time_remaining')}:{' '}
              <span className="font-medium text-foreground">{etaLabel}</span>
            </span>
          </div>
        ) : null}

        {!chapterProgress && shouldShowSummaryMessage ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{progress?.message}</p>
        ) : null}

        {epubName ? (
          <div className="flex items-start gap-2">
            <FileText
              className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <p className="break-all text-sm leading-tight text-foreground">
              {t('download.progress.file_generated', { format: 'EPUB' })}:{' '}
              <span className="font-medium text-foreground">{epubName}</span>
            </p>
          </div>
        ) : null}

        {pdfName ? (
          <div className="flex items-start gap-2">
            <FileText
              className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <p className="break-all text-sm leading-tight text-foreground">
              {t('download.progress.file_generated', { format: 'PDF' })}:{' '}
              <span className="font-medium text-foreground">{pdfName}</span>
            </p>
          </div>
        ) : null}

        {revealTargets.length > 0 ? (
          <div className="mt-4 rounded-lg border border-gray-200 bg-transparent px-4 py-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <FolderOpen className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
              {t('download.progress.files_generated')}
            </div>
            <div className="space-y-3">
              {revealTargets.map((path, index) => {
                const pathId = `${idPrefix}-file-path-${index}`;
                return (
                  <div
                    key={path}
                    className="rounded-lg border border-gray-200 bg-transparent px-3 py-3"
                  >
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
                        {getFriendlyTypeName(path, t)}
                      </span>
                      <p
                        className="break-all text-xs leading-relaxed text-muted-foreground"
                        id={pathId}
                      >
                        {path.split(/[/\\]/).pop() || path}
                      </p>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleReveal(path)}
                        disabled={revealingPath === path}
                        className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-describedby={pathId}
                      >
                        {revealingPath === path ? (
                          <>
                            <Spinner
                              className="h-4 w-4 animate-spin"
                              strokeWidth={2.5}
                              aria-hidden="true"
                            />
                            {t('common.opening')}
                          </>
                        ) : (
                          <>
                            <FolderOpen className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
                            {t('download.progress.open_location')}
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleCopy(path)}
                        className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-describedby={pathId}
                      >
                        <Copy className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
                        {t('download.progress.copy_path')}
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
            className="flex items-center gap-2 text-xs text-green-700"
            role="status"
            aria-live="polite"
          >
            <CheckCircle className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            {actionMessage}
          </div>
        ) : null}

        {actionError ? (
          <div
            className="flex items-start gap-2 text-xs text-red-700"
            role="alert"
            aria-live="assertive"
          >
            <WarningCircle
              className="mt-0.5 h-4 w-4 shrink-0"
              strokeWidth={1.75}
              aria-hidden="true"
            />
            {actionError}
          </div>
        ) : null}

        {hasTechnicalDetails ? (
          <details className="mt-3 rounded-lg border border-border bg-muted px-4 py-3">
            <summary className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <CaretRight className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
              {t('download.progress.technical_details')}
            </summary>
            <div className="mt-3 space-y-2 text-xs text-foreground">
              {progress?.message ? (
                <p>
                  <span className="font-medium">{t('common.message')}:</span> {progress.message}
                </p>
              ) : null}
              {progress?.error ? (
                <p className="text-red-700">
                  <span className="font-medium">{t('common.error')}:</span> {progress.error}
                </p>
              ) : null}
              {progress?.code ? (
                <p className="text-red-700">
                  <span className="font-medium">{t('common.code')}:</span> {progress.code}
                </p>
              ) : null}
              {progress?.details ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-red-200 bg-red-50 p-3 text-xs leading-relaxed text-red-800">
                  {JSON.stringify(progress.details, null, 2)}
                </pre>
              ) : null}
            </div>
          </details>
        ) : null}
      </div>
    </>
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
