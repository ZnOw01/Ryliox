import { useDownloadManager } from "../hooks/useDownloadManager";
import { ChapterSelector } from "./download-progress/ChapterSelector";
import { DownloadActions } from "./download-progress/DownloadActions";
import { ErrorNotice } from "./download-progress/ErrorNotice";
import { FormatSelector } from "./download-progress/FormatSelector";
import { ProgressStatus } from "./download-progress/ProgressStatus";
import { SseStatusBadge } from "./download-progress/SseStatusBadge";
import { formatName } from "./download-progress/utils";

export function DownloadProgressCard() {
  const manager = useDownloadManager();
  const canForceReconnect = manager.sseStatus === "error";
  const chapters = manager.chaptersQuery.data?.chapters ?? [];
  // Formats that can only download the full book (e.g. epub) cannot use chapter selection
  const chapterSelectable = !manager.bookOnlyFormats.has(manager.format);

  return (
    <section className="soft-rise min-w-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-panel backdrop-blur">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2 sm:items-center">
        <h2 className="text-lg font-semibold text-ink">Descarga y progreso</h2>
        <SseStatusBadge status={manager.sseStatus} />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="min-w-0 text-sm">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Libro</span>
          <p
            role="status"
            aria-live="polite"
            className="w-full min-w-0 truncate rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          >
            {manager.selectedBook ? manager.selectedBook.title : "Selecciona un libro para comenzar"}
          </p>
        </div>

        <FormatSelector
          format={manager.format}
          formats={manager.formats}
          selectedFormatDescription={manager.selectedFormatDescription}
          hasChapterSelection={manager.hasChapterSelection}
          bookOnlyFormats={manager.bookOnlyFormats}
          isLoading={manager.formatsQuery.isLoading}
          onChange={(newFormat) => {
            manager.setFormat(newFormat);
            // Switching to a book-only format makes chapter selection invalid — clear it immediately
            if (manager.bookOnlyFormats.has(newFormat)) {
              manager.clearSelectedChapters();
            }
          }}
        />
      </div>

      <ChapterSelector
        chapters={chapters}
        error={manager.chaptersQuery.error}
        hasData={Boolean(manager.chaptersQuery.data)}
        isLoading={manager.chaptersLoading}
        isFetching={manager.chaptersRefreshing}
        onSelectAll={manager.selectAllChapters}
        onClear={manager.clearSelectedChapters}
        onToggleChapter={manager.toggleChapter}
        selectedBook={manager.selectedBook}
        selectedChapterIndexes={manager.selectedChapterIndexes}
        selectedChapterSet={manager.selectedChapterSet}
        selectable={chapterSelectable}
        totalChapters={manager.totalChapters}
      />

      {manager.invalidFormatWithChapterSelection ? (
        <p className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-700">
          <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M8 2L14.5 13H1.5L8 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M8 7v3M8 11.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span>{formatName(manager.format)} no acepta seleccion de capitulos. Cambia el formato o limpia la seleccion.</span>
        </p>
      ) : null}

      <DownloadActions
        selectedBook={Boolean(manager.selectedBook)}
        skipImages={manager.skipImages}
        onSkipImagesChange={manager.setSkipImages}
        onStart={() => manager.startMutation.mutate()}
        onCancel={() => manager.cancelMutation.mutate()}
        startDisabledReason={manager.startDisabledReason}
        startPending={manager.startMutation.isPending}
        cancelPending={manager.cancelMutation.isPending}
        active={manager.active}
        invalidFormatWithChapterSelection={manager.invalidFormatWithChapterSelection}
        formatsDisabled={manager.formatsDisabled}
        canForceReconnect={canForceReconnect}
        onForceReconnect={manager.forceReconnect}
      />

      {manager.formatsQuery.error ? <ErrorNotice error={manager.formatsQuery.error} /> : null}
      {manager.progressQuery.error ? <ErrorNotice error={manager.progressQuery.error} /> : null}
      {manager.startMutation.error ? <ErrorNotice error={manager.startMutation.error} /> : null}
      {manager.cancelMutation.error ? <ErrorNotice error={manager.cancelMutation.error} /> : null}

      <ProgressStatus
        currentLabel={manager.currentLabel}
        progressPercent={manager.progressPercent}
        progress={manager.progressQuery.data}
      />
    </section>
  );
}
