import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { getCookies, getHealth, getStatus, saveCookies } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import { EnhancedEmptyState } from './ui/EnhancedEmptyState';
import {
  Copy,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Key,
  RefreshCw,
  Clipboard,
  ExternalLink,
  Check,
  AlertTriangle,
  X,
} from 'lucide-react';
import { parseApiError } from '../lib/api-error';
import { toast } from './ui/BeautifulToast';
import { cn } from '../lib/cn';

type StatusTone = 'green' | 'amber' | 'red' | 'checking';

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

function StatusIcon({ tone }: { tone: StatusTone }) {
  if (tone === 'checking') {
    return (
      <Loader2
        className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0"
        strokeWidth={2.5}
        aria-hidden="true"
      />
    );
  }
  if (tone === 'green') {
    return <Check className="h-3.5 w-3.5 shrink-0 stroke-[2.5]" aria-hidden="true" />;
  }
  if (tone === 'amber') {
    return <AlertTriangle className="h-3.5 w-3.5 shrink-0 stroke-[2.5]" aria-hidden="true" />;
  }
  return <X className="h-3.5 w-3.5 shrink-0 stroke-[2.5]" aria-hidden="true" />;
}

export function AuthStatusCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [cookiesText, setCookiesText] = useState('');
  const [showCookieEditor, setShowCookieEditor] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedCookies, setCopiedCookies] = useState(false);
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
  }, [cookiesQuery.data?.cookies, cookiesText]);

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
      toast.success(t('download.notifications.cookies_saved'));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.authStatus }),
        queryClient.invalidateQueries({ queryKey: queryKeys.storedCookies }),
      ]);
    },
    onError: (err: Error) => {
      toast.error(`${t('download.notifications.cookies_error')}: ${err.message}`);
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
    ? 'checking'
    : authStatus.valid
      ? 'green'
      : authStatus.reason === 'network_error' && authStatus.has_cookies
        ? 'amber'
        : 'red';
  const badgeClassName =
    statusTone === 'green'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/30 dark:bg-emerald-950/20 dark:text-emerald-400'
      : statusTone === 'checking'
        ? 'border-neutral-200 bg-neutral-50 text-neutral-600 dark:border-neutral-800/30 dark:bg-neutral-950/20 dark:text-neutral-400'
        : statusTone === 'amber'
          ? 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800/30 dark:bg-amber-950/20 dark:text-amber-400'
          : 'border-red-200 bg-red-50 text-red-700 dark:border-red-800/30 dark:bg-red-950/20 dark:text-red-400';

  const persistedCookieCount = useMemo(
    () => Object.keys(cookiesQuery.data?.cookies ?? {}).length,
    [cookiesQuery.data?.cookies]
  );
  const visibleErrors = useMemo(() => {
    const items = [healthQuery.error, statusQuery.error, cookiesMutation.error].filter(Boolean);
    const seen = new Set<string>();

    return items.filter(error => {
      const parsed = parseApiError(error);
      if (seen.has(parsed.message)) {
        return false;
      }
      seen.add(parsed.message);
      return true;
    });
  }, [healthQuery.error, statusQuery.error, cookiesMutation.error]);

  const copyCookiesToClipboard = useCallback(async () => {
    if (!cookiesText.trim()) return;
    try {
      await navigator.clipboard.writeText(cookiesText);
      setCopiedCookies(true);
      toast.success(t('download.progress.path_copied'));
      setTimeout(() => setCopiedCookies(false), 2000);
    } catch {
      // clipboard not available
    }
  }, [cookiesText, t]);

  const pasteFromClipboard = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setCookiesText(text);
      }
    } catch {
      // clipboard permission denied
    }
  }, []);

  const formatCookiesJson = useCallback(() => {
    try {
      const parsed = JSON.parse(cookiesText);
      setCookiesText(JSON.stringify(parsed, null, 2));
    } catch {
      // ignore invalid JSON
    }
  }, [cookiesText]);

  useEffect(() => {
    if (!shouldShowCookieEditor) {
      return;
    }

    const el = cookiesTextareaRef.current;
    if (!el) {
      return;
    }

    el.style.height = 'auto';
    const minHeight = 140;
    const maxHeight = Math.round(window.innerHeight * 0.5);
    const targetHeight = Math.min(maxHeight, Math.max(minHeight, el.scrollHeight + 2));
    el.style.height = `${targetHeight}px`;
  }, [cookiesText, shouldShowCookieEditor]);

  // Clean collapsed card when session is healthy
  if (sessionHealthy && !shouldShowCookieEditor && !isExpanded) {
    return (
      <section className="premium-card min-w-0 flex-shrink-0 self-start overflow-hidden p-5 w-full">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </div>
            <div className="min-w-0">
              <span className="text-sm font-semibold text-foreground truncate block">
                {t('auth.title')}:{' '}
                <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                  {t('auth.status.valid')}
                </span>
              </span>
              <span className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                {persistedCookieCount > 0
                  ? `${t('auth.cookies.saved')}: ${persistedCookieCount}`
                  : 'SQLite Vault Encrypted'}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsExpanded(true)}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0"
          >
            {t('auth.cookies.configure')}
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="premium-card min-w-0 flex-shrink-0 self-start overflow-hidden p-6">
      <div className="mb-4 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Key className="h-4 w-4" strokeWidth={2} />
          </div>
          <div>
            <h2 className="text-base font-semibold leading-tight text-foreground sm:text-lg">
              {t('auth.title')}
            </h2>
          </div>
          {sessionHealthy && (
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="text-xs text-muted-foreground hover:text-foreground transition underline underline-offset-2 ml-2"
            >
              {t('common.collapse')}
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={() => {
            void queryClient.invalidateQueries({
              queryKey: queryKeys.authStatus,
            });
            void queryClient.invalidateQueries({
              queryKey: queryKeys.apiHealth,
            });
            if (authStatus?.has_cookies) {
              void queryClient.invalidateQueries({
                queryKey: queryKeys.storedCookies,
              });
            }
          }}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={2} />
          {t('auth.refresh')}
        </button>
      </div>

      <div className="mb-3 flex min-w-0 items-center gap-2">
        <span
          role="status"
          aria-live="polite"
          className={`inline-flex max-w-full flex-wrap items-center gap-2 break-words rounded-full border px-3 py-1 text-xs font-semibold leading-tight ${badgeClassName}`}
        >
          <StatusIcon tone={statusTone} />
          {statusLabel}
        </span>
      </div>

      {healthQuery.data ? (
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
          <p
            className="flex items-center gap-1.5"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <span
              className={`h-2 w-2 rounded-full ${healthQuery.data.status === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`}
            />
            {healthQuery.data.status === 'ok'
              ? t('auth.service.available')
              : t('auth.service.status', { status: healthQuery.data.status })}
          </p>
          {typeof healthQuery.data.uptime_seconds === 'number' ? (
            <p>
              {t('auth.uptime')}: {formatUptime(healthQuery.data.uptime_seconds)}
            </p>
          ) : null}
        </div>
      ) : null}

      {!healthQuery.data && healthQuery.isFetching ? (
        <p className="mb-3 text-xs text-muted-foreground" role="status" aria-live="polite">
          {t('auth.service.checking')}
        </p>
      ) : null}

      {visibleErrors.length > 0 ? (
        <div className="mb-4 space-y-2">
          {visibleErrors.map(error => {
            const parsed = parseApiError(error);
            return (
              <div
                key={parsed.message}
                className="flex items-start gap-2 rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive"
                role="alert"
                aria-live="assertive"
              >
                <AlertCircle
                  className="mt-0.5 h-4 w-4 shrink-0"
                  strokeWidth={2}
                  aria-hidden="true"
                />
                <span>{parsed.message}</span>
              </div>
            );
          })}
        </div>
      ) : null}

      {sessionHealthy && persistedCookieCount > 0 && !shouldShowCookieEditor ? (
        <p
          className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50/70 dark:border-emerald-900/30 dark:bg-emerald-950/20 px-3 py-2 text-xs leading-tight text-emerald-800 dark:text-emerald-300"
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
        <div id="cookie-editor" className="mt-2">
          <div className="mb-2 flex items-center justify-between gap-2">
            <label
              className="block text-xs font-medium uppercase tracking-wide text-muted-foreground"
              htmlFor="cookies-payload"
            >
              {t('auth.cookies.label')}
            </label>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={pasteFromClipboard}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition"
                title="Paste from clipboard"
              >
                <Clipboard className="h-3 w-3" />
                <span className="hidden sm:inline">Pegar</span>
              </button>
              {cookiesText.trim() ? (
                <>
                  <button
                    type="button"
                    onClick={formatCookiesJson}
                    className="rounded-md border border-border bg-background px-2 py-1 text-[11px] font-mono text-muted-foreground transition hover:bg-accent"
                    title={t('auth.cookies.format_json')}
                  >
                    {'{}'}
                  </button>
                  <button
                    type="button"
                    onClick={copyCookiesToClipboard}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-muted-foreground transition hover:bg-accent"
                    title={t('auth.cookies.copy_to_clipboard')}
                    aria-label={t('auth.cookies.copy_json_to_clipboard')}
                  >
                    {copiedCookies ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-600 dark:text-emerald-400 stroke-[2.5]" />
                        <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                          Copiado
                        </span>
                      </>
                    ) : (
                      <Copy className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                    )}
                  </button>
                </>
              ) : null}
            </div>
          </div>

          <textarea
            id="cookies-payload"
            ref={cookiesTextareaRef}
            value={cookiesText}
            onChange={event => setCookiesText(event.target.value)}
            placeholder={t('auth.cookies.placeholder')}
            className="w-full resize-none overflow-y-auto rounded-xl border border-input bg-background/80 p-3 font-mono text-xs leading-relaxed text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:bg-background focus:ring-2 focus:ring-primary/20 shadow-xs"
            spellCheck={false}
          />

          {cookiesText.trim() ? <FormattedJsonPreview json={cookiesText} /> : null}

          <div className="mt-3.5 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => cookiesMutation.mutate(cookiesText)}
              disabled={!cookiesText.trim() || cookiesMutation.isPending}
              className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-xs transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
            >
              {cookiesMutation.isPending ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
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
                className="rounded-xl border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent"
              >
                {t('auth.cookies.hide_editor')}
              </button>
            ) : null}

            <a
              href="https://github.com/ZnOw01/Ryliox#cookie-setup"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              {t('auth.cookies.help_link')}
              <ExternalLink className="h-3 w-3" />
            </a>

            {cookiesQuery.isFetching ? (
              <span className="text-xs text-muted-foreground" role="status" aria-live="polite">
                {t('auth.cookies.loading')}
              </span>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => {
              setCookiesText('');
              hasPrefilledRef.current = false;
              setShowCookieEditor(true);
            }}
            aria-expanded={shouldShowCookieEditor}
            className="rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground transition hover:bg-accent"
          >
            {t('auth.cookies.show_editor')}
          </button>
        </div>
      )}
    </section>
  );
}

function maskValue(value: string): string {
  if (value.length <= 8) return '****';
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function FormattedJsonPreview({ json }: { json: string }) {
  const { t } = useTranslation();
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = JSON.parse(json);
  } catch {
    // not valid JSON
  }
  if (!parsed || Object.keys(parsed).length === 0) return null;

  const entries = Object.entries(parsed);

  return (
    <div className="mt-2.5 overflow-hidden rounded-xl border border-border bg-muted/40 shadow-2xs">
      <div className="border-b border-border bg-muted/60 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
        <span>{t('auth.cookies.preview')}</span>
        <span className="font-mono text-primary font-bold">{entries.length} cookies</span>
      </div>
      <div className="divide-y divide-border max-h-40 overflow-y-auto chapter-scroll">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-start gap-2 px-3 py-1.5 text-xs">
            <span className="shrink-0 font-medium text-primary">{key}</span>
            <span className="min-w-0 break-all text-foreground/80 font-mono text-[11px]">
              {typeof value === 'string' ? `"${maskValue(value)}"` : JSON.stringify(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
