/**
 * Feature flags configuration for the frontend
 * Simple implementation - all features enabled by default
 */

const DEFAULT_FLAGS: Record<string, boolean> = {
  enable_i18n: true,
  enable_dark_mode: true,
  enable_pwa: true,
  enable_keyboard_shortcuts: true,
  enable_a11y_improvements: true,
  enable_toast_notifications: true,
  enable_advanced_search: true,
  enable_new_ui: false,
  enable_batch_downloads: false,
};

/**
 * Check if a feature flag is enabled
 */
export function isEnabled(flagName: string): boolean {
  // Check localStorage for user override
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem(`feature_${flagName}`);
      if (stored !== null) {
        return stored === 'true';
      }
    } catch {
      // Ignore localStorage errors
    }
  }

  return DEFAULT_FLAGS[flagName] ?? false;
}

/**
 * Set a feature flag value
 */
export function setFlag(flagName: string, enabled: boolean): void {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(`feature_${flagName}`, String(enabled));
    } catch {
      // Ignore localStorage errors
    }
  }
}

/**
 * Get all feature flags
 */
export function getAllFlags(): Record<string, boolean> {
  const result: Record<string, boolean> = {};

  for (const flag of Object.keys(DEFAULT_FLAGS)) {
    result[flag] = isEnabled(flag);
  }

  return result;
}
