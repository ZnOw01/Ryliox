export const queryKeys = {
  authStatus: ["auth-status"] as const,
  apiHealth: ["api-health"] as const,
  storedCookies: ["stored-cookies"] as const,
  search: (query: string) => ["search", query] as const,
  formats: ["formats"] as const,
  bookChapters: (bookId: string | null) => ["book-chapters", bookId] as const,
  downloadProgressRoot: ["download-progress"] as const,
  downloadProgress: (jobId: string | null) => ["download-progress", jobId ?? "latest"] as const,
};
