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
      },
    },
  },
  plugins: [],
};
