import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import {
  Search,
  X,
  BookOpen,
  User,
  Building2,
  Loader2,
  Clock,
  Type,
  PenLine,
  Zap,
  Check,
  Compass,
} from 'lucide-react';

import { parseApiError } from '../lib/api-error';
import { getBookChapters, getBookInfo, getFormats, searchBooks } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import type { SearchBook, SearchResponse } from '../lib/types';
import { useDebouncedValue } from '../lib/use-debounced-value';
import { useBookStore } from '../store/book-store';
import { cn } from '../lib/cn';
import { Badge } from './ui/Badge';
import { EnhancedEmptyState } from './ui/EnhancedEmptyState';
import { BookCover, BookCoverSkeleton } from './ui/BookCover';
import { toast } from './ui/BeautifulToast';
import {
  AnimatedLayoutGroup,
  StaggeredLayoutContainer,
  StaggeredLayoutItem,
} from './motion/LayoutAnimations';
import { OptimizedFadeIn } from './motion/OptimizedAppear';

const SUGGESTED_TOPICS = [
  'Python',
  'Rust',
  'Kubernetes',
  'System Design',
  'AI & Machine Learning',
  'TypeScript',
  'Go',
  'Docker',
];

/**
 * Search Results Skeleton - Shimmer loading effect for search results
 */
function SearchResultsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          className="rounded-xl border border-border bg-card p-3"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div className="flex gap-3">
            <BookCoverSkeleton size="md" />
            <div className="flex-1 space-y-2 py-1">
              <div className="h-5 w-3/4 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

type SearchScope = 'all' | 'title' | 'author' | 'publisher';

const SEARCH_DEBOUNCE_MS = 350;
const SEARCH_STALE_TIME_MS = 30000;
const PREFETCH_STALE_TIME_MS = 2 * 60 * 1000;

function hasSearchResponseShape(value: unknown): boolean {
  if (
    typeof value !== 'object' ||
    value === null ||
    Array.isArray(value) ||
    !('results' in value)
  ) {
    return false;
  }

  const results = value.results;
  if (!Array.isArray(results)) return false;

  return results.every((entry: unknown) => {
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) return false;

    if (
      !('id' in entry) ||
      typeof entry.id !== 'string' ||
      !('title' in entry) ||
      typeof entry.title !== 'string'
    ) {
      return false;
    }

    const authors = 'authors' in entry ? entry.authors : undefined;
    const publishers = 'publishers' in entry ? entry.publishers : undefined;
    const hasValidAuthors =
      authors === undefined ||
      authors === null ||
      (Array.isArray(authors) && authors.every((author: unknown) => typeof author === 'string'));
    const hasValidPublishers =
      publishers === undefined ||
      publishers === null ||
      (Array.isArray(publishers) &&
        publishers.every((publisher: unknown) => typeof publisher === 'string'));

    return hasValidAuthors && hasValidPublishers;
  });
}

function getFreshCachedSearchQuery(query: string, queryClient: QueryClient): string | null {
  if (!query) return null;

  const state = queryClient.getQueryState<SearchResponse>(queryKeys.search.byQuery(query));
  if (state?.status !== 'success' || state.isInvalidated || !hasSearchResponseShape(state.data)) {
    return null;
  }

  const ageMs = Date.now() - state.dataUpdatedAt;
  return ageMs >= 0 && ageMs < SEARCH_STALE_TIME_MS ? query : null;
}

/**
 * Detect if the query is a direct book reference:
 * - An O'Reilly URL → extract ISBN + title from slug
 * - A plain ISBN (10 or 13 digits, optionally with dashes)
 *
 * Returns a minimal SearchBook or null.
 */
