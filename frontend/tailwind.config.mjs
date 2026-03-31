import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // shadcn v4 new-york color tokens
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        // Custom brand colors
        ink: "var(--ink)",
        mist: "var(--mist)",
        brand: {
          DEFAULT: "var(--brand)",
          soft: "var(--brand-soft)",
          deep: "var(--brand-deep)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", ...defaultTheme.fontFamily.sans],
        mono: ["IBM Plex Mono", ...defaultTheme.fontFamily.mono],
      },
      boxShadow: {
        panel: "0 20px 48px -30px rgba(153, 27, 27, 0.38)",
        "panel-md": "0 8px 24px -12px rgba(153, 27, 27, 0.28)",
        "brand-glow": "0 0 0 3px rgba(220, 38, 38, 0.2)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      spacing: {
        'touch': '44px',
        'touch-lg': '48px',
        'safe-top': 'env(safe-area-inset-top)',
        'safe-bottom': 'env(safe-area-inset-bottom)',
      },
      minWidth: {
        'touch': '44px',
      },
      minHeight: {
        'touch': '44px',
      },
      fontSize: {
        'mobile-base': ['16px', { lineHeight: '1.5' }],
      },
      screens: {
        'xs': '475px',
        'landscape': { 'raw': '(orientation: landscape)' },
        'portrait': { 'raw': '(orientation: portrait)' },
        'touch': { 'raw': '(pointer: coarse)' },
        'mouse': { 'raw': '(pointer: fine)' },
      },
    },
  },
  plugins: [],
};
