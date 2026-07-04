import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import {
  MagnifyingGlass,
  X,
  BookOpen,
  User,
  Buildings,
  Spinner,
  Clock,
  TextAa,
  PencilSimple,
  Buildings as BuildingsIcon,
} from '@phosphor-icons/react';

import { parseApiError } from '../lib/api-error';
import { getBookChapters, getBookInfo, getFormats, searchBooks } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import type { SearchBook } from '../lib/types';
import { useDebouncedValue } from '../lib/use-debounced-value';
import { useBookStore } from '../store/book-store';
import { cn } from '../lib/cn';
import { Badge } from './ui/Badge';
import { EnhancedEmptyState } from './ui/EnhancedEmptyState';
import { BookCover, BookCoverSkeleton } from './ui/BookCover';
import {
  AnimatedLayoutGroup,
  StaggeredLayoutContainer,
  StaggeredLayoutItem,
} from './motion/LayoutAnimations';
import { OptimizedFadeIn } from './motion/OptimizedAppear';

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
          transition={{ delay: i * 0.1, duration: 0.3 }}
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

function getRecentSearches(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string) {
  const trimmed = query.trim();
  if (!trimmed) return;
  const recent = getRecentSearches().filter(s => s !== trimmed);
  recent.unshift(trimmed);
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent.slice(0, MAX_RECENT_SEARCHES)));
}

