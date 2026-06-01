import type {
  ApiErrorPayload,
  AuthStatus,
  BookChaptersResponse,
  BookInfoResponse,
  CancelResponse,
  CookiesResponse,
  DownloadRequest,
  DownloadStartResponse,
  FormatsResponse,
  HealthResponse,
  ProgressResponse,
  RevealResponse,
  SaveCookiesResponse,
  SearchResponse,
} from './types';

const API_BASE = import.meta.env.PUBLIC_API_BASE ?? '';
const SSE_BASE = API_BASE || '';

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: Record<string, unknown>;

  constructor(payload: ApiErrorPayload, status: number) {
    super(payload.error);
    this.name = 'ApiError';
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseApiErrorPayload(data: unknown, status: number): ApiErrorPayload {
  if (!isRecord(data)) {
    return { error: `Request failed with status ${status}` };
  }

  const message =
    typeof data.error === 'string' ? data.error : `Request failed with status ${status}`;
  const code = typeof data.code === 'string' ? data.code : undefined;
  const details = isRecord(data.details) ? data.details : undefined;

  return { error: message, code, details };
}

async function parseResponseBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

async function request<T>(path: string, init?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
    signal: init?.signal,
  });

  const data = await parseResponseBody(response);
  const payload = isRecord(data) ? data : {};

  if (!response.ok) {
    throw new ApiError(parseApiErrorPayload(data, response.status), response.status);
  }

  return payload as T;
}

export function getStatus(): Promise<AuthStatus> {
  return request<AuthStatus>('/api/status', { method: 'GET' });
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health', { method: 'GET' });
}

export function saveCookies(payload: unknown): Promise<SaveCookiesResponse> {
  return request<SaveCookiesResponse>('/api/cookies', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getCookies(): Promise<CookiesResponse> {
  return request<CookiesResponse>('/api/cookies', { method: 'GET' });
}

export function searchBooks(query: string): Promise<SearchResponse> {
  const q = encodeURIComponent(query);
  return request<SearchResponse>(`/api/search?q=${q}`, { method: 'GET' });
}

export function getBookChapters(bookId: string): Promise<BookChaptersResponse> {
  return request<BookChaptersResponse>(`/api/book/${encodeURIComponent(bookId)}/chapters`, {
    method: 'GET',
  });
}

export function getBookInfo(bookId: string): Promise<BookInfoResponse> {
  return request<BookInfoResponse>(`/api/book/${encodeURIComponent(bookId)}`, {
    method: 'GET',
  });
}

export function getFormats(): Promise<FormatsResponse> {
  return request<FormatsResponse>('/api/formats', { method: 'GET' });
}

export function startDownload(payload: DownloadRequest, signal?: AbortSignal): Promise<DownloadStartResponse> {
  return request<DownloadStartResponse>('/api/download', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}

export function getProgress(jobId?: string | null, signal?: AbortSignal): Promise<ProgressResponse> {
  const suffix = jobId ? `?job_id=${encodeURIComponent(jobId)}` : '';
  return request<ProgressResponse>(`/api/progress${suffix}`, { method: 'GET', signal });
}

export function cancelDownload(jobId?: string | null, signal?: AbortSignal): Promise<CancelResponse> {
  return request<CancelResponse>('/api/cancel', {
    method: 'POST',
    body: JSON.stringify(jobId ? { job_id: jobId } : {}),
    signal,
  });
}

export function revealFile(path: string): Promise<RevealResponse> {
  return request<RevealResponse>('/api/reveal', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export function subscribeProgress(
  handlers: {
    onProgress: (payload: ProgressResponse) => void;
    onError?: (error: Event) => void;
    onOpen?: (event: Event) => void;
  },
  jobId?: string | null
): () => void {
  const suffix = jobId ? `?job_id=${encodeURIComponent(jobId)}` : '';
  const source = new EventSource(`${SSE_BASE}/api/progress/stream${suffix}`);
  const { onProgress, onError, onOpen } = handlers;

  source.addEventListener('progress', event => {
    const message = event as MessageEvent<string>;
    try {
      const payload = JSON.parse(message.data) as ProgressResponse;
      onProgress(payload);
    } catch {
      console.warn('Invalid progress payload received from SSE stream.');
      if (onError) {
        onError(new Event('error'));
      }
    }
  });

  if (onOpen) {
    source.addEventListener('open', onOpen);
  }

  if (onError) {
    source.addEventListener('error', onError);
  }

  return () => source.close();
}
