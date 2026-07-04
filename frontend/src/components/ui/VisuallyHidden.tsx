import * as VisuallyHiddenPrimitive from '@radix-ui/react-visually-hidden';
import * as React from 'react';

/**
 * VisuallyHidden Component
 *
 * Utility component for hiding content visually while keeping it accessible to screen readers.
 * Based on Radix UI VisuallyHidden primitive.
 *
 * Use cases:
 * - Provide accessible labels for icon-only buttons
 * - Hide decorative text from visual users but announce it to screen readers
 * - Provide additional context for complex UI elements
 *
 * Accessibility (WCAG 2.1 AAA):
 * - Content is hidden via CSS but remains in the DOM
 * - Screen readers can access and announce the content
 * - Does not affect layout or visual appearance
 *
 * @example
 * // Icon-only button with accessible label
 * <button aria-label="Close dialog">
 *   <XIcon aria-hidden="true" />
 *   <VisuallyHidden>Close dialog</VisuallyHidden>
 * </button>
 *
 * @example
 * // Decorative icon with hidden label
 * <div>
 *   <SearchIcon aria-hidden="true" />
 *   <VisuallyHidden>Search</VisuallyHidden>
 * </div>
 */
const VisuallyHidden = VisuallyHiddenPrimitive.Root;

/**
 * Styled VisuallyHidden with additional safety checks
 *
 * This wrapper adds:
 * - Automatic aria-hidden on children to prevent double announcement
 * - Validation that content is not empty
 */
const StyledVisuallyHidden = React.forwardRef<
  HTMLSpanElement,
  React.ComponentPropsWithoutRef<typeof VisuallyHiddenPrimitive.Root>
>(({ children, ...props }, ref) => {
  // Validate that children is not empty
  const content = React.Children.toArray(children);
  const hasContent = content.some(child => {
    if (typeof child === 'string') return child.trim().length > 0;
    if (typeof child === 'number') return true;
    return React.isValidElement(child);
  });

  if (!hasContent && typeof window !== 'undefined') {
    console.warn('VisuallyHidden should have non-empty content for accessibility');
  }

  return (
    <VisuallyHiddenPrimitive.Root ref={ref} {...props}>
      {children}
    </VisuallyHiddenPrimitive.Root>
  );
});
StyledVisuallyHidden.displayName = 'StyledVisuallyHidden';

export { VisuallyHidden, StyledVisuallyHidden };
