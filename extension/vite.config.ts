import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { crx } from "@crxjs/vite-plugin";
import path from "node:path";
import manifest from "./manifest.config.ts";

export default defineConfig({
  plugins: [react(), tailwindcss(), crx({ manifest })],
  resolve: {
    alias: {
      "@shared": path.resolve(import.meta.dirname, "../shared"),
    },
  },
  build: {
    rollupOptions: {
      // The popup and content script are discovered by @crxjs/vite-plugin
      // from manifest.config.ts. The dashboard is a full-tab page opened
      // via chrome.tabs.create() rather than referenced anywhere in the
      // manifest, so it needs to be listed as a build entry explicitly.
      input: {
        dashboard: path.resolve(import.meta.dirname, "src/dashboard/index.html"),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    hmr: {
      port: 5173,
    },
  },
});
