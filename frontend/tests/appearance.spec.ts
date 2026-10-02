import { test, expect } from '@playwright/test'

// Mock only the list: appearance checks never write to the personal database.
const problems = [
  { number: 1, name: 'Two Sum', difficulty: 'Easy', topic: 'Arrays & Hashing', mastery_level: 'Partial Recall', next_review: '2026-10-01', attempts: 3 },
  { number: 20, name: 'Valid Parentheses', difficulty: 'Easy', topic: 'Stack', mastery_level: 'Mastered', next_review: '2026-10-08', attempts: 5 },
  { number: 33, name: 'Search in Rotated Sorted Array', difficulty: 'Medium', topic: 'Binary Search', mastery_level: 'Solved Independently', next_review: '2026-10-05', attempts: 2 },
  { number: 70, name: 'Climbing Stairs', difficulty: 'Easy', topic: 'Dynamic Programming', mastery_level: 'Solved with Struggle', next_review: '2026-10-07', attempts: 2 },
  { number: 42, name: 'Trapping Rain Water', difficulty: 'Hard', topic: 'Two Pointers', mastery_level: 'Learned Solution', next_review: '2026-09-30', attempts: 1 },
].map(problem => ({ ...problem, notes: 'An example note.', archived: false }))

test('theme defaults to dark, persists through reload, and applies to forms and narrow screens', async ({ page }) => {
  await page.route('**/api/problems/summary', route => route.fulfill({ json: problems }))
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')
  await expect(page.getByRole('rowheader', { name: 'Two Sum', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.screenshot({ path: 'test-results/appearance-dark.png' })
  await page.getByRole('button', { name: 'Switch to light mode' }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.screenshot({ path: 'test-results/appearance-light.png' })
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  await page.getByRole('button', { name: 'Close form' }).click()
  await page.getByRole('button', { name: 'Switch to dark mode' }).click()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Random pick', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/appearance-mobile.png' })
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCSS('background-color', 'rgb(32, 34, 38)')
  await page.screenshot({ path: 'test-results/appearance-mobile-form.png' })
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Add problem', exact: true })).toBeFocused()
})

test('blocked browser storage still allows changing the theme', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Storage blocked', 'SecurityError') } })
  })
  await page.route('**/api/problems/summary', route => route.fulfill({ json: [] }))
  await page.goto('/')
  await expect(page.getByText('A fresh start for your practice')).toBeVisible()
  await page.getByRole('button', { name: 'Switch to light mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
})
