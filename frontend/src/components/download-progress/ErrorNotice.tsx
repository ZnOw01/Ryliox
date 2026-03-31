import { parseApiError } from '../../lib/api-error';
import { useTranslation } from 'react-i18next';

type ErrorNoticeProps = {
  error: unknown;
  /** Optional ID for aria-describedby reference */
  id?: string;
  /** Accessible label describing the error context */
  ariaLabel?: string;
};

export function ErrorNotice({ error, id, ariaLabel }: ErrorNoticeProps) {
  const { t } = useTranslation();
  const parsed = parseApiError(error);

  return (
    <div
      id={id}
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      aria-label={ariaLabel || t('common.error')}
      className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive-foreground"
    >
      <p className="font-medium">{parsed.message}</p>
      {parsed.code ? (
        <p className="mt-1 text-xs">
          {t('common.code')}: {parsed.code}
        </p>
      ) : null}
      {parsed.details ? (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded border border-destructive/20 bg-background p-2 text-xs text-destructive-foreground">
          {parsed.details}
        </pre>
      ) : null}
    </div>
  );
}
