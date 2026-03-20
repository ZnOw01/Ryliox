type DownloadActionsProps = {
  active: boolean;
  cancelPending: boolean;
  canForceReconnect: boolean;
  formatsDisabled: boolean;
  invalidFormatWithChapterSelection: boolean;
  onCancel: () => void;
  onForceReconnect: () => void;
  onSkipImagesChange: (value: boolean) => void;
  onStart: () => void;
  selectedBook: boolean;
  skipImages: boolean;
  startDisabledReason: string | null;
  startPending: boolean;
};

export function DownloadActions({
  active,
  cancelPending,
  canForceReconnect,
  formatsDisabled,
  invalidFormatWithChapterSelection,
  onCancel,
  onForceReconnect,
  onSkipImagesChange,
  onStart,
  selectedBook,
  skipImages,
  startDisabledReason,
  startPending,
}: DownloadActionsProps) {
  const startDisabled = !selectedBook || startPending || active || invalidFormatWithChapterSelection || formatsDisabled;

  return (
    <>
      <label className="mb-3 flex cursor-pointer items-center gap-2 text-sm text-slate-600 transition hover:text-slate-800">
        <input
          type="checkbox"
          checked={skipImages}
          onChange={(event) => onSkipImagesChange(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300 accent-brand"
        />
        Omitir imagenes
      </label>

      <div className="mb-3 grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          onClick={onStart}
          aria-describedby={startDisabledReason ? "start-disabled-reason" : undefined}
          disabled={startDisabled}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {startPending ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Iniciando...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M5 3.5l7 4.5-7 4.5V3.5z" fill="currentColor" />
              </svg>
              Iniciar descarga
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={!active || cancelPending}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-red-300 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {cancelPending ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-400/30 border-t-slate-500" />
              Cancelando...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
              </svg>
                Cancelar
            </>
          )}
        </button>

        {canForceReconnect ? (
          <button
            type="button"
            onClick={onForceReconnect}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white hover:bg-amber-100 sm:col-span-2"
          >
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
              <path d="M6.5 1.5L8 2.5L6.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Reintentar conexion en vivo
          </button>
        ) : null}
      </div>
      {startDisabledReason && startDisabledReason !== "Selecciona un libro para comenzar." ? (
        <p id="start-disabled-reason" className="mb-4 text-xs text-amber-700">
          {startDisabledReason}
        </p>
      ) : null}
    </>
  );
}
