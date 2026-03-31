import { defineConfig, envField } from "astro/config";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  devToolbar: {
    enabled: false,
  },
  env: {
    schema: {
      PUBLIC_API_BASE: envField.string({
        context: "client",
        access: "public",
        optional: true,
      }),
    },
  },
  integrations: [
    react(),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
  outDir: "./dist",
});
