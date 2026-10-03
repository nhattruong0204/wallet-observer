import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // No environment variable is automatically copied into a browser bundle.
  envPrefix: [],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" },
    fs: {
      allow: [
        fileURLToPath(new URL(".", import.meta.url)),
        fileURLToPath(new URL("../node_modules", import.meta.url)),
      ],
      deny: [
        ".env",
        ".env.*",
        "*.{crt,pem}",
        "**/.git/**",
        "**/local-data/**",
        "**/watchlist.local.*",
        "**/secrets/**",
        "**/backups/**",
      ],
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
