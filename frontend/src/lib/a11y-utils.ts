/**
 * Accessibility utilities following WCAG 2.1 guidelines
 */

import { useEffect, useRef, useCallback, useState } from 'react';

// Focus trap hook for modals
export function useFocusTrap(isActive: boolean) {
  const containerRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isActive) {
      previousFocusRef.current = document.activeElement as HTMLElement;

      // Focus first focusable element
      const container = containerRef.current;
      if (container) {
        const focusableElements = container.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstElement = focusableElements[0];
        firstElement?.focus();
      }
    } else {
      // Restore previous focus
      previousFocusRef.current?.focus();
    }
  }, [isActive]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      // Handle Escape key to close modal
      if (event.key === 'Escape' && isActive) {
        event.preventDefault();
        // Close modal logic here - just prevent default for now
        return;
      }

      // Handle Tab key for focus trapping
      if (event.key !== 'Tab' || !containerRef.current) return;

      const focusableElements = containerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (event.shiftKey) {
        if (document.activeElement === firstElement) {
          event.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          event.preventDefault();
          firstElement?.focus();
        }
      }
    },
    [isActive]
  );

  return { containerRef, handleKeyDown };
}

// Reduced motion preference hook
export function useReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return prefersReducedMotion;
}

// High contrast preference hook
export function useHighContrast(): boolean {
  const [prefersHighContrast, setPrefersHighContrast] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-contrast: high)');
    setPrefersHighContrast(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setPrefersHighContrast(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return prefersHighContrast;
}

// Utility to get accessible button props
export function getAccessibleButtonProps(
  label: string,
  expanded?: boolean,
  pressed?: boolean
): React.ButtonHTMLAttributes<HTMLButtonElement> {
  return {
    'aria-label': label,
    'aria-expanded': expanded,
    'aria-pressed': pressed,
  };
}

// Utility for accessible form labels
export function getAccessibleLabelProps(
  id: string,
  label: string,
  required?: boolean,
  error?: string
): React.LabelHTMLAttributes<HTMLLabelElement> & React.HTMLAttributes<HTMLDivElement> {
  return {
    htmlFor: id,
    'aria-required': required,
    'aria-invalid': !!error,
    'aria-describedby': error ? `${id}-error` : undefined,
  };
}
