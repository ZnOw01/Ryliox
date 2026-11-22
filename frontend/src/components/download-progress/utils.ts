import type { SseStatus } from '../../hooks/useDownloadManager';
import type { TFunction } from 'i18next';
import type { ProgressResponse } from '../../lib/types';

function roundToSingleDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

function formatDecimal(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
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

export function formatTotalReadingTime(minutes: number | null | undefined): string | null {
  if (typeof minutes !== 'number' || Number.isNaN(minutes) || minutes <= 0) {
    return null;
  }
  if (minutes < 60) {
    return `${Math.round(minutes)} min`;
  }
  const hours = (minutes / 60).toFixed(1);
  return `${hours} hrs`;
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
    cancelled: t('download.progress.status_cancelled'),
    canceled: t('download.progress.status_cancelled'),
  };
  return labels[status] ?? status.replace(/_/g, ' ');
}

export function formatSseStatusLabel(status: SseStatus, t?: TFunction): string {
  if (!t) {
    const fallbackLabels: Record<SseStatus, string> = {
      disconnected: 'paused',
      connected: 'active',
      connecting: 'starting',
      error: 'paused',
      reconnecting: 'retrying',
    };
    return fallbackLabels[status];
  }

  const labels: Record<SseStatus, string> = {
    disconnected: t('download.sse.status_disconnected'),
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

/** The UI's own description of a format, else the server's, else none. */
export function formatDescription(
  format: string,
  t: TFunction,
  serverDescription?: string
): string | undefined {
  return (
    t(`download.format.descriptions.${format}`, { defaultValue: serverDescription ?? '' }) ||
    undefined
  );
}

const DOWNLOAD_ERROR_KEYS: Record<string, string> = {
  auth_required: 'errors.cookies_required_description',
  session_rejected: 'errors.session_rejected',
  upstream_blocked: 'errors.upstream_blocked',
};

/**
 * What a failed job means to the user, in the UI language. The server's own
 * text stays under the technical details; it is English and not for users.
 */
export function downloadErrorMessage(progress: ProgressResponse | undefined, t: TFunction): string {
  const key = progress?.code ? DOWNLOAD_ERROR_KEYS[progress.code] : undefined;
  return t(key ?? 'download.errors.generic');
}

export function sseStatusClass(status: SseStatus): string {
  if (status === 'connected') {
    return 'border-green-200 bg-green-50 text-green-800';
  }
  if (status === 'error') {
    return 'border-gray-200 bg-gray-50 text-gray-600';
  }
  if (status === 'reconnecting') {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  return 'border-gray-200 bg-gray-50 text-gray-600';
}
