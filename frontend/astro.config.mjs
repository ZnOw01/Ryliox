import { defineConfig, envField } from "astro/config";
import react from "@astrojs/react";
import tailwind from "@astrojs/tailwind";

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
    tailwind()
  ],
  outDir: "./dist",
});
