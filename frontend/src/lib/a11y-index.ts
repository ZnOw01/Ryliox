/**
 * Accessibility Utilities - Barrel Export
 *
 * Enhanced accessibility utilities following WCAG 2.1 and Radix UI patterns.
 */

// Legacy hooks (keeping for compatibility)
export {
  getAccessibleButtonProps,
  getAccessibleLabelProps,
  useFocusTrap,
  useHighContrast,
  useReducedMotion,
} from './a11y-utils';

// New focus management utilities (Radix UI 2025-2026 patterns)
export {
  createAccessibleButtonProps,
  focusFirstInContainer,
  getFirstFocusableElement,
  getFocusableElements,
  getLastFocusableElement,
  isFocusable,
  setFocus,
  useFocusTrap as useAdvancedFocusTrap,
  useFocusVisible,
  useRovingTabIndex,
  useSkipLink,
} from './focus-management';
