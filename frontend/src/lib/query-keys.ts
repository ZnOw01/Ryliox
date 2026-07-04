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

  // Book Info (metadata by ID)
  bookInfo: {
    root: ['book-info'] as const,
    byId: (bookId: string | null) =>
      bookId ? ([...queryKeys.bookInfo.root, bookId] as const) : queryKeys.bookInfo.root,
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


} as const;

// Type-safe query key helpers
export type QueryKeys = typeof queryKeys;
