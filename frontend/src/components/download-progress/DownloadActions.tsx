import { cn } from '../../lib/cn';
import { Play, X, ImageOff, Loader2, Info } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type DownloadActionsProps = {
  active: boolean;
  cancelPending: boolean;
  formatsDisabled: boolean;
  invalidFormatWithChapterSelection: boolean;
  onCancel: () => void;
  onSkipImagesChange: (value: boolean) => void;
  onStart: () => void;
  selectedBook: boolean;
  skipImages: boolean;
  startDisabledReason: string | null;
  startPending: boolean;
  ariaLabel?: string;
};

export function DownloadActions({
  active,
  cancelPending,
  formatsDisabled,
  invalidFormatWithChapterSelection,
  onCancel,
  onSkipImagesChange,
  onStart,
  selectedBook,
  skipImages,
  startDisabledReason,
  startPending,
  ariaLabel,
}: DownloadActionsProps) {
  const { t } = useTranslation();
  const startDisabled =
    !selectedBook || startPending || active || invalidFormatWithChapterSelection || formatsDisabled;

  return (
    <>
      <label className="mb-3 flex cursor-pointer items-center gap-3 text-sm text-muted-foreground transition hover:text-foreground min-h-touch group">
        <div
          className={cn(
            'flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
            skipImages
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-input bg-background text-transparent group-hover:border-muted-foreground'
          )}
        >
          {skipImages ? (
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path
                d="M2.5 6L5 8.5L9.5 3.5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : (
            <span className="h-3 w-3" />
          )}
        </div>
        <input
          type="checkbox"
          checked={skipImages}
          onChange={event => onSkipImagesChange(event.target.checked)}
          className="sr-only"
          aria-describedby="skip-images-desc"
        />
        <span id="skip-images-desc" className="inline-flex items-center gap-1.5">
          <ImageOff className="h-4 w-4 opacity-60" strokeWidth={1.75} aria-hidden="true" />
          {t('download.actions.skip_images')}
        </span>
      </label>

      <div
        className="mb-3 grid gap-3 sm:grid-cols-2"
        role="group"
        aria-label={ariaLabel || t('download.actions.aria_label')}
      >
        <button
          type="button"
          onClick={onStart}
          aria-describedby={startDisabledReason ? 'start-disabled-reason' : undefined}
          disabled={startDisabled}
          className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:border disabled:border-gray-200 disabled:bg-gray-200 disabled:text-gray-400 disabled:shadow-none disabled:cursor-not-allowed disabled:opacity-100 sm:py-2"
        >
          {startPending ? (
            <>
              <Loader2
                className="h-4 w-4 animate-spin sm:h-3.5 sm:w-3.5"
                strokeWidth={2.5}
                aria-hidden="true"
              />
              <span>{t('download.actions.starting')}</span>
            </>
          ) : (
            <>
              <Play
                className="h-5 w-5 fill-current sm:h-4 sm:w-4"
                strokeWidth={1.75}
                aria-hidden="true"
              />
              <span>{t('download.actions.start')}</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={!active || cancelPending}
          className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg border border-gray-200 bg-background px-4 py-3 text-sm font-semibold text-gray-900 transition hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:bg-gray-200 disabled:text-gray-400 disabled:shadow-none disabled:hover:border-gray-200 disabled:hover:bg-gray-200 disabled:hover:text-gray-400 disabled:cursor-not-allowed disabled:opacity-100 sm:py-2"
        >
          {cancelPending ? (
            <>
              <Loader2
                className="h-4 w-4 animate-spin sm:h-3.5 sm:w-3.5"
                strokeWidth={2.5}
                aria-hidden="true"
              />
              <span>{t('download.actions.cancelling')}</span>
            </>
          ) : (
            <>
              <X className="h-5 w-5 sm:h-4 sm:w-4" strokeWidth={1.75} aria-hidden="true" />
              <span>{t('download.actions.cancel')}</span>
            </>
          )}
        </button>
      </div>

      {startDisabledReason ? (
        <div id="start-disabled-reason" className="mb-4 flex items-start gap-1.5" role="status">
          <Info
            className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <p className="text-xs text-muted-foreground">{startDisabledReason}</p>
        </div>
      ) : null}
    </>
  );
}
