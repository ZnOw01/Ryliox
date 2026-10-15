import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { searchBooks } from '../../lib/api';
import { queryKeys } from '../../lib/query-keys';
import type { SearchResponse } from '../../lib/types';
import { useBookStore } from '../../store/book-store';
import { SearchBooksCard } from '../SearchBooksCard';

vi.mock('../../lib/api', async importOriginal => {
  const actual = await importOriginal<typeof import('../../lib/api')>();
  return {
    ...actual,
    getBookChapters: vi.fn(),
    getBookInfo: vi.fn(),
    getFormats: vi.fn(),
    searchBooks: vi.fn(),
  };
});

const SEARCH_RESPONSE: SearchResponse = {
  results: [
    {
      id: '9781000000001',
      title: 'Python systems',
      authors: ['Ada Example'],
      publishers: ['Synthetic Press'],
    },
  ],
};
const SEARCH_QUERY = 'python';
const SEARCH_KEY = queryKeys.search.byQuery(SEARCH_QUERY);
const DEBOUNCE_MS = 350;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: Infinity,
        retry: false,
      },
    },
  });
}

function renderSearchCard(queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <SearchBooksCard />
    </QueryClientProvider>
  );
}

async function advanceTimersBy(milliseconds: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
}

describe('SearchBooksCard cached results', () => {
  beforeEach(() => {
    useBookStore.getState().reset();
    window.history.replaceState(null, '', '/');
    vi.mocked(searchBooks).mockReset().mockResolvedValue(SEARCH_RESPONSE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows a fresh cached result immediately without another request', () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(SEARCH_KEY, SEARCH_RESPONSE, { updatedAt: Date.now() });
    renderSearchCard(queryClient);

    fireEvent.change(screen.getByRole('combobox', { name: /buscar libros/i }), {
      target: { value: SEARCH_QUERY },
    });

    expect(screen.getByRole('option', { name: /python systems/i })).toBeInTheDocument();
    expect(searchBooks).not.toHaveBeenCalled();
    expect(window.location.search).toBe('?q=python');
    queryClient.clear();
  });

  it('debounces a new uncached query after a settled cache hit', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    queryClient.setQueryData(SEARCH_KEY, SEARCH_RESPONSE, { updatedAt: Date.now() });
    renderSearchCard(queryClient);

    const input = screen.getByRole('combobox', { name: /buscar libros/i });
    fireEvent.change(input, { target: { value: SEARCH_QUERY } });

    expect(screen.getByRole('option', { name: /python systems/i })).toBeInTheDocument();
    expect(window.location.search).toBe('?q=python');
    expect(searchBooks).not.toHaveBeenCalled();

    await advanceTimersBy(DEBOUNCE_MS);
    fireEvent.change(input, { target: { value: 'rust' } });

    expect(searchBooks).not.toHaveBeenCalled();
    expect(window.location.search).toBe('?q=python');

    await advanceTimersBy(DEBOUNCE_MS - 1);
    expect(searchBooks).not.toHaveBeenCalled();
    expect(window.location.search).toBe('?q=python');

    await advanceTimersBy(1);
    expect(searchBooks).toHaveBeenCalledTimes(1);
    expect(searchBooks).toHaveBeenCalledWith('rust');
    queryClient.clear();
  });

  it('keeps an uncached search debounced until 350 ms of inactivity', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    renderSearchCard(queryClient);

    fireEvent.change(screen.getByRole('combobox', { name: /buscar libros/i }), {
      target: { value: SEARCH_QUERY },
    });

    expect(searchBooks).not.toHaveBeenCalled();
    expect(screen.queryByRole('option', { name: /python systems/i })).not.toBeInTheDocument();

    await advanceTimersBy(DEBOUNCE_MS - 1);
    expect(searchBooks).not.toHaveBeenCalled();

    await advanceTimersBy(1);
    expect(searchBooks).toHaveBeenCalledTimes(1);
    expect(searchBooks).toHaveBeenCalledWith(SEARCH_QUERY);
    queryClient.clear();
  });

  it('does not bypass debounce for an invalidated cached query', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    queryClient.setQueryData(SEARCH_KEY, SEARCH_RESPONSE, { updatedAt: Date.now() });
    await queryClient.invalidateQueries({ queryKey: SEARCH_KEY, refetchType: 'none' });
    renderSearchCard(queryClient);

    fireEvent.change(screen.getByRole('combobox', { name: /buscar libros/i }), {
      target: { value: SEARCH_QUERY },
    });

    expect(searchBooks).not.toHaveBeenCalled();
    expect(screen.queryByRole('option', { name: /python systems/i })).not.toBeInTheDocument();
    await advanceTimersBy(DEBOUNCE_MS - 1);
    expect(searchBooks).not.toHaveBeenCalled();

    await advanceTimersBy(1);
    expect(searchBooks).toHaveBeenCalledTimes(1);
    expect(searchBooks).toHaveBeenCalledWith(SEARCH_QUERY);
    queryClient.clear();
  });

  it('does not bypass debounce for an expired cached query', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    queryClient.setQueryData(SEARCH_KEY, SEARCH_RESPONSE, {
      updatedAt: Date.now() - DEBOUNCE_MS - 30000,
    });
    renderSearchCard(queryClient);

    fireEvent.change(screen.getByRole('combobox', { name: /buscar libros/i }), {
      target: { value: SEARCH_QUERY },
    });

    expect(searchBooks).not.toHaveBeenCalled();
    expect(screen.queryByRole('option', { name: /python systems/i })).not.toBeInTheDocument();
    await advanceTimersBy(DEBOUNCE_MS - 1);
    expect(searchBooks).not.toHaveBeenCalled();

    await advanceTimersBy(1);
    expect(searchBooks).toHaveBeenCalledTimes(1);
    expect(searchBooks).toHaveBeenCalledWith(SEARCH_QUERY);
    queryClient.clear();
  });

  it('does not bypass debounce for cached data with an error state', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    queryClient.setQueryData(SEARCH_KEY, SEARCH_RESPONSE, { updatedAt: Date.now() });
    const refreshError = new Error('refresh failed');
    vi.mocked(searchBooks).mockRejectedValueOnce(refreshError);

    await expect(
      queryClient.fetchQuery({
        queryKey: SEARCH_KEY,
        queryFn: () => searchBooks(SEARCH_QUERY),
        staleTime: 0,
        retry: false,
      })
    ).rejects.toBe(refreshError);
    expect(queryClient.getQueryState(SEARCH_KEY)?.status).toBe('error');
    expect(queryClient.getQueryData(SEARCH_KEY)).toEqual(SEARCH_RESPONSE);

    renderSearchCard(queryClient);
    fireEvent.change(screen.getByRole('combobox', { name: /buscar libros/i }), {
      target: { value: SEARCH_QUERY },
    });

    expect(searchBooks).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('option', { name: /python systems/i })).not.toBeInTheDocument();
    await advanceTimersBy(DEBOUNCE_MS - 1);
    expect(searchBooks).toHaveBeenCalledTimes(1);

    await advanceTimersBy(1);
    expect(screen.getByRole('option', { name: /python systems/i })).toBeInTheDocument();
    expect(searchBooks).toHaveBeenCalledTimes(2);
    expect(searchBooks).toHaveBeenNthCalledWith(2, SEARCH_QUERY);
    queryClient.clear();
  });

  it('keeps an empty query disabled even if the empty key has cached data', async () => {
    vi.useFakeTimers();
    const queryClient = createQueryClient();
    queryClient.setQueryData(queryKeys.search.byQuery(''), SEARCH_RESPONSE, {
      updatedAt: Date.now(),
    });
    renderSearchCard(queryClient);

    await advanceTimersBy(DEBOUNCE_MS);

    expect(searchBooks).not.toHaveBeenCalled();
    expect(screen.queryByRole('option', { name: /python systems/i })).not.toBeInTheDocument();
    queryClient.clear();
  });
});
