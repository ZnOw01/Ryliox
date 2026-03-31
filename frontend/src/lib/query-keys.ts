// Query Keys Factory Pattern para TanStack Query v5
// Sigue las mejores prácticas de estandarización de query keys

export const queryKeys = {
  // Auth & Status
  authStatus: ['auth-status'] as const,
  apiHealth: ['api-health'] as const,
  storedCookies: ['stored-cookies'] as const,

  // Search
  search: {
    root: ['search'] as const,
    byQuery: (query: string) => [...queryKeys.search.root, query] as const,
  },

  // Formats - datos estáticos, rara vez cambian
  formats: {
    root: ['formats'] as const,
    all: ['formats', 'all'] as const,
    byBook: (bookId: string) => ['formats', 'book', bookId] as const,
  },

  // Book Chapters
  chapters: {
    root: ['chapters'] as const,
    byBook: (bookId: string | null) =>
      bookId ? ([...queryKeys.chapters.root, bookId] as const) : queryKeys.chapters.root,
  },

  // Download Progress
  progress: {
    root: ['progress'] as const,
    all: ['progress', 'all'] as const,
    byJob: (jobId: string | null) =>
      jobId
        ? ([...queryKeys.progress.root, jobId] as const)
        : ([...queryKeys.progress.root, 'latest'] as const),
  },

  // Legacy aliases para compatibilidad gradual (deprecated)
  /** @deprecated Use queryKeys.search.byQuery() */
  searchLegacy: (query: string) => ['search', query] as const,
  /** @deprecated Use queryKeys.formats.all */
  formatsLegacy: ['formats'] as const,
  /** @deprecated Use queryKeys.chapters.byBook() */
  bookChaptersLegacy: (bookId: string | null) => ['book-chapters', bookId] as const,
  /** @deprecated Use queryKeys.progress.root */
  downloadProgressRoot: ['download-progress'] as const,
  /** @deprecated Use queryKeys.progress.byJob() */
  downloadProgressLegacy: (jobId: string | null) =>
    ['download-progress', jobId ?? 'latest'] as const,
} as const;

// Type-safe query key helpers
export type QueryKeys = typeof queryKeys;
