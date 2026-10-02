import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const headers = ['Problem', 'Difficulty', 'Topic', 'Last Reviewed', 'Mastery', 'Pattern/Trick', 'Reviews']
const notes = 'Keep commas, and\nmultiline notes intact'
const cell = (value: string) => `"${value.replaceAll('"', '""')}"`
function csv(rows: string[][]) {
  return [headers, ...rows].map(row => row.map(cell).join(',')).join('\r\n')
}
function row(title = 'Imported practice #12002', attempts = '4') {
  return [title, 'Easy', 'Import topic', 'September 10, 2026', '🔵 Mastered', notes, attempts]
}
async function choose(page: Page, text: string) {
  await page.getByLabel('Notion CSV file').setInputFiles({ name: 'practice_all.csv', mimeType: 'text/csv', buffer: Buffer.from(text) })
}
async function openPreview(page: Page, text: string) {
  await page.getByRole('button', { name: 'Import CSV', exact: true }).click()
  await choose(page, text)
  await page.getByRole('button', { name: 'Preview import', exact: true }).click()
}

test.afterEach(async ({ request }) => {
  // These IDs are synthetic and only exist in the disposable test database.
  for (const number of [12001, 12002]) await request.delete(`/api/problems/${number}`)
})

test('CSV preview, confirmed import, totals, repeated import and new attempt persist', async ({ page }) => {
  expect((await page.request.post('/api/problems', { data: {
    number: 12001, name: 'Keep existing practice', difficulty: 'Hard', topic: 'Existing topic', notes: 'Original note',
    first_attempt: { reviewed_on: '2026-09-01', mastery_level: 'Partial Recall' },
  } })).status()).toBe(201)
  const text = csv([row('Overwrite attempt #12001', '99'), row(), row('Missing number'), headers.map(() => '')])
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Show', exact: true }).selectOption('unreviewed')
  await openPreview(page, text)
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('2 valid problems')
  await expect(dialog).toContainText('Row 4: No match found')
  await expect(dialog).toContainText('1 empty row skipped')
  await expect(dialog.getByText(notes, { exact: true }).first()).not.toBeVisible()
  expect((await (await page.request.get('/api/problems')).json()).some((p: { number: number }) => p.number === 12002)).toBe(false)
  await page.screenshot({ path: 'test-results/import-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(dialog.getByRole('button', { name: 'Import 2 valid problems', exact: true })).toBeInViewport()
  await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeInViewport()
  await page.screenshot({ path: 'test-results/import-mobile.png', fullPage: true })
  await dialog.getByRole('button', { name: 'Import 2 valid problems', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('Imported 1 problem. Skipped 1 existing problem, 1 invalid row, and 1 empty row.', { exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Show', exact: true })).toHaveValue('all')
  const importedRow = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Imported practice', exact: true }) })
  await expect(importedRow.getByRole('cell').nth(5)).toHaveText('4')
  await expect(importedRow.locator('time')).toHaveAttribute('datetime', '2026-09-24')
  await expect(page.getByRole('rowheader', { name: 'Keep existing practice', exact: true })).toBeVisible()
  await expect(page.getByText(notes, { exact: true })).not.toBeVisible()
  await importedRow.getByRole('button', { name: 'Show notes' }).click()
  await expect(page.getByText(notes, { exact: true })).toBeVisible()
  await page.reload()
  await expect(importedRow.getByRole('cell').nth(5)).toHaveText('4')
  await expect(page.getByText(notes, { exact: true })).not.toBeVisible()

  await openPreview(page, text)
  await dialog.getByRole('button', { name: 'Import 2 valid problems', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('Imported 0 problems. Skipped 2 existing problems, 1 invalid row, and 1 empty row.', { exact: true })).toBeVisible()
  await expect(importedRow.getByRole('cell').nth(5)).toHaveText('4')
  const reviews = await (await page.request.get('/api/reviews')).json()
  expect(reviews.filter((r: { problem_number: number }) => r.problem_number === 12002)).toHaveLength(1)

  await importedRow.getByRole('button', { name: 'Record attempt for Imported practice', exact: true }).click()
  await page.getByLabel('Completion date').fill('2026-10-01')
  await page.getByRole('combobox', { name: 'Mastery level', exact: true }).selectOption('Solved Independently')
  await page.getByRole('button', { name: 'Save attempt', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(importedRow.getByRole('cell').nth(5)).toHaveText('5')
  await expect(importedRow.locator('time')).toHaveAttribute('datetime', '2026-10-08')
})

test('invalid files, zero valid rows, replacing a preview and cancellation never save', async ({ page }) => {
  let writes = 0
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/imports/notion') writes++ })
  await page.goto('/')
  await openPreview(page, '')
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('alert')).toContainText('This file is empty')
  await choose(page, 'Problem\nMissing headers')
  await dialog.getByRole('button', { name: 'Preview import', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Missing columns:')
  await choose(page, csv([row('No number')]))
  await dialog.getByRole('button', { name: 'Preview import', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Import 0 valid problems', exact: true })).toBeDisabled()
  await expect(dialog).toContainText('No valid problems to import')
  await choose(page, csv([row()]))
  await expect(dialog.getByRole('button', { name: /Import \d valid/ })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Preview import', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  expect(writes).toBe(0)
})

test('import blocks conflicting actions while pending, recovers from failure and confirms success despite failed refresh', async ({ page }) => {
  let attempts = 0
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/imports/notion', async route => {
    attempts++
    if (attempts === 1) {
      await pending
      await route.fulfill({ status: 500, json: { detail: 'Import failed. No problems were saved. Please try again.' } })
    } else {
      await route.fulfill({ json: { imported_numbers: [12002], skipped_existing_numbers: [], errors: [], skipped_rows: 0 } })
    }
  })
  await page.goto('/')
  await openPreview(page, csv([row()]))
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Importing…' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled()
  await expect(page.getByLabel('Notion CSV file')).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  expect(attempts).toBe(1)
  release()
  await expect(dialog.getByRole('alert')).toContainText('No problems were saved')
  await expect(dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true })).toBeEnabled()
  await page.route('**/api/problems/summary', route => route.fulfill({ status: 503, body: '' }))
  await dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('Imported 1 problem. Skipped 0 existing problems, 0 invalid rows, and 0 empty rows.', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('503')
  await page.unroute('**/api/problems/summary')
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(attempts).toBe(2)
})
