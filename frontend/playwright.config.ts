import { defineConfig } from '@playwright/test'

// Override with GF_CONSOLE_URL when the default dev port is already in use.
const baseURL = process.env.GF_CONSOLE_URL ?? 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL,
    screenshot: 'only-on-failure',
  },
})
