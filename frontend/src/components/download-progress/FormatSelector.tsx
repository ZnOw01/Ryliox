import { formatName } from './utils';
import { useTranslation } from 'react-i18next';

type FormatSelectorProps = {
  bookOnlyFormats: Set<string>;
  descriptions?: Record<string, string>;
  format: string;
  formats: string[];
  hasChapterSelection: boolean;
  isLoading: boolean;
  onChange: (value: string) => void;
  selectedFormatDescription?: string;
  /** Accessible label for the format selector */
  ariaLabel?: string;
};

export function FormatSelector({
  bookOnlyFormats,
  descriptions,
  format,
  formats,
  hasChapterSelection,
  isLoading,
  onChange,
  selectedFormatDescription,
  ariaLabel,
}: FormatSelectorProps) {
  const { t } = useTranslation();
  const disabled = isLoading || formats.length === 0;
  const selectValue = disabled ? '' : format;
  const selectId = 'format-selector';
  const helperId = hasChapterSelection ? 'format-helper-text' : undefined;

  return (
    <div className="min-w-0 text-sm leading-tight">
      <label
        htmlFor={selectId}
        className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
      >
        {t('download.format.label')}
      </label>
      {isLoading ? (
        <div className="mb-2 h-10 animate-pulse rounded-lg bg-muted" aria-hidden="true" />
      ) : null}
      <select
        id={selectId}
        value={selectValue}
        onChange={event => onChange(event.target.value)}
        aria-label={ariaLabel || t('download.format.aria_label')}
        aria-describedby={helperId}
        disabled={disabled}
        className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm leading-tight text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
      >
        {isLoading ? <option value="">{t('download.format.loading')}</option> : null}
        {!isLoading && formats.length === 0 ? (
          <option value="">{t('download.format.no_formats')}</option>
        ) : null}
        {!isLoading
          ? formats.map(item => (
              <option
                key={item}
                value={item}
                disabled={hasChapterSelection && bookOnlyFormats.has(item)}
                aria-disabled={
                  hasChapterSelection && bookOnlyFormats.has(item) ? 'true' : undefined
                }
              >
                {formatName(item, t)}
                {descriptions?.[item] ? ` — ${descriptions[item]}` : ''}
              </option>
            ))
          : null}
      </select>
      {hasChapterSelection ? (
        <p id="format-helper-text" className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {t('download.format.helper_text')}
        </p>
      ) : null}
      {selectedFormatDescription ? (
        <p className="mt-2 break-words text-xs leading-relaxed text-muted-foreground">
          {selectedFormatDescription}
        </p>
      ) : null}
    </div>
  );
}
