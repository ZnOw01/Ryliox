import { ApiError } from './api';
import i18n from '../i18n/config';

type ParsedApiError = {
  message: string;
  code?: string;
  details?: string;
  suggestion?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function formatDetails(details: Record<string, unknown> | undefined): string | undefined {
  if (!details) {
    return undefined;
  }

  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return String(details);
  }
}

function getUserFriendlyMessage(error: ApiError | Record<string, unknown>): string {
  const t = i18n.t;

  // Check for specific error codes
  const code =
    error instanceof ApiError
      ? error.code
      : typeof error.code === 'string'
        ? error.code
        : undefined;

  if (code === 'auth_required' || code === 'cookies_required') {
    return t('errors.cookies_required_description');
  }

  if (code === 'book_chapters_failed') {
    return t('errors.chapters_failed_description');
  }

  if (code === 'search_failed') {
    return t('search.error.generic');
  }

  if (code === 'internal_error') {
    return t('errors.unknown_description');
  }

  if (code === 'network_error' || code === 'timeout') {
    return t('errors.network_description');
  }

  if (code === 'service_unavailable') {
    return t('errors.service_unavailable_description');
  }

  // Return original message if no specific handling
  if (error instanceof ApiError) {
    return error.message;
  }

  return typeof error.error === 'string' ? error.error : t('errors.unknown_description');
}

function getSuggestion(error: ApiError | Record<string, unknown>): string | undefined {
  const t = i18n.t;
  const code =
    error instanceof ApiError
      ? error.code
      : typeof error.code === 'string'
        ? error.code
        : undefined;
  const details =
    error instanceof ApiError ? error.details : isRecord(error.details) ? error.details : undefined;

  if (code === 'auth_required' || code === 'cookies_required') {
    return t('errors.cookies_required_description');
  }

  if (code === 'book_chapters_failed') {
    return t('errors.chapters_failed_description');
  }

  if (code === 'network_error') {
    return t('errors.network_description');
  }

  // Check if suggestion is in details
  if (details && typeof details.suggestion === 'string') {
    return details.suggestion;
  }

  return undefined;
}

export function parseApiError(error: unknown): ParsedApiError {
  const t = i18n.t;

  if (error instanceof ApiError) {
    return {
      message: getUserFriendlyMessage(error),
      code: error.code,
      details: formatDetails(error.details),
      suggestion: getSuggestion(error),
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      suggestion: t('errors.retry'),
    };
  }

  if (isRecord(error)) {
    return {
      message: getUserFriendlyMessage(error),
      code: typeof error.code === 'string' ? error.code : undefined,
      details: formatDetails(isRecord(error.details) ? error.details : undefined),
      suggestion: getSuggestion(error),
    };
  }

  return {
    message: t('errors.unknown_description'),
    suggestion: t('errors.contact_support'),
  };
}