function parseDirectBookRef(query: string): SearchBook | null {
  const trimmed = query.trim();

  // O'Reilly URL: https://learning.oreilly.com/library/view/<slug>/<isbn>/...
  const urlMatch = trimmed.match(/learning\.oreilly\.com\/library\/view\/([^/]+)\/(\d{10,13})/);
  if (urlMatch) {
    const slug = urlMatch[1];
    const isbn = urlMatch[2];
    // Convert kebab-slug → Proper Title (capitalize every word)
    const title = slug
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
    return {
      id: isbn,
      title,
      cover_url: `https://learning.oreilly.com/library/cover/${isbn}/`,
    };
  }

  // Plain ISBN: 10 or 13 digits, optional dashes
  const isbnClean = trimmed.replace(/-/g, '');
  if (/^\d{10}$/.test(isbnClean) || /^\d{13}$/.test(isbnClean)) {
    return {
      id: isbnClean,
      title: `ISBN ${isbnClean}`,
      cover_url: `https://learning.oreilly.com/library/cover/${isbnClean}/`,
    };
  }

  return null;
}

const RECENT_SEARCHES_KEY = 'ryliox-recent-searches';
const MAX_RECENT_SEARCHES = 5;
const SEARCH_SCOPES = new Set<SearchScope>(['all', 'title', 'author', 'publisher']);

function getRecentSearches(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || '[]');
    return Array.isArray(value) ? value.filter(item => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string): string[] {
  const trimmed = query.trim();
  if (!trimmed) return getRecentSearches();
  const recent = getRecentSearches().filter(s => s !== trimmed);
  recent.unshift(trimmed);
  const next = recent.slice(0, MAX_RECENT_SEARCHES);
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next));
  return next;
}

function getInitialSearchState(): { query: string; scope: SearchScope } {
  if (typeof window === 'undefined') {
    return { query: '', scope: 'all' };
  }
  const params = new URLSearchParams(window.location.search);
  const rawScope = (params.get('scope') || 'all').toLowerCase() as SearchScope;
  return {
    query: (params.get('q') || '').trim(),
    scope: SEARCH_SCOPES.has(rawScope) ? rawScope : 'all',
  };
}

