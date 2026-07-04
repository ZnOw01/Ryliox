import { defineConfig, envField } from 'astro/config';
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
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
  },
  outDir: './dist',
});
