import { defineConfig, devices } from '@playwright/test'

const preview = (workspace: string, port: number) => ({
  command: `npm run preview -w ${workspace} -- --host 127.0.0.1 --port ${port} --strictPort`,
  url: `http://127.0.0.1:${port}`,
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
})

// Uses the locally installed Chrome so the smoke tests run without downloading a browser.
// On CI, swap `channel: 'chrome'` for `npx playwright install chromium`.
const browser = { ...devices['Desktop Chrome'], channel: 'chrome' as const }

export default defineConfig({
  testDir: './frontend/e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  fullyParallel: false,
  projects: [
    { name: 'astronaut', testMatch: /astronaut\.spec\.ts/, use: { ...browser, baseURL: 'http://127.0.0.1:4173' } },
    { name: 'ground', testMatch: /ground\.spec\.ts/, use: { ...browser, baseURL: 'http://127.0.0.1:4174' } },
  ],
  webServer: [
    preview('web-astronaut', 4173),
    preview('web-ground', 4174),
  ],
})
