import { formatName } from './utils';
import { useTranslation } from 'react-i18next';
import { BookOpen, FileText, Layers, Sparkles, Check } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Badge } from '../ui/Badge';

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

function getFormatIcon(item: string) {
  if (item === 'epub') {
    return BookOpen;
  }
  if (item === 'pdf-chapters') {
    return Layers;
  }
  return FileText;
}

function getFormatBadge(item: string, t: (key: string) => string) {
  if (item === 'epub') {
    return {
      text: t('download.format.badges.recommended') || 'Recommended',
      variant: 'default' as const,
    };
  }
  if (item === 'pdf-chapters') {
    return {
      text: t('download.format.badges.chapter_files') || 'Per Chapter',
      variant: 'secondary' as const,
    };
  }
  return {
    text: t('download.format.badges.single_file') || 'Single File',
    variant: 'outline' as const,
  };
}

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
  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    const available = formats.filter(item => !(hasChapterSelection && bookOnlyFormats.has(item)));
    if (available.length <= 1) return;

    let targetItem: string | undefined;
    const currentItem = formats[currentIndex];
    const availableIndex = available.indexOf(currentItem);

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = (availableIndex + 1) % available.length;
      targetItem = available[nextIndex];
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = (availableIndex - 1 + available.length) % available.length;
      targetItem = available[prevIndex];
    }

    if (targetItem && targetItem !== format) {
      onChange(targetItem);
    }
  };
  return (
    <div className="min-w-0 text-sm leading-tight">
      <div className="mb-2 flex items-center justify-between">
        <label
          htmlFor={selectId}
          className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          {t('download.format.label')}
        </label>
        {format && (
          <span className="text-[11px] font-semibold text-primary">{formatName(format, t)}</span>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : null}

      {!isLoading && formats.length > 0 && (
        <div
          role="radiogroup"
          aria-label={ariaLabel || t('download.format.aria_label')}
          className="grid grid-cols-1 gap-2 sm:grid-cols-3"
        >
          {formats.map(item => {
            const isSelected = format === item;
            const isDisabled = hasChapterSelection && bookOnlyFormats.has(item);
            const Icon = getFormatIcon(item);
            const badge = getFormatBadge(item, t);

            return (
              <button
                key={item}
                type="button"
                role="radio"
                tabIndex={
                  isSelected || (!formats.includes(format) && formats.indexOf(item) === 0) ? 0 : -1
                }
                aria-checked={isSelected}
                aria-disabled={isDisabled}
                disabled={isDisabled || disabled}
                onClick={() => onChange(item)}
                onKeyDown={e => handleKeyDown(e, formats.indexOf(item))}
                className={cn(
                  'group relative flex flex-col justify-between rounded-xl border p-3 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isSelected
                    ? 'border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/20'
                    : 'border-border bg-card hover:border-primary/30 hover:bg-accent/50',
                  isDisabled && 'cursor-not-allowed opacity-50 bg-muted/50 hover:border-border'
                )}
              >
                <div className="flex items-start justify-between gap-1 mb-2">
                  <div
                    className={cn(
                      'flex h-7 w-7 items-center justify-center rounded-lg transition-colors',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground group-hover:text-foreground'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <Badge variant={badge.variant} size="sm" className="text-[10px] px-1.5 py-0">
                    {badge.text}
                  </Badge>
                </div>

                <div>
                  <div className="flex items-center gap-1">
                    <span
                      className={cn(
                        'text-xs font-semibold leading-tight',
                        isSelected ? 'text-primary' : 'text-foreground'
                      )}
                    >
                      {formatName(item, t)}
                    </span>
                    {isSelected && (
                      <Check className="h-3 w-3 text-primary ml-auto" strokeWidth={2.5} />
                    )}
                  </div>
                  <p className="mt-0.5 line-clamp-1 text-[10px] text-muted-foreground">
                    {descriptions?.[item] || item.toUpperCase()}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Hidden native select for screen reader & form compatibility */}
      <select
        id={selectId}
        value={selectValue}
        onChange={event => onChange(event.target.value)}
        aria-label={ariaLabel || t('download.format.aria_label')}
        aria-describedby={helperId}
        disabled={disabled}
        className="sr-only"
        tabIndex={-1}
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
