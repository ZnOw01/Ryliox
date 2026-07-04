/**
 * Skip Link Component - Enhanced Accessibility
 *
 * Allows keyboard users to skip repetitive navigation and jump to main content.
 * Follows WCAG 2.1 guideline 2.4.1 (Bypass Blocks).
 *
 * Features:
 * - Visualmente oculto por defecto
 * - Visible cuando recibe focus
 * - Smooth scroll al contenido principal
 * - Focus se mueve al elemento destino
 * - ARIA labeling apropiado
 *
 * @example
 * // En tu layout principal:
 * <SkipLink targetId="main-content" />
 * <header>...</header>
 * <main id="main-content" tabIndex={-1}>
 *   ...
 * </main>
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

export interface SkipLinkProps {
  /** ID del elemento destino (default: "main-content") */
  targetId?: string;
  /** Texto del link (default: "Skip to main content" / "Saltar al contenido principal") */
  label?: string;
  /** Clases adicionales */
  className?: string;
  /** Callback cuando se activa el skip link */
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
      // Asegurar que el elemento pueda recibir focus
      target.tabIndex = -1;
      target.focus({ preventScroll: true });

      // Scroll al elemento
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });

      // Limpiar tabIndex después de perder focus
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
        // Posicionamiento
        'fixed left-0 top-0 z-[9999]',
        // Visibilidad: oculto por defecto, visible en focus
        '-translate-y-full',
        'focus:translate-y-0',
        'transition-transform duration-200 ease-out',
        // Estilos
        'bg-gray-900 text-white',
        'px-4 py-3',
        'text-sm font-medium',
        'shadow-lg',
        // Focus styles
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        className
      )}
      aria-label={label}
    >
      {label}
    </a>
  );
}

/**
 * SkipLinkEn - English version
 */
export function SkipLinkEn(props: Omit<SkipLinkProps, 'label'>) {
  return <SkipLink {...props} label="Skip to main content" />;
}

/**
 * SkipLinkEs - Spanish version
 */
export function SkipLinkEs(props: Omit<SkipLinkProps, 'label'>) {
  return <SkipLink {...props} label="Saltar al contenido principal" />;
}

// CSS styles para referencia (usar en global.css o Tailwind config)
export const skipLinkCSS = `
  /* Skip Link Base Styles */
  .skip-link {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 9999;
    transform: translateY(-100%);
    transition: transform 0.2s ease-out;
    background-color: #1f2937;
    color: white;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  }

  .skip-link:focus {
    transform: translateY(0);
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }
`;

export default SkipLink;
