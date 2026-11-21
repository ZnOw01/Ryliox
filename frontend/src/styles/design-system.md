# Ryliox Design System 2026

## Overview

Sistema de diseño moderno y coherente para Ryliox, construido con los principios de Context7 2025-2026. Utiliza el espacio de color OKLCH para consistencia perceptual y tokens CSS para escalabilidad.

---

## Design Philosophy

**Intent**: Una interfaz que se siente como una librería digital moderna — limpia, cálida, pero profesional. El color principal (coral/rose) evoca los libros de O'Reilly mientras mantiene una identidad propia distintiva.

**Signature Element**: Gradiente orgánico en el fondo que recuerda el papel de un libro, combinado con una cuadrícula sutil de guías de impresión.

**Color World**: Papel viejo, tinta de imprenta, marcadores de colores, etiquetas de estante, luz cálida de librería.

---

## Color System (OKLCH)

### Brand Colors

| Token | OKLCH Value | Usage |
|-------|-------------|-------|
| `--brand-50` | `oklch(97% 0.02 20)` | Fondos suaves |
| `--brand-100` | `oklch(95% 0.03 20)` | Surfaces hover |
| `--brand-200` | `oklch(91% 0.05 20)` | Bordes suaves |
| `--brand-300` | `oklch(86% 0.09 20)` | Scrollbar |
| `--brand-400` | `oklch(78% 0.14 20)` | Accent hover |
| `--brand-500` | `oklch(68% 0.18 20)` | **Primary brand** |
| `--brand-600` | `oklch(58% 0.20 20)` | Primary button |
| `--brand-700` | `oklch(48% 0.18 20)` | Primary hover |
| `--brand-800` | `oklch(40% 0.15 20)` | Text brand |
| `--brand-900` | `oklch(32% 0.12 20)` | Deep brand |
| `--brand-950` | `oklch(24% 0.09 20)` | Dark accents |

### Semantic Colors

**Success (Emerald)**
- `--success-500`: `oklch(62% 0.21 150)` - Indicadores de éxito
- `--success-600`: `oklch(52% 0.20 150)` - Botones success

**Warning (Amber)**
- `--warning-500`: `oklch(65% 0.21 80)` - Alertas
- `--warning-600`: `oklch(55% 0.20 80)` - Botones warning

**Error (Crimson)**
- `--error-500`: `oklch(58% 0.21 25)` - Errores críticos
- `--error-600`: `oklch(48% 0.20 25)` - Botones danger

**Info (Ocean)**
- `--info-500`: `oklch(62% 0.16 250)` - Información
- `--info-600`: `oklch(52% 0.15 250)` - Links informativos

### Neutral Scale (Slate)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--neutral-50` | 99% L | 12% L | Background base |
| `--neutral-100` | 97% L | 18% L | Surfaces hover |
| `--neutral-200` | 92% L | 22% L | Borders subtle |
| `--neutral-300` | 85% L | 30% L | Borders default |
| `--neutral-400` | 72% L | 40% L | Text muted |
| `--neutral-500` | 60% L | 50% L | Text tertiary |
| `--neutral-600` | 48% L | 65% L | Text secondary |
| `--neutral-700` | 38% L | 80% L | - |
| `--neutral-800` | 28% L | 92% L | - |
| `--neutral-900` | 20% L | 98% L | Text primary |
| `--neutral-950` | 12% L | - | Deep neutral |

### Surface Colors

**Light Mode:**
- `--surface-base`: `#fffdfd` - Fondo de página
- `--surface-elevated`: `#ffffff` - Cards elevadas
- `--surface-card`: `#ffffff` - Cards base
- `--surface-input`: `var(--neutral-100)` - Inputs
- `--surface-hover`: `var(--neutral-100)` - Estados hover
- `--surface-active`: `var(--neutral-200)` - Estados active

**Dark Mode:**
- `--surface-base`: `oklch(18% 0.03 260)`
- `--surface-elevated`: `oklch(22% 0.04 260)`
- `--surface-card`: `oklch(26% 0.05 260)`
- `--surface-input`: `oklch(30% 0.05 260)`
- `--surface-hover`: `oklch(30% 0.05 260)`
- `--surface-active`: `oklch(35% 0.06 260)`

---

## Typography

### Font Stack

```css
--font-sans: "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-mono: "IBM Plex Mono", "SF Mono", Consolas, Monaco, monospace;
```

### Type Scale

| Level | Size | Line Height | Letter Spacing | Weight | Usage |
|-------|------|-------------|----------------|--------|-------|
| Display | 3rem (48px) | 1.1 | -0.02em | 700 | Hero headings |
| H1 | 2.25rem (36px) | 1.2 | -0.02em | 700 | Page titles |
| H2 | 1.875rem (30px) | 1.3 | -0.01em | 600 | Section titles |
| H3 | 1.5rem (24px) | 1.4 | 0 | 600 | Card titles |
| H4 | 1.25rem (20px) | 1.5 | 0 | 600 | Sub-sections |
| Body | 1rem (16px) | 1.6 | 0 | 400 | Main text |
| Small | 0.875rem (14px) | 1.5 | 0 | 400 | Secondary text |
| XSmall | 0.75rem (12px) | 1.5 | 0.01em | 400 | Captions, badges |
| Tiny | 0.625rem (10px) | 1.4 | 0.02em | 500 | Labels |

