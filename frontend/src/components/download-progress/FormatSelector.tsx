import { formatName } from "./utils";

type FormatSelectorProps = {
  bookOnlyFormats: Set<string>;
  format: string;
  formats: string[];
  hasChapterSelection: boolean;
  isLoading: boolean;
  onChange: (value: string) => void;
  selectedFormatDescription?: string;
};

export function FormatSelector({
  bookOnlyFormats,
  format,
  formats,
  hasChapterSelection,
  isLoading,
  onChange,
  selectedFormatDescription,
}: FormatSelectorProps) {
  const disabled = isLoading || formats.length === 0;
  const selectValue = disabled ? "" : format;

  return (
    <label className="min-w-0 text-sm">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Formato</span>
      {isLoading ? <div className="mb-2 h-10 animate-pulse rounded-lg bg-slate-100" /> : null}
      <select
        value={selectValue}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={hasChapterSelection ? "format-helper-text" : undefined}
        disabled={disabled}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
      >
        {isLoading ? <option value="">Cargando formatos...</option> : null}
        {!isLoading && formats.length === 0 ? <option value="">No hay formatos disponibles</option> : null}
        {!isLoading
          ? formats.map((item) => (
            <option
              key={item}
              value={item}
              disabled={hasChapterSelection && bookOnlyFormats.has(item)}
            >
              {formatName(item)}
            </option>
          ))
          : null}
      </select>
      {hasChapterSelection ? (
        <p id="format-helper-text" className="mt-1 text-xs text-slate-500">
          EPUB siempre descarga el libro completo. PDF puede usar todos o solo los capitulos elegidos.
        </p>
      ) : null}
      {selectedFormatDescription ? <p className="mt-1 break-words text-xs text-slate-500">{selectedFormatDescription}</p> : null}
    </label>
  );
}
