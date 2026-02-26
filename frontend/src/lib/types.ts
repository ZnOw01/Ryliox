export type ApiErrorPayload = {
  error: string;
  code?: string;
  details?: Record<string, unknown>;
};

export type AuthStatus = {
  valid: boolean;
  reason?: string | null;
  has_cookies: boolean;
};

export type HealthResponse = {
  status: string;
  uptime_seconds: number;
  version: string;
};

export type CookiesResponse = {
  cookies: Record<string, string>;
};

export type SearchBook = {
  id: string;
  title: string;
  authors?: string[];
  cover_url?: string;
  publishers?: string[];
};

export type SearchResponse = {
  results: SearchBook[];
};

export type ChapterSummary = {
  index: number;
  title: string;
  pages?: number | null;
  minutes?: number | null;
};

export type BookChaptersResponse = {
  chapters: ChapterSummary[];
  total: number;
};

export type FormatsResponse = {
  formats: string[];
  aliases: Record<string, string>;
  book_only: string[];
  descriptions: Record<string, string>;
};

export type DownloadRequest = {
  book_id: string;
  format: string;
  chapters?: number[];
  output_dir?: string;
  skip_images?: boolean;
};

export type DownloadStartResponse = {
  status: string;
  book_id: string | null;
  job_id: string;
  queue_position?: number | null;
};

export type ProgressResponse = {
  job_id?: string | null;
  queue_position?: number | null;
  status?: string | null;
  book_id?: string | null;
  percentage?: number | null;
  message?: string | null;
  eta_seconds?: number | null;
  current_chapter?: number | null;
  total_chapters?: number | null;
  chapter_title?: string | null;
  title?: string | null;
  epub?: string | null;
  pdf?: string | string[] | null;
  error?: string | null;
  code?: string | null;
  details?: Record<string, unknown> | null;
  trace_log?: string | null;
};

export type CancelResponse = {
  success: boolean;
  message: string;
};

export type SaveCookiesResponse = {
  success: boolean;
};
