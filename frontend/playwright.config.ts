import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5174', ...devices['Desktop Chrome'] },
  webServer: [
    { command: '../.venv/bin/python -B tests/api_server.py', url: 'http://127.0.0.1:8011/problems', reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174 --strictPort', url: 'http://127.0.0.1:5174', env: { TRACKER_API_URL: 'http://127.0.0.1:8011' }, reuseExistingServer: false },
  ],
})
