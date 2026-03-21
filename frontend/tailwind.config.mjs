import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        mist: "#fff5f5",
        brand: {
          DEFAULT: "#dc2626",
          soft: "#fee2e2",
          deep: "#991b1b",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", ...defaultTheme.fontFamily.sans],
        display: ["Space Grotesk", ...defaultTheme.fontFamily.sans],
        mono: ["IBM Plex Mono", ...defaultTheme.fontFamily.mono],
      },
      boxShadow: {
        panel: "0 18px 54px -34px rgba(15, 23, 42, 0.32)",
        "panel-md": "0 10px 26px -16px rgba(15, 23, 42, 0.22)",
        "brand-glow": "0 0 0 3px rgba(220, 38, 38, 0.18)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [],
};
