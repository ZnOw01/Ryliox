import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getCookies, getHealth, getStatus, saveCookies } from "../lib/api";
import { queryKeys } from "../lib/query-keys";

type StatusTone = "green" | "amber" | "red";

function formatAuthReason(reason: string | null | undefined): string {
  if (!reason) {
    return "desconocido";
  }
  const labels: Record<string, string> = {
    network_error: "servicio no disponible",
    not_authenticated: "sesion no autenticada",
    subscription_expired: "suscripcion expirada",
  };
  return labels[reason] ?? reason.replace(/_/g, " ");
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
  const queryClient = useQueryClient();
  const [cookiesText, setCookiesText] = useState("");
  const [showCookieEditor, setShowCookieEditor] = useState(false);
  const [hasPrefilledCookies, setHasPrefilledCookies] = useState(false);
  const cookiesTextareaRef = useRef<HTMLTextAreaElement | null>(null);

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
    authStatus?.valid || (authStatus?.reason === "network_error" && authStatus?.has_cookies),
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
      setHasPrefilledCookies(false);
    }
  }, [shouldShowCookieEditor]);

  useEffect(() => {
    const storedCookies = cookiesQuery.data?.cookies;
    if (!storedCookies || Object.keys(storedCookies).length === 0) {
      return;
    }
    if (cookiesText.trim().length > 0 || hasPrefilledCookies) {
      return;
    }
    setCookiesText(JSON.stringify(storedCookies, null, 2));
    setHasPrefilledCookies(true);
  }, [cookiesQuery.data?.cookies, cookiesText, hasPrefilledCookies]);

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
      setCookiesText("");
      setHasPrefilledCookies(false);
      setShowCookieEditor(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.authStatus }),
        queryClient.invalidateQueries({ queryKey: queryKeys.storedCookies }),
      ]);
    },
  });

  const statusLabel = !authStatus
    ? "Verificando sesion..."
    : authStatus.valid
      ? "Sesion valida"
      : authStatus.reason === "network_error" && authStatus.has_cookies
        ? "Cookies cargadas (red no disponible)"
        : `Sesion invalida (${formatAuthReason(authStatus.reason)})`;
  const statusTone: StatusTone = !authStatus
    ? "amber"
    : authStatus.valid
      ? "green"
      : authStatus.reason === "network_error" && authStatus.has_cookies
        ? "amber"
        : "red";
  const badgeClassName =
    statusTone === "green"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : statusTone === "amber"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-red-200 bg-red-50 text-red-700";

  function StatusIcon() {
    if (statusTone === "green") {
      return (
        <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    }
    if (statusTone === "amber") {
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
    [cookiesQuery.data?.cookies],
  );

  useEffect(() => {
    if (!shouldShowCookieEditor) {
      return;
    }

    const el = cookiesTextareaRef.current;
    if (!el) {
      return;
    }

    el.style.height = "auto";
    const minHeight = 160;
    const maxHeight = Math.round(window.innerHeight * 0.62);
    const targetHeight = Math.min(maxHeight, Math.max(minHeight, el.scrollHeight + 2));
    el.style.height = `${targetHeight}px`;
  }, [cookiesText, shouldShowCookieEditor]);

  return (
    <section className="soft-rise min-w-0 self-start overflow-hidden rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-panel backdrop-blur">
      <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink">Autenticacion</h2>
        <button
          type="button"
          onClick={() => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.authStatus });
            void queryClient.invalidateQueries({ queryKey: queryKeys.apiHealth });
            if (authStatus?.has_cookies) {
              void queryClient.invalidateQueries({ queryKey: queryKeys.storedCookies });
            }
          }}
          className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            <path d="M6.5 1.5L8 2.5L6.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Actualizar
        </button>
      </div>

      <div className="mb-3 flex min-w-0 items-center gap-2">
        <span
          role="status"
          aria-live="polite"
          className={`inline-flex max-w-full flex-wrap items-center gap-1.5 break-words rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClassName}`}
        >
          <StatusIcon />
          {statusLabel}
        </span>
      </div>
      {healthQuery.data ? (
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="flex items-center gap-1.5 text-xs text-slate-500" role="status" aria-live="polite" aria-atomic="true">
            <span className={`h-1.5 w-1.5 rounded-full ${healthQuery.data.status === "ok" ? "bg-emerald-400" : "bg-amber-400"}`} />
            {healthQuery.data.status === "ok" ? "Servicio disponible" : `Servicio: ${healthQuery.data.status}`}
          </p>
          {typeof healthQuery.data.uptime_seconds === "number" ? (
            <p className="text-xs text-slate-400">
              Uptime: {formatUptime(healthQuery.data.uptime_seconds)}
            </p>
          ) : null}
        </div>
      ) : null}
      {!healthQuery.data && healthQuery.isFetching ? <p className="mb-3 text-xs text-slate-500" role="status" aria-live="polite">Verificando servicio...</p> : null}
      {healthQuery.error ? <p className="mb-3 text-sm text-red-600" role="alert" aria-live="assertive">Servicio no disponible: {(healthQuery.error as Error).message}</p> : null}
      {statusQuery.error ? <p className="mb-3 text-sm text-red-600" role="alert" aria-live="assertive">{(statusQuery.error as Error).message}</p> : null}
      {sessionHealthy && persistedCookieCount > 0 && !shouldShowCookieEditor ? (
        <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800" role="status" aria-live="polite" aria-atomic="true">
          Cookies guardadas: {persistedCookieCount}
        </p>
      ) : null}

      {shouldShowCookieEditor ? (
        <div id="cookie-editor">
          <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-500" htmlFor="cookies-payload">
            Cookies (JSON o encabezado HTTP)
          </label>
          <textarea
            id="cookies-payload"
            ref={cookiesTextareaRef}
            value={cookiesText}
            onChange={(event) => setCookiesText(event.target.value)}
            placeholder='{"cookie": "value"} o "a=1; b=2"'
            className="w-full resize-none overflow-y-auto rounded-xl border border-slate-700/70 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none ring-brand placeholder:text-slate-400 focus:border-brand focus:ring-2"
          />

          <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap sm:items-center sm:gap-3">
            <button
              type="button"
              onClick={() => cookiesMutation.mutate(cookiesText)}
              disabled={!cookiesText.trim() || cookiesMutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            >
              {cookiesMutation.isPending ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Guardando...
                </>
              ) : "Guardar cookies"}
            </button>

            {sessionHealthy ? (
              <button
                type="button"
                onClick={() => setShowCookieEditor(false)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 sm:w-auto"
              >
                Ocultar editor
              </button>
            ) : null}

            {cookiesQuery.isFetching ? <span className="text-xs text-slate-500" role="status" aria-live="polite">Cargando cookies guardadas...</span> : null}
          </div>
        </div>
      ) : (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => {
              setCookiesText("");
              setHasPrefilledCookies(false);
              setShowCookieEditor(true);
            }}
            aria-expanded={shouldShowCookieEditor}
              className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
          >
              Ver / editar cookies
          </button>
        </div>
      )}

      {cookiesMutation.error ? <p className="mt-2 text-sm text-red-600" role="alert" aria-live="assertive">{(cookiesMutation.error as Error).message}</p> : null}
    </section>
  );
}
