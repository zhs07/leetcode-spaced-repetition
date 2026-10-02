import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testIgnore: '**/auth/**',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5174', ...devices['Desktop Chrome'], locale: 'en-US', timezoneId: 'America/Vancouver' },
  webServer: [
    { command: '../.venv/bin/python -B tests/api_server.py', url: 'http://127.0.0.1:8011/problems', reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174 --strictPort', url: 'http://127.0.0.1:5174', env: { TRACKER_API_URL: 'http://127.0.0.1:8011', VITE_TRACKER_MODE: 'local', VITE_API_BASE_URL: '/api' }, reuseExistingServer: false },
  ],
})
