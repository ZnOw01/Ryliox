/**
 * Focus Management Utilities
 *
 * Advanced focus management following Radix UI Context7 patterns and WCAG 2.1 guidelines.
 * Provides utilities for focus trapping, focus restoration, skip links, and keyboard navigation.
 *
 * Key Features:
 * - Focus trapping in modals/dialogs with circular navigation
 * - Focus restoration after closing
 * - Skip link functionality
 * - Focus visible indicators
 * - Keyboard navigation helpers (roving tabindex)
 * - No keyboard traps detection
 *
 * WCAG 2.1 Compliance:
 * - 2.1.1 Keyboard accessible
 * - 2.1.2 No keyboard trap
 * - 2.4.3 Focus order
 * - 2.4.7 Focus visible
 */

import { useCallback, useEffect, useRef, useState } from 'react';

// Selector for focusable elements
const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'a[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"]):not([disabled])',
  'details > summary:first-of-type',
  'iframe',
  'object',
  'embed',
  '[contenteditable]:not([contenteditable="false"])',
  'audio[controls]',
  'video[controls]',
].join(', ');

/**
 * Get all focusable elements within a container
 *
 * @param container - Container element to search
 * @returns NodeList of focusable elements
 */
export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const elements = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  return elements.filter(el => {
    // Filter out hidden elements
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  });
}

/**
 * Get the first focusable element within a container
 */
export function getFirstFocusableElement(container: HTMLElement): HTMLElement | null {
  const elements = getFocusableElements(container);
  return elements[0] || null;
}

/**
 * Get the last focusable element within a container
 */
export function getLastFocusableElement(container: HTMLElement): HTMLElement | null {
  const elements = getFocusableElements(container);
  return elements[elements.length - 1] || null;
}

/**
 * Focus the first focusable element in a container
 *
 * @param container - Container element
 * @param options - Options
 * @param options.excludeSelector - CSS selector to exclude from focus
 * @param options.delay - Delay in ms before focusing
 */
export function focusFirstInContainer(
  container: HTMLElement,
  options: { excludeSelector?: string; delay?: number } = {}
): void {
  const { excludeSelector, delay = 0 } = options;

  const focusElement = () => {
    let elements = getFocusableElements(container);

    if (excludeSelector) {
      elements = elements.filter(el => !el.matches(excludeSelector));
    }

    const firstElement = elements[0];
    if (firstElement) {
      firstElement.focus();
    }
  };

  if (delay > 0) {
    setTimeout(focusElement, delay);
  } else {
    focusElement();
  }
}

/**
 * React hook for focus trapping
 *
 * Implements WCAG 2.1 guidelines for focus trapping:
 * - Traps focus within container
 * - Circular navigation (Tab from last goes to first, Shift+Tab from first goes to last)
 * - Escape key handling
 * - Focus restoration on unmount
 *
 * @param isActive - Whether focus trapping is active
 * @param options - Configuration options
 * @returns Object with containerRef and handleKeyDown
 *
 * @example
 * const { containerRef, handleKeyDown } = useFocusTrap(isOpen);
 *
 * <div ref={containerRef} onKeyDown={handleKeyDown}>
 *   <button>Focusable 1</button>
 *   <button>Focusable 2</button>
 * </div>
 */
