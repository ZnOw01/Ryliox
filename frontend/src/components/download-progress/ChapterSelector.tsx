import type { ChapterSummary, SearchBook } from "../../lib/types";
import { ErrorNotice } from "./ErrorNotice";
import { chapterMeta, formatReadingMinutes } from "./utils";

type ChapterSelectorProps = {
  chapters: ChapterSummary[];
  error: unknown;
  hasData: boolean;
  isFetching: boolean;
  isLoading: boolean;
  onClear: () => void;
  onSelectAll: () => void;
  onToggleChapter: (chapterIndex: number) => void;
  selectedBook: SearchBook | null;
  selectedChapterIndexes: number[];
  selectedChapterSet: Set<number>;
  totalChapters: number;
};

export function ChapterSelector({
  chapters,
  error,
  hasData,
  isFetching,
  isLoading,
  onClear,
  onSelectAll,
  onToggleChapter,
  selectedBook,
  selectedChapterIndexes,
  selectedChapterSet,
  totalChapters,
}: ChapterSelectorProps) {
  const selectedReadingMinutes = chapters.reduce((sum, chapter) => {
    if (!selectedChapterSet.has(chapter.index) || typeof chapter.minutes !== "number") {
      return sum;
    }
    return sum + chapter.minutes;
  }, 0);
  const selectedReadingLabel = selectedReadingMinutes > 0 ? formatReadingMinutes(selectedReadingMinutes) : null;

  return (
    <div className="mb-4 rounded-xl border border-slate-200 p-3">
      <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-1.5">
        <p className="text-sm font-semibold text-slate-800">Capitulos</p>
        <p
          className="min-w-0 break-words text-left text-xs text-slate-500 sm:ml-auto sm:max-w-[62%] sm:text-right"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          Seleccionados {selectedChapterIndexes.length}/{totalChapters}
          {selectedReadingLabel ? ` | ${selectedReadingLabel}` : ""}
        </p>
      </div>

      {!selectedBook ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          Selecciona un libro desde busqueda para cargar los capitulos.
        </div>
      ) : null}
      {selectedBook && isLoading ? (
        <div className="space-y-2">
          <p className="text-sm text-slate-500">Cargando capitulos...</p>
          <div className="space-y-2 rounded border border-slate-200 p-2">
            <div className="h-4 animate-pulse rounded bg-slate-100" />
            <div className="h-4 animate-pulse rounded bg-slate-100" />
            <div className="h-4 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
      ) : null}
      {selectedBook && !isLoading && isFetching ? <p className="text-sm text-slate-500">Actualizando capitulos...</p> : null}
      {selectedBook && error ? <ErrorNotice error={error} /> : null}

      {selectedBook && hasData ? (
        <>
          <p className="mb-2 text-xs text-slate-500">Los minutos por capitulo son una lectura estimada; no representan el tiempo de descarga.</p>
          <div className="mb-2 grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={onSelectAll}
              disabled={chapters.length === 0 || isLoading}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Seleccionar todo
            </button>
            <button
              type="button"
              onClick={onClear}
              disabled={selectedChapterIndexes.length === 0 || isLoading}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Limpiar
            </button>
          </div>

          <div className="chapter-scroll max-h-56 space-y-1 overflow-x-hidden overflow-y-auto rounded border border-slate-200 p-2">
            {chapters.map((chapter) => {
              const checked = selectedChapterSet.has(chapter.index);
              const meta = chapterMeta(chapter);
              return (
                <label
                  key={chapter.index}
                  className="flex min-w-0 cursor-pointer items-start gap-2 rounded px-3 py-1.5 text-sm hover:bg-slate-50 focus-within:bg-brand/5 focus-within:ring-2 focus-within:ring-brand/40"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleChapter(chapter.index)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-brand"
                  />
                  <span className="min-w-0 overflow-hidden">
                    <span className="block truncate text-slate-800">{chapter.title}</span>
                    {meta ? <span className="text-xs text-slate-500">{meta}</span> : null}
                  </span>
                </label>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}
