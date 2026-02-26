import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { parseApiError } from "../lib/api-error";
import { searchBooks } from "../lib/api";
import { queryKeys } from "../lib/query-keys";
import type { SearchBook } from "../lib/types";
import { useDebouncedValue } from "../lib/use-debounced-value";
import { useBookStore } from "../store/book-store";

type SearchScope = "all" | "title" | "author" | "publisher";

const SEARCH_SCOPES: Array<{ value: SearchScope; label: string }> = [
  { value: "all", label: "Todos los campos" },
  { value: "title", label: "Titulo" },
  { value: "author", label: "Autor" },
  { value: "publisher", label: "Editorial" },
];

function readSearchStateFromUrl(): { query: string; scope: SearchScope } {
  if (typeof window === "undefined") {
    return { query: "", scope: "all" };
  }

  const params = new URLSearchParams(window.location.search);
  const query = (params.get("q") || "").trim();
  const rawScope = (params.get("scope") || "all").toLowerCase();
  const scope = SEARCH_SCOPES.some((item) => item.value === rawScope) ? (rawScope as SearchScope) : "all";

  return { query, scope };
}

function searchMatch(book: SearchBook, query: string, scope: SearchScope): boolean {
  if (!query) {
    return true;
  }

  const value = query.toLowerCase();
  const title = (book.title || "").toLowerCase();
  const authors = (book.authors || []).join(" ").toLowerCase();
  const publishers = (book.publishers || []).join(" ").toLowerCase();

  if (scope === "title") {
    return title.includes(value);
  }
  if (scope === "author") {
    return authors.includes(value);
  }
  if (scope === "publisher") {
    return publishers.includes(value);
  }
  return title.includes(value) || authors.includes(value) || publishers.includes(value);
}