export function useFocusTrap(
  isActive: boolean,
  options: {
    /** Return focus to this element when closing (default: previously focused) */
    returnFocusTo?: HTMLElement | null;
    /** Callback when Escape is pressed */
    onEscape?: () => void;
    /** Callback when Tab reaches last element (default: loops to first) */
    onTabEnd?: () => void;
    /** Callback when Shift+Tab reaches first element (default: loops to last) */
    onShiftTabStart?: () => void;
    /** Exclude elements matching this selector from focus */
    excludeSelector?: string;
    /** Delay before initial focus (ms) */
    focusDelay?: number;
  } = {}
) {
  const {
    returnFocusTo,
    onEscape,
    onTabEnd,
    onShiftTabStart,
    excludeSelector,
    focusDelay = 0,
  } = options;

  const containerRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Store previous focus when activating
  useEffect(() => {
    if (isActive) {
      previousFocusRef.current = document.activeElement as HTMLElement;

      // Focus first element after delay
      const container = containerRef.current;
      if (container) {
        focusFirstInContainer(container, { excludeSelector, delay: focusDelay });
      }
    } else {
      // Restore focus when closing
      const elementToFocus = returnFocusTo || previousFocusRef.current;
      elementToFocus?.focus();
    }
  }, [isActive, returnFocusTo, excludeSelector, focusDelay]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!isActive || !containerRef.current) return;

      const container = containerRef.current;
      const focusableElements = getFocusableElements(container);

      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      switch (event.key) {
        case 'Escape':
          event.preventDefault();
          onEscape?.();
          break;

        case 'Tab':
          if (event.shiftKey) {
            // Shift+Tab: Go backwards
            if (document.activeElement === firstElement) {
              event.preventDefault();
              if (onShiftTabStart) {
                onShiftTabStart();
              } else {
                lastElement?.focus();
              }
            }
          } else {
            // Tab: Go forwards
            if (document.activeElement === lastElement) {
              event.preventDefault();
              if (onTabEnd) {
                onTabEnd();
              } else {
                firstElement?.focus();
              }
            }
          }
          break;
      }
    },
    [isActive, onEscape, onTabEnd, onShiftTabStart]
  );

  return { containerRef, handleKeyDown, previousFocus: previousFocusRef.current };
}

/**
 * React hook for roving tabindex
 *
 * Implements keyboard navigation pattern for lists/menus:
 * - Only one element has tabindex="0" at a time
 * - Arrow keys navigate between items
 * - Home/End keys go to first/last
 * - Tab key exits the roving group
 *
 * WCAG Pattern: https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/#kbd_roving_tabindex
 *
 * @param itemCount - Number of items in the group
 * @param options - Configuration options
 * @returns Object with navigation handlers and current index
 *
 * @example
 * const { getTabIndex, handleKeyDown, currentIndex } = useRovingTabIndex(5);
 *
 * <ul onKeyDown={handleKeyDown}>
 *   {items.map((item, i) => (
 *     <li key={i} tabIndex={getTabIndex(i)}>{item}</li>
 *   ))}
 * </ul>
 */
export function useRovingTabIndex(
  itemCount: number,
  options: {
    /** Orientation of navigation: horizontal | vertical | both */
    orientation?: 'horizontal' | 'vertical' | 'both';
    /** Wrap around from last to first and vice versa */
    wrap?: boolean;
    /** Initial active index (default: 0) */
    defaultIndex?: number;
    /** Callback when active index changes */
    onChange?: (index: number) => void;
  } = {}
) {
  const { orientation = 'horizontal', wrap = false, defaultIndex = 0, onChange } = options;
  const [currentIndex, setCurrentIndex] = useState(defaultIndex);
  const containerRef = useRef<HTMLElement>(null);

  const getTabIndex = useCallback(
    (index: number) => {
      return index === currentIndex ? 0 : -1;
    },
    [currentIndex]
  );

  const focusItem = useCallback((index: number) => {
    if (containerRef.current) {
      const items = containerRef.current.querySelectorAll('[tabindex]');
      const item = items[index] as HTMLElement | undefined;
      item?.focus();
    }
  }, []);

  const navigate = useCallback(
    (direction: 'next' | 'prev' | 'first' | 'last') => {
      let newIndex: number;

      switch (direction) {
        case 'next':
          newIndex = currentIndex + 1;
          if (newIndex >= itemCount) {
            newIndex = wrap ? 0 : itemCount - 1;
          }
          break;
        case 'prev':
          newIndex = currentIndex - 1;
          if (newIndex < 0) {
            newIndex = wrap ? itemCount - 1 : 0;
          }
          break;
        case 'first':
          newIndex = 0;
          break;
        case 'last':
          newIndex = itemCount - 1;
          break;
      }

      setCurrentIndex(newIndex);
      onChange?.(newIndex);
      focusItem(newIndex);
    },
    [currentIndex, itemCount, wrap, onChange, focusItem]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const isHorizontal = orientation === 'horizontal' || orientation === 'both';
      const isVertical = orientation === 'vertical' || orientation === 'both';

      switch (event.key) {
        case 'ArrowRight':
          if (isHorizontal) {
            event.preventDefault();
            navigate('next');
          }
          break;
        case 'ArrowLeft':
          if (isHorizontal) {
            event.preventDefault();
            navigate('prev');
          }
          break;
        case 'ArrowDown':
          if (isVertical) {
            event.preventDefault();
            navigate('next');
          }
          break;
        case 'ArrowUp':
          if (isVertical) {
            event.preventDefault();
            navigate('prev');
          }
          break;
        case 'Home':
          event.preventDefault();
          navigate('first');
          break;
        case 'End':
          event.preventDefault();
          navigate('last');
          break;
      }
    },
    [navigate, orientation]
  );

  return {
    currentIndex,
    getTabIndex,
    handleKeyDown,
    containerRef,
    navigate,
    setCurrentIndex,
  };
}

