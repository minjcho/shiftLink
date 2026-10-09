import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', testMatch: '**/*.spec.ts', timeout: 90000,
  expect: { timeout: 15000 }, workers: 1, retries: 0,
  use: { baseURL: process.env.SHIFTLINK_E2E_BASE_URL ?? 'http://127.0.0.1:5173', headless: true, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  reporter: [['list']], outputDir: 'test-results',
});
