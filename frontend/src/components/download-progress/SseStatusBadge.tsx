import type { SseStatus } from "../../hooks/useDownloadManager";
import { formatSseStatusLabel, sseStatusClass } from "./utils";

type SseStatusBadgeProps = {
  status: SseStatus;
};

export function SseStatusBadge({ status }: SseStatusBadgeProps) {
  return (
    <span
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`inline-flex max-w-full flex-wrap items-center gap-1 break-words rounded-full border px-2 py-0.5 text-xs font-medium ${sseStatusClass(status)}`}
    >
      Actualizaciones en vivo: {formatSseStatusLabel(status)}
    </span>
  );
}
