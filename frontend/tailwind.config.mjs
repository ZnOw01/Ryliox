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
    },
  },
  plugins: [],
};
