import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { getCookies, getHealth, getStatus, saveCookies } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import { EnhancedEmptyState } from './ui/EnhancedEmptyState';

type StatusTone = 'green' | 'amber' | 'red';

function formatAuthReason(reason: string | null | undefined, t: (key: string) => string): string {
  if (!reason) {
    return t('auth.status.reason.unknown');
  }
  const labels: Record<string, string> = {
    network_error: t('auth.status.reason.network_error'),
    not_authenticated: t('auth.status.reason.not_authenticated'),
    subscription_expired: t('auth.status.reason.subscription_expired'),
  };
  return labels[reason] ?? reason.replace(/_/g, ' ');
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  const hrs = hours % 24;
  return hrs > 0 ? `${days}d ${hrs}h` : `${days}d`;
}

export function AuthStatusCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [cookiesText, setCookiesText] = useState('');
  const [showCookieEditor, setShowCookieEditor] = useState(false);
  const cookiesTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const hasPrefilledRef = useRef(false);

  const statusQuery = useQuery({
    queryKey: queryKeys.authStatus,
    queryFn: getStatus,
    refetchInterval: 30000,
  });

  const healthQuery = useQuery({
    queryKey: queryKeys.apiHealth,
    queryFn: getHealth,
    refetchInterval: 30000,
  });
  const authStatus = statusQuery.data ?? null;

  const sessionHealthy = Boolean(
    authStatus?.valid || (authStatus?.reason === 'network_error' && authStatus?.has_cookies)
  );
  const checkingSession = statusQuery.isPending && !authStatus;
  const shouldShowCookieEditor = showCookieEditor || (!checkingSession && !sessionHealthy);

  const cookiesQuery = useQuery({
    queryKey: queryKeys.storedCookies,
    queryFn: getCookies,
    enabled: shouldShowCookieEditor || Boolean(authStatus?.has_cookies),
    staleTime: 30000,
  });

  useEffect(() => {
    if (!shouldShowCookieEditor) {
      hasPrefilledRef.current = false;
    }
  }, [shouldShowCookieEditor]);

  useEffect(() => {
    const storedCookies = cookiesQuery.data?.cookies;
    if (!storedCookies || Object.keys(storedCookies).length === 0) {
      return;
    }
    if (cookiesText.trim().length > 0 || hasPrefilledRef.current) {
      return;
    }
    setCookiesText(JSON.stringify(storedCookies, null, 2));
    hasPrefilledRef.current = true;
  }, [cookiesQuery.data?.cookies]);

  const cookiesMutation = useMutation({
    mutationFn: async (raw: string) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = raw;
      }
      return saveCookies(parsed);
    },
    onSuccess: async () => {
      setCookiesText('');
      hasPrefilledRef.current = false;
      setShowCookieEditor(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.authStatus }),
        queryClient.invalidateQueries({ queryKey: queryKeys.storedCookies }),
      ]);
    },
  });

  const statusLabel = !authStatus
    ? t('auth.status.checking')
    : authStatus.valid
      ? t('auth.status.valid')
      : authStatus.reason === 'network_error' && authStatus.has_cookies
        ? t('auth.status.cookies_loaded')
        : `${t('auth.status.invalid')} (${formatAuthReason(authStatus.reason, t)})`;
  const statusTone: StatusTone = !authStatus
    ? 'amber'
    : authStatus.valid
      ? 'green'
      : authStatus.reason === 'network_error' && authStatus.has_cookies
        ? 'amber'
        : 'red';
  const badgeClassName =
    statusTone === 'green'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
      : statusTone === 'amber'
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : 'border-red-200 bg-red-50 text-red-700';

  function StatusIcon() {
    if (statusTone === 'green') {
      return (
        <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M3 8l3.5 3.5L13 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    }
    if (statusTone === 'amber') {
      return (
        <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 5v4M8 11v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      );
    }
    return (
      <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  const persistedCookieCount = useMemo(
    () => Object.keys(cookiesQuery.data?.cookies ?? {}).length,
    [cookiesQuery.data?.cookies]
  );

  useEffect(() => {
    if (!shouldShowCookieEditor) {
      return;
    }

    const el = cookiesTextareaRef.current;
    if (!el) {
      return;
    }

    el.style.height = 'auto';
    const minHeight = 160;
    const maxHeight = Math.round(window.innerHeight * 0.62);
    const targetHeight = Math.min(maxHeight, Math.max(minHeight, el.scrollHeight + 2));
    el.style.height = `${targetHeight}px`;
  }, [cookiesText, shouldShowCookieEditor]);

  return (
    <section className="soft-rise min-w-0 flex-shrink-0 self-start overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-panel backdrop-blur-sm">
      <div className="mb-4 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold leading-tight text-foreground">{t('auth.title')}</h2>
        <button
          type="button"
          onClick={() => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.authStatus });
            void queryClient.invalidateQueries({ queryKey: queryKeys.apiHealth });
            if (authStatus?.has_cookies) {
              void queryClient.invalidateQueries({ queryKey: queryKeys.storedCookies });
            }
          }}
          className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M13.5 8A5.5 5.5 0 1 1 8 2.5"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M6.5 1.5L8 2.5L6.5 3.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {t('auth.refresh')}
        </button>
      </div>

      <div className="mb-4 flex min-w-0 items-center gap-2">
        <span
          role="status"
          aria-live="polite"
          className={`inline-flex max-w-full flex-wrap items-center gap-2 break-words rounded-full border px-3 py-1.5 text-xs font-semibold leading-tight ${badgeClassName}`}
        >
          <StatusIcon />
          {statusLabel}
        </span>
      </div>
      {healthQuery.data ? (
        <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          <p
            className="flex items-center gap-2 text-xs text-muted-foreground"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <span
              className={`h-2 w-2 rounded-full ${healthQuery.data.status === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`}
            />
            {healthQuery.data.status === 'ok'
              ? t('auth.service.available')
              : `Servicio: ${healthQuery.data.status}`}
          </p>
          {typeof healthQuery.data.uptime_seconds === 'number' ? (
            <p className="text-xs text-muted-foreground">
              {t('auth.uptime')}: {formatUptime(healthQuery.data.uptime_seconds)}
            </p>
          ) : null}
        </div>
      ) : null}
      {!healthQuery.data && healthQuery.isFetching ? (
        <p className="mb-4 text-xs text-muted-foreground" role="status" aria-live="polite">
          {t('auth.service.checking')}
        </p>
      ) : null}
      {healthQuery.error ? (
        <p className="mb-4 text-sm text-destructive" role="alert" aria-live="assertive">
          {t('auth.service.unavailable')}: {(healthQuery.error as Error).message}
        </p>
      ) : null}
      {statusQuery.error ? (
        <p className="mb-4 text-sm text-destructive" role="alert" aria-live="assertive">
          {(statusQuery.error as Error).message}
        </p>
      ) : null}
      {sessionHealthy && persistedCookieCount > 0 && !shouldShowCookieEditor ? (
        <p
          className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-tight text-emerald-800"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {t('auth.cookies.saved')}: {persistedCookieCount}
        </p>
      ) : null}

      {/* Empty state mejorado cuando no hay cookies */}
      {!sessionHealthy && persistedCookieCount === 0 && !shouldShowCookieEditor ? (
        <EnhancedEmptyState
          type="cookies"
          variant="default"
          action={{
            label: t('auth.cookies.configure'),
            onClick: () => {
              setCookiesText('');
              hasPrefilledRef.current = false;
              setShowCookieEditor(true);
            },
            variant: 'primary',
          }}
        />
      ) : null}

      {shouldShowCookieEditor ? (
        <div id="cookie-editor">
          <label
            className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
            htmlFor="cookies-payload"
          >
            {t('auth.cookies.label')}
          </label>
          <textarea
            id="cookies-payload"
            ref={cookiesTextareaRef}
            value={cookiesText}
            onChange={event => setCookiesText(event.target.value)}
            placeholder={t('auth.cookies.placeholder')}
            className="w-full resize-none overflow-y-auto rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed text-foreground outline-none ring-ring placeholder:text-muted-foreground focus:border-primary focus:ring-2"
          />

          <div className="mt-4 grid gap-3 sm:flex sm:flex-wrap sm:items-center sm:gap-3">
            <button
              type="button"
              onClick={() => cookiesMutation.mutate(cookiesText)}
              disabled={!cookiesText.trim() || cookiesMutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            >
              {cookiesMutation.isPending ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  {t('auth.cookies.saving')}
                </>
              ) : (
                t('auth.cookies.save')
              )}
            </button>

            {sessionHealthy ? (
              <button
                type="button"
                onClick={() => setShowCookieEditor(false)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-auto"
              >
                {t('auth.cookies.hide_editor')}
              </button>
            ) : null}

            {cookiesQuery.isFetching ? (
              <span className="text-xs text-muted-foreground" role="status" aria-live="polite">
                {t('auth.cookies.loading')}
              </span>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => {
              setCookiesText('');
              hasPrefilledRef.current = false;
              setShowCookieEditor(true);
            }}
            aria-expanded={shouldShowCookieEditor}
            className="rounded-lg border border-border bg-background px-3 py-2.5 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {t('auth.cookies.show_editor')}
          </button>
        </div>
      )}

      {cookiesMutation.error ? (
        <p className="mt-4 text-sm text-destructive" role="alert" aria-live="assertive">
          {(cookiesMutation.error as Error).message}
        </p>
      ) : null}
    </section>
  );
}
