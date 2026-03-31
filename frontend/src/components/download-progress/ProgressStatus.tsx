import { useState } from 'react';
import {
  CheckCircle,
  Clock,
  FileText,
  FolderOpen,
  Copy,
  WarningCircle,
  Spinner,
  CaretRight,
} from '@phosphor-icons/react';

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
  const etaLabel = formatEta(progress?.eta_seconds);
  const statusLabel = formatStatusLabel(currentLabel);
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
        className="h-3 overflow-hidden rounded-full bg-muted shadow-inner"
        role="progressbar"
        aria-label={t('download.progress.aria_label')}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressPercent}
        aria-valuetext={t('download.progress.percentage_aria', {
          percent: progressPercent,
          status: statusLabel,
        })}
        tabIndex={0}
      >
        <div
          className={cn(
            'h-full bg-gradient-to-r from-primary to-primary/80 transition-all duration-500 ease-out',
            isActive && 'progress-bar-active animate-pulse'
          )}
          style={{ width: `${progressPercent}%` }}
          aria-hidden="true"
        />
      </div>

      <div className="mt-3 space-y-2 text-sm text-foreground">
        {progress?.status === 'completed' ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm font-medium text-success-foreground"
            role="status"
            aria-live="polite"
          >
            <CheckCircle className="h-4 w-4 shrink-0" weight="regular" aria-hidden="true" />
            <span>{t('download.progress.completed_message')}</span>
          </div>
        ) : null}

        {typeof progress?.queue_position === 'number' && progress.queue_position > 0 ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-tight text-warning-foreground"
            role="status"
            aria-live="polite"
          >
            <Clock className="h-4 w-4 shrink-0" weight="regular" aria-hidden="true" />
            <span>
              {t('download.progress.queue_position', { position: progress.queue_position })}
            </span>
          </div>
        ) : null}

        {chapterProgress ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <FileText className="h-4 w-4" weight="regular" aria-hidden="true" />
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
          <div className="mt-4 rounded-lg border border-border bg-muted px-4 py-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <FolderOpen className="h-4 w-4" weight="regular" aria-hidden="true" />
              {t('download.progress.files_generated')}
            </div>
            <div className="space-y-3">
              {revealTargets.map(path => (
                <div key={path} className="rounded-lg border border-border bg-background px-3 py-3">
                  <p
                    className="break-all text-xs leading-relaxed text-muted-foreground"
                    id={`file-path-${path}`}
                  >
                    {path}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleReveal(path)}
                      disabled={revealingPath === path}
                      className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-describedby={`file-path-${path}`}
                    >
                      {revealingPath === path ? (
                        <>
                          <Spinner
                            className="h-4 w-4 animate-spin"
                            weight="bold"
                            aria-hidden="true"
                          />
                          {t('common.opening')}
                        </>
                      ) : (
                        <>
                          <FolderOpen className="h-4 w-4" weight="regular" aria-hidden="true" />
                          {t('download.progress.open_location')}
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleCopy(path)}
                      className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-describedby={`file-path-${path}`}
                    >
                      <Copy className="h-4 w-4" weight="regular" aria-hidden="true" />
                      {t('download.progress.copy_path')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {actionMessage ? (
          <div
            className="flex items-center gap-2 text-xs text-success-foreground"
            role="status"
            aria-live="polite"
          >
            <CheckCircle className="h-4 w-4" weight="regular" aria-hidden="true" />
            {actionMessage}
          </div>
        ) : null}

        {actionError ? (
          <div
            className="flex items-start gap-2 text-xs text-destructive-foreground"
            role="alert"
            aria-live="assertive"
          >
            <WarningCircle
              className="mt-0.5 h-4 w-4 shrink-0"
              weight="regular"
              aria-hidden="true"
            />
            {actionError}
          </div>
        ) : null}

        {hasTechnicalDetails ? (
          <details className="mt-3 rounded-lg border border-border bg-muted px-4 py-3">
            <summary className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <CaretRight className="h-4 w-4" weight="regular" aria-hidden="true" />
              {t('download.progress.technical_details')}
            </summary>
            <div className="mt-3 space-y-2 text-xs text-foreground">
              {progress?.message ? (
                <p>
                  <span className="font-medium">{t('common.message')}:</span> {progress.message}
                </p>
              ) : null}
              {progress?.error ? (
                <p className="text-destructive-foreground">
                  <span className="font-medium">{t('common.error')}:</span> {progress.error}
                </p>
              ) : null}
              {progress?.code ? (
                <p className="text-destructive-foreground">
                  <span className="font-medium">{t('common.code')}:</span> {progress.code}
                </p>
              ) : null}
              {progress?.details ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-border bg-background p-3 text-xs leading-relaxed text-destructive-foreground">
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
