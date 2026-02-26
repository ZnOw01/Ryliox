import type { ProgressResponse } from "../../lib/types";
import { formatEta, formatStatusLabel, renderOutputPath } from "./utils";

type ProgressStatusProps = {
  currentLabel: string;
  progress: ProgressResponse | undefined;
  progressPercent: number;
};

function localizeProgressMessage(message: string | null | undefined): string | null {
  if (!message) {
    return null;
  }
  const normalized = message.trim().toLowerCase();
  if (normalized === "completed") {
    return "Completado";
  }
  if (normalized === "cancelled" || normalized === "canceled") {
    return "Cancelado";
  }
  if (normalized === "queued") {
    return "En cola";
  }
  return message;
}

function outputFileNames(value: string | string[] | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const values = Array.isArray(value) ? value : [value];
  const names = values.map((item) => {
    const normalized = String(item).replace(/\\/g, "/");
    const parts = normalized.split("/");
    return parts[parts.length - 1] || normalized;
  });
  return names.join(" | ");
}

export function ProgressStatus({ currentLabel, progress, progressPercent }: ProgressStatusProps) {
  const etaLabel = formatEta(progress?.eta_seconds);
  const statusLabel = formatStatusLabel(currentLabel);
  const messageLabel = localizeProgressMessage(progress?.message);
  const epubName = outputFileNames(progress?.epub);
  const pdfName = outputFileNames(progress?.pdf);
  const epubPath = renderOutputPath(progress?.epub);
  const pdfPath = renderOutputPath(progress?.pdf);
  const shouldShowSummaryMessage = Boolean(messageLabel && messageLabel.toLowerCase() !== "completado");
  const hasTechnicalDetails = Boolean(
    progress?.details || progress?.code || progress?.error || epubPath || pdfPath || messageLabel
  );
  const chapterProgress =
    typeof progress?.current_chapter === "number" && typeof progress?.total_chapters === "number" && progress.total_chapters > 0
      ? `${progress.current_chapter}/${progress.total_chapters}`
      : null;

  return (
    <>
      <div className="mb-2 flex min-w-0 items-center justify-between gap-2 text-xs text-slate-600" role="status" aria-live="polite" aria-atomic="true">
        <span className="min-w-0 break-words">Estado: {statusLabel}</span>
        <span className="shrink-0">{progressPercent}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-label="Progreso de descarga"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressPercent}
        aria-valuetext={`${progressPercent}% - ${statusLabel}`}
      >
        <div className="h-full bg-brand transition-all" style={{ width: `${progressPercent}%` }} />
      </div>

      <div className="mt-3 space-y-1 text-sm text-slate-600">
        {progress?.status === "completed" ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Descarga completada correctamente.
          </p>
        ) : null}
        {typeof progress?.queue_position === "number" ? <p>Cola: {progress.queue_position}</p> : null}
        {chapterProgress ? <p>Capitulos procesados: {chapterProgress}</p> : null}
        {etaLabel ? <p>Tiempo estimado de descarga: {etaLabel}</p> : null}
        {!etaLabel && progress?.status === "processing_chapters" ? <p>Calculando tiempo restante...</p> : null}
        {shouldShowSummaryMessage ? <p>Mensaje: {messageLabel}</p> : null}
        {progress?.chapter_title ? <p className="break-all">Capitulo: {progress.chapter_title}</p> : null}
        {epubName ? <p className="break-all">EPUB generado: <span className="font-medium text-slate-700">{epubName}</span></p> : null}
        {pdfName ? <p className="break-all">PDF generado: <span className="font-medium text-slate-700">{pdfName}</span></p> : null}

        {hasTechnicalDetails ? (
          <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-slate-600">Detalles para soporte</summary>
            <div className="mt-2 space-y-1 text-xs text-slate-600">
              {messageLabel ? <p>Mensaje original: {messageLabel}</p> : null}
              {progress?.error ? <p className="text-red-600">Error: {progress.error}</p> : null}
              {progress?.code ? <p className="text-red-600">Codigo: {progress.code}</p> : null}
              {progress?.details ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-red-100 bg-red-50 p-2 text-xs text-red-700">
                  {JSON.stringify(progress.details, null, 2)}
                </pre>
              ) : null}
              {epubPath ? <p className="break-all font-mono text-[11px] text-slate-500">Archivo EPUB (ruta local): {epubPath}</p> : null}
              {pdfPath ? <p className="break-all font-mono text-[11px] text-slate-500">Archivo PDF (ruta local): {pdfPath}</p> : null}
            </div>
          </details>
        ) : null}
      </div>
    </>
  );
}
