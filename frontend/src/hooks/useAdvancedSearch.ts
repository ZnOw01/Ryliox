import { useMemo, useCallback, useState, useEffect } from 'react';
import { useBookStore } from '../store/book-store';
import type { SearchBook } from '../lib/types';

// Simple fuzzy matching implementation
function fuzzyMatch(text: string, query: string): number {
  if (!query) return 1;
  if (!text) return 0;

  const textLower = text.toLowerCase();
  const queryLower = query.toLowerCase();

  // Exact match
  if (textLower === queryLower) return 1;

  // Contains query
  if (textLower.includes(queryLower)) return 0.9;

  // Fuzzy match - check if all characters appear in order
  let queryIndex = 0;
  let matches = 0;

  for (let i = 0; i < textLower.length && queryIndex < queryLower.length; i++) {
    if (textLower[i] === queryLower[queryIndex]) {
      matches++;
      queryIndex++;
    }
  }

  if (matches === queryLower.length) {
    return 0.7 + (matches / textLower.length) * 0.2;
  }

  return 0;
}

interface SearchFilters {
  minPages?: number;
  maxPages?: number;
  hasCover?: boolean;
  publishers?: string[];
}

interface UseAdvancedSearchOptions {
  query: string;
  books: SearchBook[];
  filters?: SearchFilters;
  threshold?: number;
  maxResults?: number;
}

export function useAdvancedSearch({
  query,
  books,
  filters,
  threshold = 0.3,
  maxResults = 50,
}: UseAdvancedSearchOptions) {
  const results = useMemo(() => {
    if (!query.trim()) {
      return books.slice(0, maxResults);
    }

    const scored = books.map(book => {
      let score = 0;

      // Title match (highest weight)
      const titleScore = fuzzyMatch(book.title, query);
      score += titleScore * 0.5;

      // Authors match
      const authorsText = book.authors?.join(' ') || '';
      const authorsScore = fuzzyMatch(authorsText, query);
      score += authorsScore * 0.3;

      // Publisher match
      const publisherText = book.publishers?.join(' ') || '';
      const publisherScore = fuzzyMatch(publisherText, query);
      score += publisherScore * 0.2;

      return { book, score };
    });

    // Filter by threshold and apply additional filters
    let filtered = scored.filter(item => item.score >= threshold);

    if (filters) {
      filtered = filtered.filter(({ book }) => {
        if (filters.hasCover !== undefined && filters.hasCover !== !!book.cover_url) {
          return false;
        }
        if (
          filters.publishers?.length &&
          !book.publishers?.some(p => filters.publishers?.includes(p))
        ) {
          return false;
        }
        return true;
      });
    }

    // Sort by score and limit results
    return filtered
      .sort((a, b) => b.score - a.score)
      .slice(0, maxResults)
      .map(item => item.book);
  }, [query, books, filters, threshold, maxResults]);

  return { results, count: results.length };
}

// Search history hook
const STORAGE_KEY = 'search-history';
const MAX_HISTORY_ITEMS = 20;

export interface SearchHistoryItem {
  query: string;
  timestamp: number;
  filters?: SearchFilters;
}

export function useSearchHistory() {
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setHistory(parsed);
      }
    } catch {
      // Ignore parse errors
    }
    setIsLoaded(true);
  }, []);

  // Save to localStorage when history changes
  useEffect(() => {
    if (isLoaded) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }
  }, [history, isLoaded]);

  const addToHistory = useCallback((query: string, filters?: SearchFilters) => {
    if (!query.trim()) return;

    setHistory(prev => {
      // Remove existing entry with same query
      const filtered = prev.filter(item => item.query.toLowerCase() !== query.toLowerCase());

      // Add new entry at the beginning
      const newItem: SearchHistoryItem = {
        query,
        timestamp: Date.now(),
        filters,
      };

      return [newItem, ...filtered].slice(0, MAX_HISTORY_ITEMS);
    });
  }, []);

  const removeFromHistory = useCallback((query: string) => {
    setHistory(prev => prev.filter(item => item.query !== query));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  const getRecentQueries = useCallback(
    (limit = 5) => {
      return history.slice(0, limit).map(item => item.query);
    },
    [history]
  );

  return {
    history,
    addToHistory,
    removeFromHistory,
    clearHistory,
    getRecentQueries,
    isLoaded,
  };
}

// Autocomplete hook
export function useAutocomplete(query: string, suggestions: string[], maxSuggestions = 5) {
  const matches = useMemo(() => {
    if (!query.trim()) return [];

    const queryLower = query.toLowerCase();
    return suggestions
      .filter(
        suggestion =>
          suggestion.toLowerCase().includes(queryLower) && suggestion.toLowerCase() !== queryLower
      )
      .slice(0, maxSuggestions);
  }, [query, suggestions, maxSuggestions]);

  return matches;
}
