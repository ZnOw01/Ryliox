import { cn } from '../../lib/cn';
import { Play, X, ImageOff, Loader2, Info, Check } from 'lucide-react';
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
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-2.5 text-xs text-muted-foreground transition hover:text-foreground select-none group">
          <div
            className={cn(
              'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
              skipImages
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-input bg-background text-transparent group-hover:border-muted-foreground'
            )}
          >
            {skipImages ? <Check className="h-2.5 w-2.5 stroke-[3]" aria-hidden="true" /> : null}
          </div>
          <input
            type="checkbox"
            checked={skipImages}
            onChange={event => onSkipImagesChange(event.target.checked)}
            className="sr-only"
            aria-describedby="skip-images-desc"
          />
          <span id="skip-images-desc" className="inline-flex items-center gap-1.5 font-medium">
            <ImageOff className="h-3.5 w-3.5 opacity-70" strokeWidth={1.75} aria-hidden="true" />
            {t('download.actions.skip_images')}
          </span>
        </label>
      </div>

      <div
        className="grid gap-3 sm:grid-cols-2"
        role="group"
        aria-label={ariaLabel || t('download.actions.aria_label')}
      >
        <button
          type="button"
          onClick={onStart}
          aria-describedby={startDisabledReason ? 'start-disabled-reason' : undefined}
          disabled={startDisabled}
          className={cn(
            'mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:py-2.5',
            startDisabled
              ? 'cursor-not-allowed bg-muted text-muted-foreground opacity-60'
              : 'bg-primary text-primary-foreground shadow-md hover:bg-primary/90 hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0'
          )}
        >
          {startPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2.5} aria-hidden="true" />
              <span>{t('download.actions.starting')}</span>
            </>
          ) : (
            <>
              <Play className="h-4 w-4 fill-current" strokeWidth={2} aria-hidden="true" />
              <span>{t('download.actions.start')}</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={!active || cancelPending}
          className={cn(
            'mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:py-2.5',
            !active || cancelPending
              ? 'cursor-not-allowed border-border bg-muted/40 text-muted-foreground opacity-50'
              : 'border-destructive/30 bg-background text-destructive hover:bg-destructive/10 hover:border-destructive/50'
          )}
        >
          {cancelPending ? (
            <>
              <Loader2
                className="h-4 w-4 animate-spin text-destructive"
                strokeWidth={2.5}
                aria-hidden="true"
              />
              <span>{t('download.actions.cancelling')}</span>
            </>
          ) : (
            <>
              <X className="h-4 w-4 text-destructive" strokeWidth={2} aria-hidden="true" />
              <span>{t('download.actions.cancel')}</span>
            </>
          )}
        </button>
      </div>

      {startDisabledReason ? (
        <div
          id="start-disabled-reason"
          className="flex items-start gap-2 rounded-lg bg-muted/50 p-2.5 text-xs text-muted-foreground"
          role="status"
        >
          <Info
            className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground"
            strokeWidth={2}
            aria-hidden="true"
          />
          <span>{startDisabledReason}</span>
        </div>
      ) : null}
    </div>
  );
}