export function SearchBooksCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const selectedBookId = useBookStore(state => state.selectedBook?.id ?? null);
  const setSelectedBook = useBookStore(state => state.setSelectedBook);
  const [queryInput, setQueryInput] = useState('');
  const [scope, setScope] = useState<SearchScope>('all');
  const [activeResultIndex, setActiveResultIndex] = useState(0);
  const [showRecent, setShowRecent] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>(getRecentSearches);
  const resultsListRef = useRef<HTMLUListElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const recentRef = useRef<HTMLDivElement | null>(null);
  const [coverSize, setCoverSize] = useState<'sm' | 'md'>('md');

  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 640) {
      setCoverSize('sm');
    }
  }, []);

  const normalizedQuery = queryInput.trim();
  const debouncedQuery = useDebouncedValue(normalizedQuery, SEARCH_DEBOUNCE_MS);

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
      if (recentRef.current && !recentRef.current.contains(e.target as Node)) {
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
        icon: MagnifyingGlass,
      },
      {
        value: 'title' as const,
        label: t('search.scopes.title'),
        icon: TextAa,
      },
      {
        value: 'author' as const,
        label: t('search.scopes.author'),
        icon: PencilSimple,
      },
      {
        value: 'publisher' as const,
        label: t('search.scopes.publisher'),
        icon: BuildingsIcon,
      },
    ],
    [t]
  );

  const searchQuery = useQuery({
    queryKey: queryKeys.search.byQuery(debouncedQuery),
    queryFn: () => searchBooks(debouncedQuery),
    enabled: debouncedQuery.length > 0,
    placeholderData: previousData => previousData,
    staleTime: SEARCH_STALE_TIME_MS,
  });

  const prefetchBookData = async (bookId: string) => {
    if (!bookId) return;

    await queryClient.prefetchQuery({
      queryKey: queryKeys.chapters.byBook(bookId),
      queryFn: () => getBookChapters(bookId),
      staleTime: PREFETCH_STALE_TIME_MS,
    });

    await queryClient.prefetchQuery({
      queryKey: queryKeys.formats.all,
      queryFn: getFormats,
      staleTime: PREFETCH_STALE_TIME_MS,
    });
  };

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    if (debouncedQuery) {
      params.set('q', debouncedQuery);
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
  }, [debouncedQuery, scope]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      const query = (params.get('q') || '').trim();
      const rawScope = (params.get('scope') || 'all').toLowerCase();
      const newScope = searchScopes.some(item => item.value === rawScope)
        ? (rawScope as SearchScope)
        : 'all';
      setQueryInput(query);
      setScope(newScope);
    };

    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [searchScopes]);

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

  const parsedError = debouncedQuery && searchQuery.error ? parseApiError(searchQuery.error) : null;
  const isSearching = Boolean(normalizedQuery) && (searchQuery.isPending || searchQuery.isFetching);
  const visibleResults = filteredResults;
  const resultCount = filteredResults.length;
  const hasStaleResults =
    Boolean(normalizedQuery) && normalizedQuery !== debouncedQuery && visibleResults.length > 0;

  const handleSelectBook = (book: SearchBook) => {
    setSelectedBook(book);
    saveRecentSearch(normalizedQuery);
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
    visibleResults.length > 0
      ? `search-result-${visibleResults[activeResultIndex]?.id ?? activeResultIndex}`
      : undefined;

  return (
    <OptimizedFadeIn direction="up" delay={50}>
      <section
        id="search-section"
        className="premium-card flex min-w-0 scroll-mt-28 flex-col overflow-visible"
      >
        <div className="flex-shrink-0 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-primary" weight="regular" aria-hidden="true" />
              <h2 className="text-base font-semibold leading-tight text-foreground sm:text-lg">
                {t('search.title')}
              </h2>
            </div>
            {normalizedQuery && !isSearching && resultCount > 0 ? (
              <Badge variant="default" size="sm">
                {t('search.results_count', { count: resultCount })}
              </Badge>
            ) : null}
          </div>

          <div className="mb-4">
            <label htmlFor="search-query" className="sr-only">
              {t('search.title')}
            </label>
            <div className="relative flex min-w-0 items-center">
              <MagnifyingGlass
                className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground"
                weight="regular"
                aria-hidden="true"
              />
              <input
                id="search-query"
                ref={searchInputRef}
                value={queryInput}
                onChange={event => setQueryInput(event.target.value)}
                onFocus={() => setShowRecent(true)}
                onKeyDown={event => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    searchInputRef.current?.blur();
                    setShowRecent(false);
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
                aria-activedescendant={activeDescendant}
                aria-autocomplete="list"
                aria-controls="search-results"
                aria-expanded={visibleResults.length > 0}
                className="mobile-full min-h-touch min-w-0 w-full rounded-lg border border-input bg-background py-3 pl-10 pr-20 text-base leading-tight text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/70 focus:ring-2 focus:ring-primary/25 sm:py-2 sm:text-sm"
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
                  <X className="h-3.5 w-3.5" weight="regular" aria-hidden="true" />
                </button>
              ) : null}

              {/* Keyboard shortcut hint */}
              <div className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 sm:flex">
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground shadow-sm">
                  {typeof window !== 'undefined' && window.navigator.platform.includes('Mac')
                    ? '⌘'
                    : 'Ctrl'}
                </kbd>
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground shadow-sm">
                  K
                </kbd>
              </div>
            </div>

            {/* Recent searches dropdown */}
            {showRecent && recentSearches.length > 0 && !normalizedQuery ? (
              <div
                ref={recentRef}
                className="absolute z-50 mt-1 w-full overflow-hidden rounded-xl border border-border bg-card shadow-lg"
                style={{ width: 'calc(100% - 2rem)' }}
              >
                <div className="flex items-center justify-between border-b border-border px-3 py-2">
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Recientes
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      localStorage.removeItem(RECENT_SEARCHES_KEY);
                      setRecentSearches([]);
                      setShowRecent(false);
                    }}
                    className="text-[10px] text-muted-foreground hover:text-foreground transition"
                  >
                    Limpiar
                  </button>
                </div>
                {recentSearches.map((search, i) => (
                  <button
                    key={`${search}-${i}`}
                    type="button"
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                    onClick={() => {
                      setQueryInput(search);
                      setShowRecent(false);
                    }}
                  >
                    <Clock
                      className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                      weight="regular"
                      aria-hidden="true"
                    />
                    <span className="truncate">{search}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <fieldset className="mb-0">
            <legend className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t('search.filter_by')}
            </legend>
            <div
              className="flex flex-wrap gap-2"
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
                      'min-h-touch cursor-pointer rounded-full border px-3 py-2 text-xs font-medium leading-tight transition focus-within:outline-none focus-within:ring-2 focus-within:ring-ring/50 flex items-center justify-center gap-1.5',
                      checked
                        ? 'border-foreground/10 bg-foreground text-background shadow-sm'
                        : 'border-border bg-background text-muted-foreground hover:border-foreground/10 hover:bg-accent hover:text-accent-foreground'
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
                    <Icon className="h-3.5 w-3.5" weight="regular" aria-hidden="true" />
                    {item.label}
                  </label>
                );
              })}
            </div>
          </fieldset>
        </div>

        <div className="px-4 pb-4 sm:px-5 sm:pb-5">
          {isSearching ? (
            <div className="mb-3 space-y-3">
              <div
                className="flex items-center gap-2 rounded-lg border border-primary/30 bg-accent px-3 py-2 text-sm text-accent-foreground"
                role="status"
                aria-live="polite"
              >
                <Spinner className="h-4 w-4 animate-spin" weight="regular" aria-hidden="true" />
                {hasStaleResults ? t('search.updating') : t('search.loading')}
              </div>
              <SearchResultsSkeleton count={3} />
            </div>
          ) : null}
          {parsedError ? (
            <div
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-3"
              role="alert"
              aria-live="assertive"
              aria-atomic="true"
            >
              <p className="text-sm font-medium text-destructive-foreground">
                {parsedError.message}
                {parsedError.code ? ` (${parsedError.code})` : ''}
              </p>
              {parsedError.suggestion ? (
                <p className="mt-1 text-xs text-destructive-foreground/80">
                  {parsedError.suggestion}
                </p>
              ) : null}
            </div>
          ) : null}
          {visibleResults.length > 0 ? (
            <p className="mb-3 text-xs text-muted-foreground" role="status" aria-live="polite">
              {t('search.navigation_hint')}
            </p>
          ) : null}

          <AnimatedLayoutGroup className="relative z-0">
            <div className="chapter-scroll max-h-[360px] overflow-y-auto overflow-x-hidden pr-1">
              <ul
                id="search-results"
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
                            setActiveResultIndex(
                              visibleResults.findIndex(item => item.id === book.id)
                            );
                            prefetchBookData(book.id).catch(() => {
                              // silent prefetch failure
                            });
                          }}
                          aria-pressed={isSelected}
                          id={`search-result-${book.id}`}
                          data-result-index={visibleResults.findIndex(item => item.id === book.id)}
                          role="option"
                          aria-selected={isSelected || isActive}
                          className={cn(
                            'group min-h-touch w-full rounded-xl border p-2.5 sm:p-3 text-left transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring/40',
                            isSelected
                              ? 'border-primary/40 bg-accent shadow-panel-md ring-1 ring-primary/20'
                              : isActive
                                ? 'border-primary/30 bg-accent/50'
                                : 'border-border hover:border-primary/40 hover:bg-accent hover:shadow-sm'
                          )}
                          whileHover={{ scale: 1.01 }}
                          whileTap={{ scale: 0.99 }}
                          transition={{
                            type: 'spring',
                            stiffness: 400,
                            damping: 25,
                          }}
                        >
                          <div className="flex min-w-0 items-start justify-between gap-2 sm:gap-3">
                            <div className="flex min-w-0 gap-2 sm:gap-3">
                              <motion.div layoutId={`cover-${book.id}`} className="shrink-0">
                                <BookCover
                                  src={book.cover_url}
                                  alt={book.title}
                                  size={coverSize}
                                  aspectRatio="book"
                                  showPlaceholderText
                                  placeholderText={t('search.book.no_cover')}
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
                                      weight="regular"
                                      aria-hidden="true"
                                    />
                                    <p className="truncate text-xs text-muted-foreground">
                                      {book.authors.join(', ')}
                                    </p>
                                  </div>
                                )}

                                {book.publishers && book.publishers.length > 0 && (
                                  <div className="flex min-w-0 items-center gap-1.5">
                                    <Buildings
                                      className="h-3 w-3 shrink-0 text-muted-foreground"
                                      weight="regular"
                                      aria-hidden="true"
                                    />
                                    <p className="truncate text-xs text-muted-foreground/80">
                                      {book.publishers.join(', ')}
                                    </p>
                                  </div>
                                )}
                              </div>
                            </div>
                            <Badge
                              variant={isSelected ? 'default' : 'secondary'}
                              size="sm"
                              className={cn(
                                'shrink-0 transition-colors',
                                !isSelected &&
                                  'group-hover:border-primary/30 group-hover:bg-accent group-hover:text-accent-foreground'
                              )}
                            >
                              {isSelected ? t('search.book.selected') : t('search.book.select')}
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

          {!normalizedQuery ? (
            <EnhancedEmptyState type="search" variant="inspirational" className="py-12" />
          ) : null}
          {debouncedQuery && !isSearching && !parsedError && visibleResults.length === 0 ? (
            <EnhancedEmptyState
              type="generic"
              icon={MagnifyingGlass}
              title={t('search.no_results_title', {
                defaultValue: 'No results found',
              })}
              description={t('search.no_results', { query: debouncedQuery })}
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