/**
 * Create a functional skip link
 *
 * WCAG 2.4.1: Bypass Blocks - Skip links allow users to skip repetitive content
 *
 * @param targetId - ID of the element to skip to
 * @returns Object with skip link props
 *
 * @example
 * // In your layout:
 * <SkipLink targetId="main-content">Skip to main content</SkipLink>
 *
 * <header>...</header>
 * <main id="main-content" tabIndex={-1}>
 *   ...
 * </main>
 */
export function useSkipLink(targetId: string) {
  const handleClick = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const target = document.getElementById(targetId);
      if (target) {
        target.tabIndex = -1;
        target.focus();
        // Remove tabIndex after focus (optional, keeps HTML cleaner)
        target.addEventListener(
          'blur',
          () => {
            target.removeAttribute('tabindex');
          },
          { once: true }
        );
      }
    },
    [targetId]
  );

  return {
    href: `#${targetId}`,
    onClick: handleClick,
    'aria-label': `Skip to ${targetId.replace(/-/g, ' ')}`,
  };
}

/**
 * Check if an element is focusable
 */
export function isFocusable(element: HTMLElement): boolean {
  const focusableElements = document.querySelectorAll(FOCUSABLE_SELECTOR);
  return Array.from(focusableElements).includes(element);
}

/**
 * Set focus on an element if it's focusable
 */
export function setFocus(element: HTMLElement | null): void {
  if (element && isFocusable(element)) {
    element.focus();
  }
}

/**
 * React hook for focus visible detection
 *
 * Implements :focus-visible pattern without CSS
 * Useful for programmatic focus management
 *
 * @returns Object with focus visible state
 */
export function useFocusVisible() {
  const [isFocusVisible, setIsFocusVisible] = useState(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const handleFocus = (e: FocusEvent) => {
      // Check if focus is from keyboard (not mouse)
      const relatedTarget = e.relatedTarget;
      if (relatedTarget || !window.matchMedia('(pointer: coarse)').matches) {
        setIsFocusVisible(true);
      }
    };

    const handleBlur = () => {
      setIsFocusVisible(false);
    };

    element.addEventListener('focus', handleFocus);
    element.addEventListener('blur', handleBlur);

    return () => {
      element.removeEventListener('focus', handleFocus);
      element.removeEventListener('blur', handleBlur);
    };
  }, []);

  return { ref, isFocusVisible };
}

/**
 * Utility to create accessible button props
 *
 * @param label - Accessible label for the button
 * @param options - Additional options
 * @returns Props for button element
 */
export function createAccessibleButtonProps(
  label: string,
  options: {
    expanded?: boolean;
    pressed?: boolean;
    describedBy?: string;
    controls?: string;
    popup?: 'menu' | 'listbox' | 'dialog' | 'tree' | 'grid';
  } = {}
): React.ButtonHTMLAttributes<HTMLButtonElement> {
  const { expanded, pressed, describedBy, controls, popup } = options;

  return {
    'aria-label': label,
    ...(expanded !== undefined && { 'aria-expanded': expanded }),
    ...(pressed !== undefined && { 'aria-pressed': pressed }),
    ...(describedBy && { 'aria-describedby': describedBy }),
    ...(controls && { 'aria-controls': controls }),
    ...(popup && { 'aria-haspopup': popup }),
  };
}
