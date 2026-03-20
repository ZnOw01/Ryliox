import { useState } from "react";

import { revealFile } from "../../lib/api";
import type { ProgressResponse } from "../../lib/types";
import { formatEta, formatStatusLabel } from "./utils";

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

function canUseClipboardApi(): boolean {
  return (
    typeof window !== "undefined"
    && window.isSecureContext
    && typeof navigator !== "undefined"
    && typeof navigator.clipboard?.writeText === "function"
  );
}

function getClipboardUnavailableMessage(): string {
  return "La copia no esta disponible en este navegador o contexto seguro.";
}


export function ProgressStatus({ currentLabel, progress, progressPercent }: ProgressStatusProps) {
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [revealingPath, setRevealingPath] = useState<string | null>(null);
  const etaLabel = formatEta(progress?.eta_seconds);
  const statusLabel = formatStatusLabel(currentLabel);
  const messageLabel = localizeProgressMessage(progress?.message);
  const epubName = outputFileNames(progress?.epub);
  const pdfName = outputFileNames(progress?.pdf);
  const shouldShowSummaryMessage = Boolean(messageLabel && messageLabel.toLowerCase() !== "completado");
  const hasTechnicalDetails = Boolean(
    progress?.details || progress?.code || progress?.error
  );
  const chapterProgress =
    typeof progress?.current_chapter === "number" && typeof progress?.total_chapters === "number" && progress.total_chapters > 0
      ? `${progress.current_chapter}/${progress.total_chapters}`
      : null;
  const isActive = progress?.status === "running";
  const revealTargets = [
    ...(progress?.epub ? [progress.epub] : []),
    ...(progress?.pdf ? (Array.isArray(progress.pdf) ? progress.pdf : [progress.pdf]) : []),
    ...(progress?.trace_log ? [progress.trace_log] : []),
  ].filter((value, index, array): value is string => Boolean(value) && array.indexOf(value) === index);
  const supportsCopy = canUseClipboardApi();

  async function handleReveal(path: string) {
    setActionMessage(null);
    setActionError(null);
    setRevealingPath(path);
    try {
      await revealFile(path);
      setActionMessage("Ruta abierta en el sistema.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "No se pudo abrir la ruta.");
    } finally {
      setRevealingPath(null);
    }
  }

  async function handleCopy(value: string) {
    setActionMessage(null);
    setActionError(null);
    try {
      await navigator.clipboard.writeText(value);
      setActionMessage("Ruta copiada al portapapeles.");
    } catch (error) {
      setActionError(error instanceof Error && error.name === "NotAllowedError"
        ? "El navegador bloqueo la copia al portapapeles."
        : "No se pudo copiar la ruta.");
    }
  }

  return (
    <>
      <div className="mb-2 flex min-w-0 items-center justify-between gap-2 text-xs text-slate-600" role="status" aria-live="polite" aria-atomic="true">
        <span className="min-w-0 break-words">Estado: {statusLabel}</span>
        <span className="shrink-0 tabular-nums">{progressPercent}%</span>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-label="Progreso de descarga"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressPercent}
        aria-valuetext={`${progressPercent}% - ${statusLabel}`}
      >
        <div
          className={`h-full transition-all duration-300 ${
            progress?.status === "completed" ? "bg-emerald-500" : "bg-brand"
          } ${isActive ? "progress-bar-active" : ""}`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="mt-3 space-y-1 text-sm text-slate-600">
        {progress?.status === "completed" ? (
          <p className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Descarga completada correctamente.
          </p>
        ) : null}
        {progress?.status === "cancelled" || progress?.status === "canceled" ? (
          <p className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
              <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            Descarga cancelada.
          </p>
        ) : null}
        {typeof progress?.queue_position === "number" && progress.queue_position > 0 ? (
          <p className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.75" />
              <path d="M8 5v4l2 2" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Posicion en cola: {progress.queue_position}
          </p>
        ) : null}
        {chapterProgress ? (
          <p className="text-xs text-slate-500">
            Capitulo {chapterProgress}{progress?.chapter_title ? `: ${progress.chapter_title}` : ""}
          </p>
        ) : null}
        {etaLabel ? (
          <p className="text-xs text-slate-500">Tiempo restante: <span className="font-medium text-slate-700">{etaLabel}</span></p>
        ) : null}
        {!chapterProgress && shouldShowSummaryMessage ? <p className="text-xs text-slate-500">{messageLabel}</p> : null}
        {epubName ? <p className="break-all">EPUB generado: <span className="font-medium text-slate-700">{epubName}</span></p> : null}
        {pdfName ? <p className="break-all">PDF generado: <span className="font-medium text-slate-700">{pdfName}</span></p> : null}
        {revealTargets.length > 0 ? (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Archivos generados</p>
            <div className="space-y-2">
              {revealTargets.map((path) => (
                <div key={path} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <p className="break-all text-xs text-slate-500">{path}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleReveal(path)}
                      disabled={revealingPath === path}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {revealingPath === path ? "Abriendo..." : "Abrir ubicacion"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleCopy(path)}
                      disabled={!supportsCopy}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {supportsCopy ? "Copiar ruta" : "Copia no disponible"}
                    </button>
                  </div>
                  {!supportsCopy ? (
                    <p className="mt-2 text-[11px] text-slate-500">{getClipboardUnavailableMessage()}</p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {actionMessage ? <p className="text-xs text-emerald-700">{actionMessage}</p> : null}
        {actionError ? <p className="text-xs text-red-600">{actionError}</p> : null}

        {hasTechnicalDetails ? (
          <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-slate-600">Detalles tecnicos</summary>
            <div className="mt-2 space-y-1 text-xs text-slate-600">
              {messageLabel ? <p>Mensaje: {messageLabel}</p> : null}
              {progress?.error ? <p className="text-red-600">Error: {progress.error}</p> : null}
              {progress?.code ? <p className="text-red-600">Codigo: {progress.code}</p> : null}
              {progress?.details ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-red-100 bg-red-50 p-2 text-xs text-red-700">
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
