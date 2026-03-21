import { parseApiError } from "../../lib/api-error";

type ErrorNoticeProps = {
  error: unknown;
};

export function ErrorNotice({ error }: ErrorNoticeProps) {
  const parsed = parseApiError(error);

  return (
    <div role="alert" aria-live="assertive" className="mb-3 rounded-[1rem] border border-red-200 bg-red-50 p-3 text-sm text-red-700">
      <p className="font-medium leading-relaxed">{parsed.message}</p>
      {parsed.code ? <p className="text-xs">Codigo: {parsed.code}</p> : null}
      {parsed.details ? (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-red-100 bg-white p-2 text-xs leading-relaxed">
          {parsed.details}
        </pre>
      ) : null}
    </div>
  );
}
