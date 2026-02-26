import type { ChapterSummary } from "../../lib/types";
import type { SseStatus } from "../../hooks/useDownloadManager";

function roundToSingleDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

function formatDecimal(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function chapterPagesLabel(pages: number): string {
  return `${pages} ${pages === 1 ? "pagina" : "paginas"}`;
}

export function formatReadingMinutes(minutes: number | null | undefined): string | null {
  if (typeof minutes !== "number" || Number.isNaN(minutes) || minutes < 0) {
    return null;
  }

  const normalized = roundToSingleDecimal(minutes);
  if (normalized < 1) {
    return "<1 min lectura";
  }
  return `${formatDecimal(normalized)} min lectura`;
}

export function formatEta(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || Number.isNaN(seconds) || seconds < 0) {
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
    return `${minutes}m ${String(secs).padStart(2, "0")}s`;
  }
  return `${secs}s`;
}

export function formatStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    idle: "en espera",
    starting: "iniciando descarga",
    fetching_metadata: "cargando metadata",
    fetching_chapters: "cargando capitulos",
    downloading_cover: "descargando portada",
    processing_chapters: "procesando capitulos",
    downloading_assets: "descargando recursos",
    generating_epub: "generando EPUB",
    generating_pdf: "generando PDF",
    generating_pdf_chapters: "generando PDFs por capitulo",
    completed: "completado",
    cancelled: "cancelado",
    failed: "fallido",
  };
  return labels[status] ?? status.replace(/_/g, " ");
}

export function formatSseStatusLabel(status: SseStatus): string {
  const labels: Record<SseStatus, string> = {
    connected: "activas",
    connecting: "iniciando",
    error: "pausadas",
    reconnecting: "reintentando",
  };
  return labels[status];
}

export function formatName(format: string): string {
  switch (format) {
    case "epub":
      return "EPUB";
    case "pdf":
      return "PDF";
    case "pdf-chapters":
      return "PDF por capitulo";
    default:
      return format
        .split("-")
        .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
        .join(" ");
  }
}

export function chapterMeta(chapter: ChapterSummary): string | null {
  const pieces: string[] = [];
  if (typeof chapter.pages === "number") {
    pieces.push(chapterPagesLabel(chapter.pages));
  }
  const reading = formatReadingMinutes(chapter.minutes);
  if (reading) {
    pieces.push(reading);
  }
  return pieces.length > 0 ? pieces.join(" | ") : null;
}

export function renderOutputPath(value: string | string[] | null | undefined) {
  if (!value) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.join(" | ");
  }
  return value;
}

export function sseStatusClass(status: SseStatus): string {
  if (status === "connected") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status === "error") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "reconnecting") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}
