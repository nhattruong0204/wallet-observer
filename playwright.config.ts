import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/ui",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5173", browserName: "chromium" },
  webServer: {
    command: "make dev",
    url: "http://127.0.0.1:5173/health/ready",
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 15000 },
    timeout: 30000,
    env: {
      APP_MODE: "fixture",
      HELIUS_ENABLED: "false",
      TELEGRAM_ENABLED: "false",
      HELIUS_API_KEY: "",
      TELEGRAM_BOT_TOKEN: "",
      TELEGRAM_CHAT_ID: "",
    },
  },
});
