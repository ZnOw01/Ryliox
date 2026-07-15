import { parseApiError } from '../../lib/api-error';
import { useTranslation } from 'react-i18next';
import { AlertCircle } from 'lucide-react';

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
      className="mb-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
    >
      <AlertCircle
        className="mt-0.5 h-4 w-4 shrink-0 text-red-600"
        strokeWidth={2}
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="font-medium">{parsed.message}</p>
        {parsed.code ? (
          <p className="mt-1 text-xs">
            {t('common.code')}: {parsed.code}
          </p>
        ) : null}
        {parsed.details ? (
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded border border-red-200 bg-white p-2 text-xs text-red-800">
            {parsed.details}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
