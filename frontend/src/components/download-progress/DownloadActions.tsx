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
      <label className="mb-3 flex items-center gap-2 text-sm text-slate-700">
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
          className="w-full rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:cursor-not-allowed disabled:opacity-60"
        >
          {startPending ? "Iniciando..." : "Iniciar descarga"}
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={!active || cancelPending}
          className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Cancelar
        </button>

        {canForceReconnect ? (
          <button
            type="button"
            onClick={onForceReconnect}
            className="w-full rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white hover:bg-amber-100 sm:col-span-2"
          >
            Reintentar conexion en vivo
          </button>
        ) : null}
      </div>
      {startDisabledReason ? (
        <p id="start-disabled-reason" className="mb-4 text-xs text-amber-700">
          {startDisabledReason}
        </p>
      ) : null}
    </>
  );
}
