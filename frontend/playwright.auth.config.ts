import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/auth',
  outputDir: './test-results-auth',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5175', ...devices['Desktop Chrome'] },
  webServer: {
    command: 'npm run dev -- --port 5175 --strictPort',
    url: 'http://127.0.0.1:5175',
    env: {
      VITE_TRACKER_MODE: 'hosted',
      VITE_SUPABASE_URL: 'https://tracker-auth-test.supabase.co',
      VITE_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_synthetic_test_key',
      VITE_API_BASE_URL: '/api',
    },
    reuseExistingServer: false,
  },
})
