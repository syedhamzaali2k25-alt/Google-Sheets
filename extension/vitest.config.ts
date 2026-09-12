import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Deliberately separate from vite.config.ts: that config's @crxjs/vite-plugin
// manipulates the build around manifest.config.ts, which has no bearing on
// (and adds needless overhead/coupling to) running component unit tests.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@shared": path.resolve(import.meta.dirname, "../shared"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
