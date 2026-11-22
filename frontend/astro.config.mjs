import { defineConfig, envField, fontProviders } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  devToolbar: {
    enabled: false,
  },
  env: {
    schema: {
      // Optional: API base URL. Defaults to same-origin in production
      // Set via PUBLIC_API_BASE env var for external API endpoints
      PUBLIC_API_BASE: envField.string({
        context: 'client',
        access: 'public',
        optional: true,
      }),
    },
  },
  // Downloaded at build time and served from the app's own origin, which the CSP allows.
  fonts: [
    {
      provider: fontProviders.fontsource(),
      name: 'Plus Jakarta Sans',
      cssVariable: '--font-jakarta',
      weights: [400, 500, 600, 700, 800],
      styles: ['normal', 'italic'],
      subsets: ['latin', 'latin-ext'],
      fallbacks: ['system-ui', 'sans-serif'],
    },
    {
      provider: fontProviders.fontsource(),
      name: 'JetBrains Mono',
      cssVariable: '--font-jetbrains',
      weights: [400, 500, 600, 700],
      styles: ['normal'],
      subsets: ['latin'],
      fallbacks: ['ui-monospace', 'monospace'],
    },
  ],
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
  },
  outDir: './dist',
});
