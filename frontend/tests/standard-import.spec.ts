import { test, expect } from '@playwright/test'

const headers = 'number,name,difficulty,topic,notes,reviewed_on,mastery_level,total_attempts'
const minimal = 'number,name,difficulty,topic\n14001,Unreviewed import,Easy,Arrays'

test.afterEach(async ({ request }) => {
  for (const number of [14001, 14002]) await request.delete(`/api/problems/${number}`)
})

test('standard preview preserves optional history, imports without invented reviews and persists', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Import CSV', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('combobox', { name: 'CSV format' })).toHaveValue('standard')
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({
    name: 'standard.csv', mimeType: 'text/csv', buffer: Buffer.from(
      `${headers}\n14001,Unreviewed import,Easy,Arrays,,,,\n` +
      '14002,Reviewed import,Medium,Graphs,"Comma, and\nnew line",2026-10-03,Partial Recall,4\n' +
      ',Missing number,Easy,Arrays,,,,',
    ),
  })
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog).toContainText('2 valid problems')
  await expect(dialog).toContainText('Row 4: number must be a positive integer')
  const previewRow = dialog.getByRole('row').filter({ hasText: '#14001 Unreviewed import' })
  await expect(previewRow.getByRole('cell').nth(0)).toHaveText('Not reviewed')
  await expect(previewRow.getByRole('cell').nth(2)).toHaveText('0')
  expect((await (await page.request.get('/api/problems')).json()).some((p: { number: number }) => p.number === 14001)).toBe(false)
  await page.screenshot({ path: 'test-results/standard-import-desktop.png', fullPage: true })
  await dialog.locator('.import-content').evaluate(element => { element.scrollTop = element.scrollHeight })
  await page.screenshot({ path: 'test-results/standard-import-preview-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(dialog.getByRole('button', { name: 'Import 2 valid problems', exact: true })).toBeInViewport()
  await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeInViewport()
  await page.screenshot({ path: 'test-results/standard-import-mobile.png', fullPage: true })
  await dialog.locator('.import-content').evaluate(element => { element.scrollTop = element.scrollHeight })
  await page.screenshot({ path: 'test-results/standard-import-preview-mobile.png', fullPage: true })
  await dialog.getByRole('button', { name: 'Import 2 valid problems', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await page.reload()
  const unreviewed = await (await page.request.get('/api/problems/14001/summary')).json()
  expect([unreviewed.attempts, unreviewed.mastery_level, unreviewed.next_review, unreviewed.notes]).toEqual([0, null, null, ''])
  const reviewed = await (await page.request.get('/api/problems/14002/summary')).json()
  expect([reviewed.attempts, reviewed.next_review, reviewed.notes]).toEqual([4, '2026-10-06', 'Comma, and\nnew line'])
  const reviews = await (await page.request.get('/api/reviews')).json()
  expect(reviews.filter((r: { problem_number: number }) => r.problem_number === 14001)).toHaveLength(0)
  expect(reviews.filter((r: { problem_number: number }) => r.problem_number === 14002)).toHaveLength(1)
  await page.getByRole('combobox', { name: 'Show', exact: true }).selectOption('unreviewed')
  await expect(page.getByRole('rowheader', { name: 'Unreviewed import', exact: true })).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Reviewed import', exact: true })).toHaveCount(0)
})

test('minimal columns preview and template download work; changing format clears stale preview', async ({ page }) => {
  let saves = 0
  page.on('request', request => {
    if (/\/api\/imports\/(standard|notion)$/.test(new URL(request.url()).pathname)) saves++
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Import CSV', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const downloadPromise = page.waitForEvent('download')
  await dialog.getByRole('link', { name: 'Download CSV template' }).click()
  expect((await downloadPromise).suggestedFilename()).toBe('standard-import-template.csv')
  const template = await page.request.get('/standard-import-template.csv')
  expect(template.ok()).toBe(true)
  expect(await template.text()).toContain(headers)
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({ name: 'minimal.csv', mimeType: 'text/csv', buffer: Buffer.from(minimal) })
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog).toContainText('1 valid problem')
  await dialog.getByRole('combobox', { name: 'CSV format' }).selectOption('notion')
  await expect(dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true })).toHaveCount(0)
  await expect(dialog.getByRole('link', { name: 'Download CSV template' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Missing columns:')
  await dialog.getByRole('combobox', { name: 'CSV format' }).selectOption('standard')
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true })).toBeEnabled()
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({ name: 'partial.csv', mimeType: 'text/csv', buffer: Buffer.from(`${headers}\n14001,Partial history,Easy,Arrays,,2026-10-03,,`) })
  await expect(dialog.getByRole('button', { name: 'Import 1 valid problem', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog).toContainText('Provide both reviewed_on and mastery_level')
  await expect(dialog.getByRole('button', { name: 'Import 0 valid problems', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  expect(saves).toBe(0)
})

test('format and file stay locked while preview is pending', async ({ page }) => {
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/imports/standard/preview', async route => {
    await pending
    await route.continue()
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Import CSV', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await page.getByLabel('CSV file', { exact: true }).setInputFiles({ name: 'minimal.csv', mimeType: 'text/csv', buffer: Buffer.from(minimal) })
  await dialog.getByRole('button', { name: 'Preview import' }).click()
  await expect(dialog.getByRole('combobox', { name: 'CSV format' })).toBeDisabled()
  await expect(page.getByLabel('CSV file', { exact: true })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  release()
  await expect(dialog).toContainText('1 valid problem')
  await expect(dialog.getByRole('combobox', { name: 'CSV format' })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
})