export function SearchBooksCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [initialSearch] = useState(getInitialSearchState);
  const idPrefix = useId().replace(/:/g, '');
  const resultsListId = `${idPrefix}-search-results`;
  const recentListId = `${idPrefix}-recent-searches`;
  const selectedBookId = useBookStore(state => state.selectedBook?.id ?? null);
  const setSelectedBook = useBookStore(state => state.setSelectedBook);
  const [queryInput, setQueryInput] = useState(initialSearch.query);
  const [scope, setScope] = useState<SearchScope>(initialSearch.scope);
  const [activeResultIndex, setActiveResultIndex] = useState(0);
  const [activeRecentIndex, setActiveRecentIndex] = useState(0);
  const [showRecent, setShowRecent] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>(getRecentSearches);
  const resultsListRef = useRef<HTMLUListElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  const normalizedQuery = queryInput.trim();
  const debouncedQuery = useDebouncedValue(normalizedQuery, SEARCH_DEBOUNCE_MS);
  const searchQueryTerm = getFreshCachedSearchQuery(normalizedQuery, queryClient) ?? debouncedQuery;

  // Keyboard shortcut to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Close recent searches dropdown on outside click
  useEffect(() => {
    if (!showRecent) return;
    const handler = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowRecent(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showRecent]);

  const searchScopes = useMemo(
    () => [
      {
        value: 'all' as const,
        label: t('search.scopes.all'),
        icon: Search,
      },
      {
        value: 'title' as const,
        label: t('search.scopes.title'),
        icon: Type,
      },
      {
        value: 'author' as const,
        label: t('search.scopes.author'),
        icon: PenLine,
      },
      {
        value: 'publisher' as const,
        label: t('search.scopes.publisher'),
        icon: Building2,
      },
    ],
    [t]
  );

  const searchQuery = useQuery({
    queryKey: queryKeys.search.byQuery(searchQueryTerm),
    queryFn: () => searchBooks(searchQueryTerm),
    enabled: searchQueryTerm.length > 0,
    placeholderData: previousData => previousData,
    staleTime: SEARCH_STALE_TIME_MS,
  });

  const prefetchBookData = async (bookId: string) => {
    if (!bookId) return;

    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: queryKeys.chapters.byBook(bookId),
        queryFn: () => getBookChapters(bookId),
        staleTime: PREFETCH_STALE_TIME_MS,
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.formats.all,
        queryFn: getFormats,
        staleTime: PREFETCH_STALE_TIME_MS,
      }),
    ]);
  };

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    if (searchQueryTerm) {
      params.set('q', searchQueryTerm);
    } else {
      params.delete('q');
    }

    if (scope === 'all') {
      params.delete('scope');
    } else {
      params.set('scope', scope);
    }

    params.delete('cover');

    const search = params.toString();
    const currentSearch = window.location.search.startsWith('?')
      ? window.location.search.slice(1)
      : window.location.search;
    if (search === currentSearch) {
      return;
    }

    const nextUrl = `${window.location.pathname}${search ? `?${search}` : ''}`;
    window.history.replaceState(null, '', nextUrl);
  }, [searchQueryTerm, scope]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      const query = (params.get('q') || '').trim();
      const rawScope = (params.get('scope') || 'all').toLowerCase();
      const newScope = SEARCH_SCOPES.has(rawScope as SearchScope)
        ? (rawScope as SearchScope)
        : 'all';
      setQueryInput(query);
      setScope(newScope);
    };

    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // Detect direct ISBN / O'Reilly URL in the query
  const directRef = useMemo(() => parseDirectBookRef(normalizedQuery), [normalizedQuery]);

  // When a direct ref is detected, fetch real book metadata from /api/book/{id}
  const bookInfoQuery = useQuery({
    queryKey: queryKeys.bookInfo.byId(directRef?.id ?? null),
    queryFn: () => getBookInfo(directRef!.id),
    enabled: directRef !== null,
    staleTime: PREFETCH_STALE_TIME_MS,
    retry: false, // if the book doesn't exist, fail fast
  });

  const filteredResults = useMemo(() => {
    if (!normalizedQuery) {
      return [];
    }

    const value = normalizedQuery.toLowerCase();
    const results = searchQuery.data?.results || [];

    const filtered = results.filter(book => {
      const id = (book.id || '').toLowerCase();
      const title = (book.title || '').toLowerCase();
      const authors = (book.authors || []).join(' ').toLowerCase();
      const publishers = (book.publishers || []).join(' ').toLowerCase();

      if (scope === 'title') {
        return title.includes(value);
      }
      if (scope === 'author') {
        return authors.includes(value);
      }
      if (scope === 'publisher') {
        return publishers.includes(value);
      }
      // 'all' scope: also match by book ID (ISBN)
      return (
        id.includes(value) ||
        title.includes(value) ||
        authors.includes(value) ||
        publishers.includes(value)
      );
    });

    // If a direct ISBN/URL was detected and the API didn't return that book,
    // prepend the real book info (from /api/book/{id}) or a temporary placeholder.
    if (directRef && !filtered.some(b => b.id === directRef.id)) {
      const info = bookInfoQuery.data;
      const syntheticBook = info
        ? {
            id: info.id,
            title: info.title ?? directRef.title,
            authors: info.authors ?? [],
            publishers: info.publishers ?? [],
            cover_url: info.cover_url ?? directRef.cover_url,
          }
        : directRef; // show placeholder while loading
      return [syntheticBook, ...filtered];
    }
    return filtered;
  }, [normalizedQuery, scope, searchQuery.data?.results, directRef, bookInfoQuery.data]);

  const parsedError =
    searchQueryTerm && searchQuery.error ? parseApiError(searchQuery.error) : null;
  const isSearching = Boolean(normalizedQuery) && (searchQuery.isPending || searchQuery.isFetching);
  const visibleResults = filteredResults;
  const resultCount = filteredResults.length;
  const hasStaleResults =
    Boolean(normalizedQuery) && normalizedQuery !== searchQueryTerm && visibleResults.length > 0;

  const handleSelectBook = (book: SearchBook) => {
    setSelectedBook(book);
    setRecentSearches(saveRecentSearch(normalizedQuery));
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      setTimeout(() => {
        const el = document.getElementById('download-section');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 120);
    }
  };

  useEffect(() => {
    if (visibleResults.length === 0) {
      setActiveResultIndex(0);
      return;
    }
    setActiveResultIndex(current => Math.min(current, visibleResults.length - 1));
  }, [visibleResults.length]);

  useEffect(() => {
    if (!resultsListRef.current || visibleResults.length === 0) {
      return;
    }

    const activeItem = resultsListRef.current.querySelector<HTMLElement>(
      `[data-result-index="${activeResultIndex}"]`
    );
    activeItem?.scrollIntoView({ block: 'nearest' });
  }, [activeResultIndex, visibleResults.length]);

  const activeDescendant =
    showRecent && !normalizedQuery && recentSearches.length > 0
      ? `${recentListId}-option-${activeRecentIndex}`
      : visibleResults.length > 0
        ? `${resultsListId}-option-${activeResultIndex}`
        : undefined;

  return (
    <OptimizedFadeIn direction="up" delay={50}>
      <section
        id="search-section"
        className="premium-card flex min-w-0 scroll-mt-28 flex-col overflow-visible"
      >
        <div className="flex-shrink-0 p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <BookOpen className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
              </div>
              <h2 className="text-base font-semibold leading-tight text-foreground sm:text-lg">
                {t('search.title')}
              </h2>
            </div>
            {normalizedQuery && !isSearching && resultCount > 0 ? (
              <Badge variant="default" size="sm" className="font-mono">
                {t('search.results_count', { count: resultCount })}
              </Badge>
            ) : null}
          </div>

          <div ref={searchContainerRef} className="relative mb-3">
            <label htmlFor="search-query" className="sr-only">
              {t('search.title')}
            </label>
            <div className="relative flex min-w-0 items-center">
              <Search
                className="pointer-events-none absolute left-3.5 h-4 w-4 text-muted-foreground"
                strokeWidth={2}
                aria-hidden="true"
              />
              <input
                id="search-query"
                ref={searchInputRef}
                value={queryInput}
                onChange={event => setQueryInput(event.target.value)}
                onFocus={() => {
                  setRecentSearches(getRecentSearches());
                  setActiveRecentIndex(0);
                  setShowRecent(true);
                }}
                onKeyDown={event => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    searchInputRef.current?.blur();
                    setShowRecent(false);
                  }

                  if (showRecent && !normalizedQuery && recentSearches.length > 0) {
                    if (event.key === 'ArrowDown') {
                      event.preventDefault();
                      setActiveRecentIndex(current =>
                        Math.min(current + 1, recentSearches.length - 1)
                      );
                    } else if (event.key === 'ArrowUp') {
                      event.preventDefault();
                      setActiveRecentIndex(current => Math.max(current - 1, 0));
                    } else if (event.key === 'Enter') {
                      event.preventDefault();
                      setQueryInput(recentSearches[activeRecentIndex] ?? '');
                      setShowRecent(false);
                    }
                    return;
                  }

                  if (visibleResults.length === 0) {
                    return;
                  }

                  if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    setActiveResultIndex(current =>
                      Math.min(current + 1, visibleResults.length - 1)
                    );
                    return;
                  }

                  if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    setActiveResultIndex(current => Math.max(current - 1, 0));
                    return;
                  }

                  if (event.key === 'Enter') {
                    const activeBook = visibleResults[activeResultIndex];
                    if (!activeBook) {
                      return;
                    }
                    event.preventDefault();
                    handleSelectBook(activeBook);
                    return;
                  }
                }}
                placeholder={t('search.placeholder')}
                role="combobox"
                aria-activedescendant={activeDescendant}
                aria-autocomplete="list"
                aria-controls={
                  showRecent && !normalizedQuery && recentSearches.length > 0
                    ? recentListId
                    : resultsListId
                }
                aria-expanded={
                  (showRecent && !normalizedQuery && recentSearches.length > 0) ||
                  visibleResults.length > 0
                }
                aria-haspopup="listbox"
                className="mobile-full min-h-touch min-w-0 w-full rounded-xl border border-input bg-background/80 py-3 pl-10 pr-20 text-sm leading-tight text-foreground shadow-xs outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:bg-background focus:ring-2 focus:ring-primary/20 sm:py-2.5 sm:text-sm"
              />

              {/* Clear button inside input */}
              {queryInput ? (
                <button
                  type="button"
                  onClick={() => {
                    setQueryInput('');
                    setScope('all');
                    searchInputRef.current?.focus();
                  }}
                  className="absolute right-10 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={t('search.clear')}
                >
                  <X className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
                </button>
              ) : null}

              {/* Keyboard shortcut hint */}
              <div className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 sm:flex">
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground shadow-2xs">
                  {typeof window !== 'undefined' && window.navigator.platform.includes('Mac')
                    ? '⌘'
                    : 'Ctrl'}
                </kbd>
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground shadow-2xs">
                  K
                </kbd>
              </div>
            </div>

            {/* Recent searches dropdown */}
            {showRecent && recentSearches.length > 0 && !normalizedQuery ? (
              <div
                id={recentListId}
                role="listbox"
                aria-label={t('search.recent.title')}
                className="absolute z-50 mt-1 w-full overflow-hidden rounded-xl border border-border bg-card shadow-lg"
              >
                <div className="flex items-center justify-between border-b border-border px-3 py-2 bg-muted/40">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {t('search.recent.title')}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      localStorage.removeItem(RECENT_SEARCHES_KEY);
                      setRecentSearches([]);
                      setShowRecent(false);
                    }}
                    className="text-[10px] text-muted-foreground hover:text-foreground transition underline underline-offset-2"
                  >
                    {t('search.recent.clear')}
                  </button>
                </div>
                {recentSearches.map((search, i) => (
                  <div
                    key={`${search}-${i}`}
                    className="flex items-center justify-between px-3.5 py-1 hover:bg-accent group/item"
                  >
                    <button
                      type="button"
                      id={`${recentListId}-option-${i}`}
                      role="option"
                      aria-selected={i === activeRecentIndex}
                      className="flex flex-1 items-center gap-2.5 py-1.5 text-left text-xs font-medium text-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                      onClick={() => {
                        setQueryInput(search);
                        setShowRecent(false);
                      }}
                    >
                      <Clock
                        className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                        strokeWidth={1.75}
                        aria-hidden="true"
                      />
                      <span className="truncate">{search}</span>
                    </button>
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation();
                        const updated = recentSearches.filter((_, idx) => idx !== i);
                        localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
                        setRecentSearches(updated);
                      }}
                      className="opacity-0 group-hover/item:opacity-100 p-1 text-muted-foreground hover:text-foreground text-xs rounded transition"
                      title="Eliminar"
                      aria-label={`Eliminar ${search}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          {/* Direct O'Reilly Link / ISBN Detection Badge */}
          {directRef && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-3 flex items-center justify-between gap-2 rounded-xl border border-primary/30 bg-primary/5 p-2.5 text-xs text-primary"
            >
              <div className="flex items-center gap-2 min-w-0">
                <Zap className="h-4 w-4 shrink-0 fill-current" />
                <span className="font-medium truncate">
                  {directRef.title.startsWith('ISBN')
                    ? t('search.isbn_detected') || 'ISBN directo detectado'
                    : t('search.direct_url_detected') || "Enlace directo de O'Reilly detectado"}
                  : <span className="font-bold text-foreground font-mono">{directRef.id}</span>
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  const syntheticBook = bookInfoQuery.data
                    ? {
                        id: bookInfoQuery.data.id,
                        title: bookInfoQuery.data.title ?? directRef.title,
                        authors: bookInfoQuery.data.authors ?? [],
                        publishers: bookInfoQuery.data.publishers ?? [],
                        cover_url: bookInfoQuery.data.cover_url ?? directRef.cover_url,
                      }
                    : directRef;
                  handleSelectBook(syntheticBook);
                }}
                className="shrink-0 rounded-lg bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground transition hover:bg-primary/90 shadow-2xs"
              >
                {t('search.book.select')}
              </button>
            </motion.div>
          )}

          {/* Filter Scopes */}
          <fieldset className="mb-0">
            <legend className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t('search.filter_by')}
            </legend>
            <div
              className="flex flex-wrap gap-1.5"
              role="radiogroup"
              aria-label={t('search.filter_by')}
            >
              {searchScopes.map(item => {
                const checked = scope === item.value;
                const Icon = item.icon;
                return (
                  <label
                    key={item.value}
                    className={cn(
                      'min-h-touch cursor-pointer rounded-full border px-3 py-1.5 text-xs font-medium leading-tight transition-all flex items-center justify-center gap-1.5 select-none focus-within:ring-2 focus-within:ring-ring',
                      checked
                        ? 'border-primary/50 bg-primary text-primary-foreground shadow-xs font-semibold'
                        : 'border-border bg-card/60 text-muted-foreground hover:border-primary/30 hover:bg-accent hover:text-foreground'
                    )}
                  >
                    <input
                      type="radio"
                      name="search-scope"
                      value={item.value}
                      checked={checked}
                      onChange={() => setScope(item.value)}
                      className="sr-only"
                    />
                    <Icon
                      className="h-3.5 w-3.5"
                      strokeWidth={checked ? 2.5 : 1.75}
                      aria-hidden="true"
                    />
                    {item.label}
                  </label>
                );
              })}
            </div>
          </fieldset>
        </div>

        <div className="px-6 pb-6">
          {isSearching ? (
            <div className="mb-3 space-y-3">
              <div
                className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-xs font-medium text-primary"
                role="status"
                aria-live="polite"
              >
                <Loader2
                  className="h-3.5 w-3.5 animate-spin"
                  strokeWidth={2.5}
                  aria-hidden="true"
                />
                {hasStaleResults ? t('search.updating') : t('search.loading')}
              </div>
              <SearchResultsSkeleton count={3} />
            </div>
          ) : null}

          {parsedError ? (
            <div
              className="rounded-xl border border-destructive/30 bg-destructive/5 p-3.5 mb-3"
              role="alert"
              aria-live="assertive"
              aria-atomic="true"
            >
              <p className="text-xs font-semibold text-destructive">
                {parsedError.message}
                {parsedError.code ? ` (${parsedError.code})` : ''}
              </p>
              {parsedError.suggestion ? (
                <p className="mt-1 text-xs text-destructive/80">{parsedError.suggestion}</p>
              ) : null}
            </div>
          ) : null}

          {visibleResults.length > 0 ? (
            <p className="mb-2.5 text-xs text-muted-foreground" role="status" aria-live="polite">
              {t('search.navigation_hint')}
            </p>
          ) : null}

          <AnimatedLayoutGroup className="relative z-0">
            <div className="chapter-scroll max-h-[380px] overflow-y-auto overflow-x-hidden pr-1">
              <ul
                id={resultsListId}
                ref={resultsListRef}
                className={`m-0 list-none space-y-2 p-0 ${isSearching ? 'opacity-90' : ''}`}
                aria-busy={isSearching}
                role="listbox"
              >
                <StaggeredLayoutContainer>
                  {visibleResults.map((book, index) => {
                    const isSelected = selectedBookId === book.id;
                    const isActive = visibleResults[activeResultIndex]?.id === book.id;
                    return (
                      <StaggeredLayoutItem key={book.id} layoutId={`book-${book.id}`}>
                        <motion.button
                          type="button"
                          layout
                          onClick={() => {
                            handleSelectBook(book);
                          }}
                          onMouseEnter={() => {
                            setActiveResultIndex(index);
                            prefetchBookData(book.id).catch(() => {
                              // silent prefetch failure
                            });
                          }}
                          id={`${resultsListId}-option-${index}`}
                          data-result-index={index}
                          role="option"
                          aria-selected={isSelected || isActive}
                          className={cn(
                            'group min-h-touch w-full rounded-xl border p-2.5 sm:p-3 text-left transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring/40',
                            isSelected
                              ? 'border-primary/50 bg-primary/5 shadow-xs ring-1 ring-primary/20'
                              : isActive
                                ? 'border-primary/30 bg-accent/60'
                                : 'border-border bg-card hover:border-primary/40 hover:bg-accent/40'
                          )}
                          whileHover={{ scale: 1.008 }}
                          whileTap={{ scale: 0.99 }}
                          transition={{
                            type: 'spring',
                            stiffness: 400,
                            damping: 25,
                          }}
                        >
                          <div className="flex min-w-0 items-start justify-between gap-2 sm:gap-3">
                            <div className="flex min-w-0 gap-3 flex-1">
                              <motion.div layoutId={`cover-${book.id}`} className="shrink-0">
                                <BookCover
                                  src={book.cover_url}
                                  alt={book.title}
                                  size="md"
                                  aspectRatio="book"
                                  showPlaceholderText
                                  placeholderText={t('search.book.no_cover')}
                                  className="shadow-md rounded-md"
                                />
                              </motion.div>
                              <div className="min-w-0 flex-1">
                                <motion.p
                                  layoutId={`title-${book.id}`}
                                  className="line-clamp-2 text-sm font-semibold leading-snug text-foreground whitespace-normal"
                                >
                                  {book.title}
                                </motion.p>

                                {book.authors && book.authors.length > 0 && (
                                  <div className="mt-1 flex min-w-0 items-center gap-1.5">
                                    <User
                                      className="h-3 w-3 shrink-0 text-muted-foreground"
                                      strokeWidth={1.75}
                                      aria-hidden="true"
                                    />
                                    <p className="truncate text-xs text-muted-foreground font-medium">
                                      {book.authors.join(', ')}
                                    </p>
                                  </div>
                                )}

                                {book.publishers && book.publishers.length > 0 && (
                                  <div className="flex min-w-0 items-center gap-1.5 mt-0.5">
                                    <Building2
                                      className="h-3 w-3 shrink-0 text-muted-foreground/70"
                                      strokeWidth={1.75}
                                      aria-hidden="true"
                                    />
                                    <p className="truncate text-[11px] text-muted-foreground/80">
                                      {book.publishers.join(', ')}
                                    </p>
                                  </div>
                                )}

                                {book.id && (
                                  <div className="mt-1.5">
                                    <span
                                      role="button"
                                      tabIndex={-1}
                                      onClick={e => {
                                        e.stopPropagation();
                                        if (book.id) {
                                          navigator.clipboard.writeText(book.id);
                                          toast.success(`ISBN ${book.id} copiado`);
                                        }
                                      }}
                                      className="inline-block font-mono text-[10px] text-muted-foreground/60 bg-muted/60 hover:bg-muted hover:text-foreground px-1.5 py-0.5 rounded transition cursor-copy"
                                      title="Copiar ISBN"
                                    >
                                      ISBN: {book.id}
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                            <Badge
                              variant={isSelected ? 'default' : 'secondary'}
                              size="sm"
                              className={cn(
                                'shrink-0 transition-colors',
                                isSelected ? 'bg-primary text-primary-foreground font-semibold' : ''
                              )}
                            >
                              {isSelected ? (
                                <span className="flex items-center gap-1">
                                  <Check className="h-3 w-3 stroke-[3]" />
                                  {t('search.book.selected')}
                                </span>
                              ) : (
                                t('search.book.select')
                              )}
                            </Badge>
                          </div>
                        </motion.button>
                      </StaggeredLayoutItem>
                    );
                  })}
                </StaggeredLayoutContainer>
              </ul>
            </div>
          </AnimatedLayoutGroup>

          {/* Quick Suggested Topics chips when query is empty */}
          {!normalizedQuery ? (
            <div className="pt-2">
              <div className="mb-4">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mb-2.5">
                  <Compass className="h-3.5 w-3.5 text-primary" />
                  {t('search.suggested_topics') || 'Temas sugeridos'}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {SUGGESTED_TOPICS.map(topic => (
                    <button
                      key={topic}
                      type="button"
                      onClick={() => {
                        setQueryInput(topic);
                        searchInputRef.current?.focus();
                      }}
                      className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/5 hover:text-primary active:scale-95"
                    >
                      {topic}
                    </button>
                  ))}
                </div>
              </div>
              <EnhancedEmptyState type="search" variant="compact" className="py-6" />
            </div>
          ) : null}

          {searchQueryTerm && !isSearching && !parsedError && visibleResults.length === 0 ? (
            <EnhancedEmptyState
              type="generic"
              icon={Search}
              title={t('search.no_results_title', {
                defaultValue: 'No results found',
              })}
              description={t('search.no_results', { query: searchQueryTerm })}
              variant="compact"
              action={{
                label: t('search.clear'),
                onClick: () => {
                  setQueryInput('');
                  setScope('all');
                },
                variant: 'secondary',
              }}
            />
          ) : null}
        </div>
      </section>
    </OptimizedFadeIn>
  );
}