export function SearchBooksCard() {
  const selectedBookId = useBookStore((state) => state.selectedBook?.id ?? null);
  const setSelectedBook = useBookStore((state) => state.setSelectedBook);
  const [queryInput, setQueryInput] = useState(() => readSearchStateFromUrl().query);
  const [scope, setScope] = useState<SearchScope>(() => readSearchStateFromUrl().scope);
  const normalizedQuery = queryInput.trim();
  const debouncedQuery = useDebouncedValue(normalizedQuery, 350);
  const lastDebouncedQueryRef = useRef(debouncedQuery);

  const searchQuery = useQuery({
    queryKey: queryKeys.search(debouncedQuery),
    queryFn: () => searchBooks(debouncedQuery),
    enabled: debouncedQuery.length > 0,
    staleTime: 30000,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    if (debouncedQuery) {
      params.set("q", debouncedQuery);
    } else {
      params.delete("q");
    }

    if (scope === "all") {
      params.delete("scope");
    } else {
      params.set("scope", scope);
    }

    params.delete("cover");

    const search = params.toString();
    const currentSearch = window.location.search.startsWith("?") ? window.location.search.slice(1) : window.location.search;
    if (search === currentSearch) {
      lastDebouncedQueryRef.current = debouncedQuery;
      return;
    }

    const nextUrl = `${window.location.pathname}${search ? `?${search}` : ""}`;
    if (lastDebouncedQueryRef.current !== debouncedQuery) {
      window.history.pushState(null, "", nextUrl);
    } else {
      window.history.replaceState(null, "", nextUrl);
    }
    lastDebouncedQueryRef.current = debouncedQuery;
  }, [debouncedQuery, scope]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const onPopState = () => {
      const next = readSearchStateFromUrl();
      setQueryInput(next.query);
      setScope(next.scope);
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const filteredResults = useMemo(() => {
    if (!normalizedQuery) {
      return [];
    }
    if (normalizedQuery !== debouncedQuery) {
      return [];
    }

    const results = searchQuery.data?.results || [];
    return results.filter((book) => searchMatch(book, debouncedQuery, scope));
  }, [debouncedQuery, normalizedQuery, scope, searchQuery.data?.results]);

  const parsedError = debouncedQuery && searchQuery.error ? parseApiError(searchQuery.error) : null;
  const isSearching = Boolean(normalizedQuery) && (searchQuery.isPending || searchQuery.isFetching);
  const visibleResults = isSearching ? [] : filteredResults;
  const resultCount = filteredResults.length;

  return (
    <section className="soft-rise min-w-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white/95 p-5 shadow-panel backdrop-blur">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink">Buscar libros</h2>
      </div>

      <div className="mb-2 grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <label htmlFor="search-query" className="sr-only">
          Buscar libros
        </label>
        <input
          id="search-query"
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
          placeholder="python, ISBN, titulo..."
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-brand focus:border-brand/70 focus:ring-2"
        />
        <button
          type="button"
          onClick={() => {
            setQueryInput("");
            setScope("all");
          }}
          className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 focus-visible:ring-offset-2 focus-visible:ring-offset-white hover:bg-slate-50 sm:w-auto"
        >
          Limpiar
        </button>
      </div>

      <div className="mb-4">
        <label className="text-sm">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Filtrar por</span>
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value as SearchScope)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:max-w-xs"
          >
            {SEARCH_SCOPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isSearching ? (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-brand/30 bg-brand/5 px-3 py-2 text-sm text-brand" role="status" aria-live="polite">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
          Buscando libros...
        </div>
      ) : null}
      {parsedError ? (
        <p className="text-sm text-red-600">
          {parsedError.message}
          {parsedError.code ? ` (${parsedError.code})` : ""}
        </p>
      ) : null}

      {normalizedQuery && !isSearching && !parsedError ? (
        <p className="mb-2 text-xs text-slate-500" role="status" aria-live="polite">
          {resultCount} resultado{resultCount === 1 ? "" : "s"}.
        </p>
      ) : null}

      <ul className={`m-0 list-none space-y-2 p-0 ${isSearching ? "pointer-events-none opacity-70" : ""}`} aria-busy={isSearching}>
        {visibleResults.map((book) => {
          const isSelected = selectedBookId === book.id;
          return (
            <li key={book.id}>
              <button
                type="button"
                onClick={() => setSelectedBook(book)}
                aria-label={`${isSelected ? "Libro seleccionado" : "Seleccionar libro"}: ${book.title}`}
                aria-pressed={isSelected}
                className={`group w-full rounded-xl border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-brand/40 ${
                  isSelected
                    ? "border-brand/40 bg-brand/10 shadow-[0_8px_24px_-18px_rgba(15,118,110,0.55)]"
                    : "border-slate-200 hover:border-brand/35 hover:bg-brand/5"
                }`}
              >
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-3">
                    <div className="h-20 w-14 flex-none overflow-hidden rounded-md border border-slate-200 bg-slate-100">
                      {book.cover_url ? (
                        <img
                          src={book.cover_url}
                          alt={book.title}
                          width={56}
                          height={80}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-slate-50 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                          Sin portada
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{book.title}</p>
                      <p className="mt-1 truncate text-xs text-slate-600">{book.authors?.join(", ") || "Autor desconocido"}</p>
                      <p className="truncate text-xs text-slate-500">
                        {book.publishers?.join(", ") || "Editorial desconocida"}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`flex-shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold ${
                      isSelected
                        ? "bg-brand/15 text-brand-deep"
                        : "bg-slate-100 text-slate-600 group-hover:bg-brand/10 group-hover:text-brand-deep"
                    }`}
                  >
                    {isSelected ? "Seleccionado" : "Seleccionar"}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      {!normalizedQuery ? (
        <p className="mt-3 text-sm text-slate-500" role="status" aria-live="polite">
          Escribe una consulta para buscar libros.
        </p>
      ) : null}
      {debouncedQuery && !isSearching && !parsedError && visibleResults.length === 0 ? (
        <p className="break-all text-sm text-slate-500" role="status" aria-live="polite">
          No hay resultados para "{debouncedQuery}".
        </p>
      ) : null}
    </section>
  );
}
