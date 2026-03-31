import type { SseStatus } from '../../hooks/useDownloadManager';
import { formatSseStatusLabel, sseStatusClass } from './utils';
import { useTranslation } from 'react-i18next';

type SseStatusBadgeProps = {
  status: SseStatus;
  /** Accessible label for the status indicator */
  ariaLabel?: string;
};

export function SseStatusBadge({ status, ariaLabel }: SseStatusBadgeProps) {
  const { t } = useTranslation();
  const statusLabel = formatSseStatusLabel(status, t);
  const isConnected = status === 'connected';

  return (
    <span
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={`${ariaLabel || t('download.sse.aria_label')}: ${statusLabel}`}
      className={`inline-flex max-w-full flex-wrap items-center gap-1.5 break-words rounded-full border px-2 py-0.5 text-xs font-semibold ${sseStatusClass(status)}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full bg-current ${isConnected ? 'sse-pulse' : ''}`}
        aria-hidden="true"
      />
      <span className="sr-only">{ariaLabel || t('download.sse.aria_label')}:</span>
      <span>
        {t('download.sse.live_updates')}: {statusLabel}
      </span>
    </span>
  );
}
