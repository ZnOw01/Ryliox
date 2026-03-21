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
      className={`inline-flex max-w-full flex-wrap items-center gap-1.5 break-words rounded-full border px-2.5 py-1 text-xs font-medium shadow-sm ${sseStatusClass(status)}`}
      title={status === "error" ? "Las actualizaciones en vivo están desconectadas" : undefined}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full bg-current ${
          status === "connected" ? "sse-pulse" : status === "error" ? "" : ""
        }`}
        aria-hidden="true"
      />
      Actualizaciones en vivo: {formatSseStatusLabel(status)}
    </span>
  );
}
