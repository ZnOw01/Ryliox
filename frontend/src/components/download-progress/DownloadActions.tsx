import { cn } from '../../lib/cn';
import { Play, X, ArrowClockwise, Image, Spinner, Warning } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

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
  ariaLabel?: string;
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
          <Image className="h-3 w-3" weight="regular" aria-hidden="true" />
        </div>
        <input
          type="checkbox"
          checked={skipImages}
          onChange={event => onSkipImagesChange(event.target.checked)}
          className="sr-only"
          aria-describedby="skip-images-desc"
        />
        <span id="skip-images-desc">{t('download.actions.skip_images')}</span>
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
          className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:py-2"
        >
          {startPending ? (
            <>
              <Spinner
                className="h-4 w-4 animate-spin sm:h-3.5 sm:w-3.5"
                weight="bold"
                aria-hidden="true"
              />
              <span>{t('download.actions.starting')}</span>
            </>
          ) : (
            <>
              <Play
                className="h-5 w-5 fill-current sm:h-4 sm:w-4"
                weight="fill"
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
          className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-3 text-sm font-semibold text-foreground transition hover:border-destructive/30 hover:bg-destructive/5 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 sm:py-2"
        >
          {cancelPending ? (
            <>
              <Spinner
                className="h-4 w-4 animate-spin sm:h-3.5 sm:w-3.5"
                weight="bold"
                aria-hidden="true"
              />
              <span>{t('download.actions.cancelling')}</span>
            </>
          ) : (
            <>
              <X className="h-5 w-5 sm:h-4 sm:w-4" weight="regular" aria-hidden="true" />
              <span>{t('download.actions.cancel')}</span>
            </>
          )}
        </button>

        {canForceReconnect ? (
          <button
            type="button"
            onClick={onForceReconnect}
            className="mobile-full min-h-touch inline-flex w-full items-center justify-center gap-2 rounded-lg border border-warning bg-warning/10 px-4 py-3 text-sm font-semibold text-warning-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring hover:bg-warning/20 sm:col-span-2 sm:py-2"
          >
            <ArrowClockwise className="h-5 w-5 sm:h-4 sm:w-4" weight="regular" aria-hidden="true" />
            <span>{t('download.actions.reconnect')}</span>
          </button>
        ) : null}
      </div>

      {startDisabledReason ? (
        <div id="start-disabled-reason" className="mb-4 flex items-start gap-1.5" role="alert">
          <Warning
            className="mt-0.5 h-4 w-4 shrink-0 text-warning"
            weight="regular"
            aria-hidden="true"
          />
          <p className="text-xs text-warning-foreground">{startDisabledReason}</p>
        </div>
      ) : null}
    </>
  );
}
