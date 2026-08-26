import * as React from 'react';
import { cn } from '../lib/cn';

export interface SkipLinkProps {
  /** ID of the target element (default: "main-content") */
  targetId?: string;
  /** Link text label */
  label?: string;
  /** Additional CSS class names */
  className?: string;
  /** Callback fired when skip link is activated */
  onSkip?: () => void;
}

export function SkipLink({
  targetId = 'main-content',
  label = 'Skip to main content',
  className,
  onSkip,
}: SkipLinkProps) {
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();

    const target = document.getElementById(targetId);
    if (target) {
      target.tabIndex = -1;
      target.focus({ preventScroll: true });
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });

      const handleBlur = () => {
        target.removeAttribute('tabindex');
        target.removeEventListener('blur', handleBlur);
      };
      target.addEventListener('blur', handleBlur);

      onSkip?.();
    }
  };

  return (
    <a
      href={`#${targetId}`}
      onClick={handleClick}
      className={cn(
        'fixed left-0 top-0 z-[9999]',
        '-translate-y-full focus:translate-y-0',
        'transition-transform duration-200 ease-out',
        'bg-gray-900 text-white',
        'px-4 py-3 text-sm font-medium shadow-lg',
        'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
        className
      )}
      aria-label={label}
    >
      {label}
    </a>
  );
}

export default SkipLink;
