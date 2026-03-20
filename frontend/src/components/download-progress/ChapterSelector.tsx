import type { ChapterSummary, SearchBook } from "../../lib/types";
import { ErrorNotice } from "./ErrorNotice";
import { chapterMeta } from "./utils";

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
  /** When false the current format downloads the whole book — checkboxes and action buttons are hidden. */
  selectable: boolean;
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
  selectable,
  totalChapters,
}: ChapterSelectorProps) {
  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-slate-50/50">
      {/* ── Header ── */}
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-1.5 border-b border-slate-200 bg-white px-3 py-2">
        <p className="text-sm font-semibold text-slate-800">Capitulos</p>
        {selectable ? (
          <p className="text-xs text-slate-500" role="status" aria-live="polite" aria-atomic="true">
            {selectedChapterIndexes.length}/{totalChapters} seleccionados
          </p>
        ) : (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
            {totalChapters} en total
          </span>
        )}
      </div>

      {/* ── Book-only notice ── */}
      {!selectable && (
        <div className="flex items-start gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2.5">
          <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 5v4M8 11v.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
          <p className="text-xs leading-relaxed text-slate-500">
            Este formato descarga el libro completo. Los capitulos se muestran solo como referencia.
          </p>
        </div>
      )}

      {/* ── Empty state ── */}
      {!selectedBook ? (
        <div className="px-3 py-4 text-center">
          <p className="text-sm text-slate-500">Selecciona un libro para ver los capitulos.</p>
        </div>
      ) : null}

      {/* ── Loading skeleton ── */}
      {selectedBook && isLoading ? (
        <div className="space-y-2 p-3">
          <p className="text-xs text-slate-400">Cargando capitulos...</p>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-7 animate-pulse rounded-lg bg-slate-200" />
            ))}
          </div>
        </div>
      ) : null}
      {selectedBook && !isLoading && isFetching ? (
        <p className="px-3 py-2 text-xs text-slate-400">Actualizando capitulos...</p>
      ) : null}
      {selectedBook && error ? <div className="p-3"><ErrorNotice error={error} /></div> : null}

      {/* ── Chapter list ── */}
      {selectedBook && hasData ? (
        <>
          {/* Action buttons — only when selectable */}
          {selectable && (
            <div className="grid gap-1.5 p-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={onSelectAll}
                disabled={chapters.length === 0 || isLoading}
                className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand-deep disabled:cursor-not-allowed disabled:opacity-60"
              >
                Seleccionar todo
              </button>
              <button
                type="button"
                onClick={onClear}
                disabled={selectedChapterIndexes.length === 0 || isLoading}
                className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand-deep disabled:cursor-not-allowed disabled:opacity-60"
              >
                Limpiar
              </button>
            </div>
          )}

          <div className="chapter-scroll max-h-56 space-y-0.5 overflow-x-hidden overflow-y-auto p-2">
            {chapters.map((chapter) => {
              const checked = selectable && selectedChapterSet.has(chapter.index);

              if (!selectable) {
                const meta = chapterMeta(chapter);
                // Read-only row — no checkbox, no interaction
                return (
                  <div
                    key={chapter.index}
                    className="flex min-w-0 items-center gap-2 rounded-lg px-2.5 py-1.5"
                  >
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" aria-hidden="true" />
                    <span className="block min-w-0 truncate text-sm text-slate-600">
                      {chapter.title}
                    </span>
                    {meta ? <span className="text-xs text-slate-400">{meta}</span> : null}
                  </div>
                );
              }

              const meta = chapterMeta(chapter);

              return (
                <label
                  key={chapter.index}
                  className={`flex min-w-0 cursor-pointer items-start gap-2 rounded-lg px-2.5 py-1.5 text-sm transition hover:bg-white focus-within:ring-2 focus-within:ring-brand/40 ${checked ? "bg-brand/5" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleChapter(chapter.index)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-brand"
                  />
                  <span className="min-w-0 overflow-hidden">
                    <span className={`block truncate ${checked ? "font-medium text-brand-deep" : "text-slate-800"}`}>
                      {chapter.title}
                    </span>
                    {meta ? <span className="block text-xs text-slate-500">{meta}</span> : null}
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
