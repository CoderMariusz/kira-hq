import { defineConfig, devices } from "@playwright/test";

// PRD §6.15 — E2E scaffold for Kira-HQ Modules 2 (FastAPI) and 3 (Next.js).
// Kept minimal so `npx playwright test --list` succeeds before Modules
// 2/3 land. Chromium-only (Mac M4 native, no Webkit/FF sprawl).
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /.*\.spec\.ts$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "line",
  use: {
    baseURL: "http://localhost:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
