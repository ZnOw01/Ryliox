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
  const formatDescriptions = manager.formatsQuery.data?.descriptions;
  const chapters = manager.chaptersQuery.data?.chapters ?? [];

  return (
    <section className="soft-rise min-w-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white/90 p-5 shadow-panel backdrop-blur">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2 sm:items-center">
        <h2 className="text-lg font-semibold text-ink">Descarga y progreso</h2>
        <SseStatusBadge status={manager.sseStatus} />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <label className="min-w-0 text-sm">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Libro</span>
          <input
            readOnly
            aria-label="Libro seleccionado"
            value={manager.selectedBook ? manager.selectedBook.title : "Selecciona un libro para comenzar"}
            className="w-full min-w-0 truncate rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          />
        </label>

        <FormatSelector
          format={manager.format}
          formats={manager.formats}
          descriptions={formatDescriptions}
          selectedFormatDescription={manager.selectedFormatDescription}
          hasChapterSelection={manager.hasChapterSelection}
          bookOnlyFormats={manager.bookOnlyFormats}
          isLoading={manager.formatsQuery.isLoading}
          onChange={manager.setFormat}
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
        totalChapters={manager.totalChapters}
      />

      {manager.invalidFormatWithChapterSelection ? (
        <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-2 text-sm text-amber-700">
          La seleccion de capitulos no es compatible con {formatName(manager.format)}. Cambia el formato o limpia la seleccion.
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
