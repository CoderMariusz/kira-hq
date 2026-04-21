import { defineConfig, devices } from '@playwright/test'

const PORT = 3001
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- -p 3001',
    url: baseURL,
    reuseExistingServer: true,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      ...process.env,
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3100',
      NEXT_PUBLIC_MOCK: process.env.NEXT_PUBLIC_MOCK ?? '1',
      NEXT_PUBLIC_HERMES_URL: process.env.NEXT_PUBLIC_HERMES_URL ?? 'http://localhost:4000',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
