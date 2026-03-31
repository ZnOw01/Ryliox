import type { SearchBook } from '../lib/types';

// Feature flags
export type FeatureFlag =
  | 'enable_new_ui'
  | 'enable_batch_downloads'
  | 'enable_advanced_search'
  | 'enable_pwa'
  | 'enable_dark_mode'
  | 'enable_keyboard_shortcuts'
  | 'enable_a11y_improvements'
  | 'enable_toast_notifications'
  | 'enable_i18n';

export interface FeatureFlagConfig {
  description: string;
  default: boolean;
  category: string;
  enabled: boolean;
}

export interface FeatureFlagsResponse {
  flags: Record<FeatureFlag, boolean>;
  config: Record<FeatureFlag, FeatureFlagConfig>;
}

// Search history
export interface SearchHistoryItem {
  query: string;
  timestamp: number;
  filters?: SearchFilters;
}

export interface SearchFilters {
  minPages?: number;
  maxPages?: number;
  hasCover?: boolean;
  publishers?: string[];
}

// Advanced search
export interface FuzzySearchResult {
  book: SearchBook;
  score: number;
}

// Toast notifications
export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
  dismissible?: boolean;
}

// Keyboard shortcuts
export interface KeyboardShortcut {
  key: string;
  description: string;
  action: () => void;
  ctrl?: boolean;
  alt?: boolean;
  shift?: boolean;
}

// Theme
export type Theme = 'light' | 'dark' | 'system';

// A11y
export type A11yPriority = 'polite' | 'assertive';

export interface Announcement {
  message: string;
  priority: A11yPriority;
}

// I18n
export type Language = 'es' | 'en';