---

## Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | - |
| `--space-1` | 0.25rem (4px) | Icon gaps |
| `--space-2` | 0.5rem (8px) | Tight spacing |
| `--space-3` | 0.75rem (12px) | Default gap |
| `--space-4` | 1rem (16px) | Component padding |
| `--space-5` | 1.25rem (20px) | Section gaps |
| `--space-6` | 1.5rem (24px) | Card padding |
| `--space-8` | 2rem (32px) | Major sections |
| `--space-10` | 2.5rem (40px) | Large gaps |
| `--space-12` | 3rem (48px) | Page sections |
| `--space-16` | 4rem (64px) | Hero spacing |

---

## Border Radius Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-0` | 0 | Sharp corners |
| `--radius-sm` | 0.25rem (4px) | Tags, badges |
| `--radius-md` | 0.375rem (6px) | Inputs, small buttons |
| `--radius-lg` | 0.5rem (8px) | Cards, buttons |
| `--radius-xl` | 0.75rem (12px) | Large cards |
| `--radius-2xl` | 1rem (16px) | Modals, dialogs |
| `--radius-3xl` | 1.5rem (24px) | Hero elements |
| `--radius-full` | 9999px | Pills, avatars |

---

## Shadow Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-1` | 0 1px 2px 0 | Subtle lift |
| `--shadow-2` | 0 1px 3px, 0 1px 2px | Default elevation |
| `--shadow-3` | 0 4px 6px, 0 2px 4px | Cards, buttons |
| `--shadow-4` | 0 10px 15px, 0 4px 6px | Dropdowns, modals |
| `--shadow-5` | 0 20px 25px, 0 8px 10px | Overlays, dialogs |
| `--shadow-inner` | inset 0 2px 4px | Inset inputs |
| `--shadow-focus` | 0 0 0 3px | Focus rings |

---

## Animation

### Timing Functions

```css
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
```

### Duration Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-instant` | 50ms | Micro-interactions |
| `--duration-fast` | 150ms | Hover states |
| `--duration-normal` | 250ms | Transitions |
| `--duration-slow` | 350ms | Page transitions |
| `--duration-slower` | 500ms | Complex animations |

### Animation Patterns

```css
/* Soft rise animation */
@keyframes soft-rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Progress stripe */
@keyframes progress-stripe {
  from { background-position: 0 0; }
  to { background-position: 28px 0; }
}

/* Pulse */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
```

---

## Z-Index Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--z-base` | 0 | Default |
| `--z-dropdown` | 100 | Dropdowns |
| `--z-sticky` | 200 | Sticky headers |
| `--z-fixed` | 300 | Fixed elements |
| `--z-modal-backdrop` | 400 | Modal overlays |
| `--z-modal` | 500 | Modals |
| `--z-popover` | 600 | Popovers |
| `--z-tooltip` | 700 | Tooltips |
| `--z-toast` | 800 | Toasts |
| `--z-skip-link` | 10000 | Skip links |

---

## Component Patterns

### Buttons

**Primary Button**
```
Background: var(--interactive-primary-bg)
Background Hover: var(--interactive-primary-bg-hover)
Text: var(--interactive-primary-text)
Padding: var(--space-3) var(--space-4)
Border Radius: var(--radius-lg)
Shadow: var(--shadow-2)
```

**Secondary Button**
```
Background: var(--interactive-secondary-bg)
Border: 1px solid var(--interactive-secondary-border)
Text: var(--interactive-secondary-text)
```

### Cards

**Card Base**
```
Background: var(--surface-card)
Border: 1px solid var(--border-subtle)
Border Radius: var(--radius-xl)
Padding: var(--space-6)
Shadow: var(--shadow-2)
```

### Inputs

**Input Base**
```
Background: var(--surface-input)
Border: 1px solid var(--border-default)
Border Radius: var(--radius-lg)
Padding: var(--space-3) var(--space-4)
Focus: border-color var(--border-focus), box-shadow var(--shadow-focus)
```

---

## Accessibility Standards

### Color Contrast (WCAG 2.1 AA)

- **Normal text**: 4.5:1 minimum
- **Large text**: 3:1 minimum
- **UI components**: 3:1 minimum

All tokens en OKLCH están calibrados para cumplir AA automáticamente.

### Focus Indicators

- Outline: 2px solid var(--border-focus)
- Outline Offset: 2px
- Transition: 150ms ease-out

### Motion Preferences

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Implementation

### Tailwind Config

```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      brand: {
        50: 'oklch(97% 0.02 20)',
        100: 'oklch(95% 0.03 20)',
        // ... etc
      }
    },
    boxShadow: {
      '1': 'var(--shadow-1)',
      '2': 'var(--shadow-2)',
      // ... etc
    }
  }
}
```

### CSS Import Order

```css
@import './oklch-palette.css';
@import './design-tokens.css';
@import './animations.css';
@import './focus.css';
@import './a11y.css';
@tailwind base;
@tailwind components;
@tailwind utilities;
```

---

## Version History

- **2026.03** - Initial Context7 2026 implementation
- OKLCH color space adoption
- Full design tokens system
- Accessibility compliance audit
- Performance optimized

---

*Design System © 2026 - Ryliox*
