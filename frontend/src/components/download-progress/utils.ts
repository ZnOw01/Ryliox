import type { ChapterSummary } from '../../lib/types';
import type { SseStatus } from '../../hooks/useDownloadManager';
import type { TFunction } from 'i18next';

function roundToSingleDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

function formatDecimal(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function chapterPagesLabel(pages: number, t: TFunction): string {
  return `${pages} ${pages === 1 ? t('common.page') : t('common.pages')}`;
}

export function formatReadingMinutes(
  minutes: number | null | undefined,
  t: TFunction
): string | null {
  if (typeof minutes !== 'number' || Number.isNaN(minutes) || minutes < 0) {
    return null;
  }

  const normalized = roundToSingleDecimal(minutes);
  if (normalized < 1) {
    return t('common.reading_time_less_than_minute');
  }
  return `${formatDecimal(normalized)} ${t('common.reading_time_minutes')}`;
}

export function formatEta(seconds: number | null | undefined): string | null {
  if (typeof seconds !== 'number' || Number.isNaN(seconds) || seconds < 0) {
    return null;
  }

  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${String(secs).padStart(2, '0')}s`;
  }
  return `${secs}s`;
}

export function formatStatusLabel(status: string, t?: TFunction): string {
  if (!t) return status.replace(/_/g, ' ');

  const labels: Record<string, string> = {
    idle: t('download.progress.status_idle'),
    queued: t('download.progress.status_queued'),
    running: t('download.progress.status_running'),
    completed: t('download.progress.status_completed'),
    error: t('download.progress.status_error'),
  };
  return labels[status] ?? status.replace(/_/g, ' ');
}

export function formatSseStatusLabel(status: SseStatus, t?: TFunction): string {
  if (!t) {
    const fallbackLabels: Record<SseStatus, string> = {
      connected: 'active',
      connecting: 'starting',
      error: 'paused',
      reconnecting: 'retrying',
    };
    return fallbackLabels[status];
  }

  const labels: Record<SseStatus, string> = {
    connected: t('download.sse.status_connected'),
    connecting: t('download.sse.status_connecting'),
    error: t('download.sse.status_error'),
    reconnecting: t('download.sse.status_reconnecting'),
  };
  return labels[status];
}

export function formatName(format: string, t?: TFunction): string {
  switch (format) {
    case 'epub':
      return 'EPUB';
    case 'pdf':
      return 'PDF';
    case 'pdf-chapters':
      return t ? t('download.format.pdf_separate') : 'PDF by chapters';
    default:
      return format
        .split('-')
        .map(part => part.slice(0, 1).toUpperCase() + part.slice(1))
        .join(' ');
  }
}

export function chapterMeta(chapter: ChapterSummary, t?: TFunction): string | null {
  const pieces: string[] = [];
  if (typeof chapter.pages === 'number' && t) {
    pieces.push(chapterPagesLabel(chapter.pages, t));
  }
  const reading = t ? formatReadingMinutes(chapter.minutes, t) : null;
  if (reading) {
    pieces.push(reading);
  }
  return pieces.length > 0 ? pieces.join(' | ') : null;
}

export function renderOutputPath(value: string | string[] | null | undefined) {
  if (!value) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.join(' | ');
  }
  return value;
}

export function sseStatusClass(status: SseStatus): string {
  if (status === 'connected') {
    return 'border-success/30 bg-success/10 text-success-foreground';
  }
  if (status === 'error') {
    return 'border-destructive/30 bg-destructive/10 text-destructive-foreground';
  }
  if (status === 'reconnecting') {
    return 'border-warning/30 bg-warning/10 text-warning-foreground';
  }
  return 'border-border bg-muted text-muted-foreground';
}
