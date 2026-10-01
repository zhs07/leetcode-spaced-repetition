import { test, expect } from '@playwright/test'

test('create problems, protect notes, record attempts, and display API errors', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('A fresh start for your practice')).toBeVisible()
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await page.getByLabel('Problem number').fill('1')
  await page.getByLabel('Name', { exact: true }).fill('Two Sum')
  await page.getByLabel('Topic', { exact: true }).fill('Arrays & Hashing')
  await page.getByLabel('Notes').fill('Use a hashmap to remember complements.')
  await expect(page.getByRole('checkbox', { name: 'Record my first attempt' })).toBeChecked()
  await page.getByRole('checkbox', { name: 'Record my first attempt' }).uncheck()
  await expect(page.getByRole('combobox', { name: 'Mastery level', exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByRole('cell', { name: 'Not reviewed', exact: true })).toBeVisible()
  await expect(page.getByText('Not scheduled', { exact: true })).toBeVisible()
  await expect(page.getByText('Use a hashmap to remember complements.')).not.toBeVisible()
  await page.getByRole('button', { name: 'Show notes' }).click()
  await expect(page.getByText('Use a hashmap to remember complements.')).toBeVisible()
  await page.getByRole('button', { name: 'Hide notes' }).click()
  await expect(page.getByText('Use a hashmap to remember complements.')).not.toBeVisible()

  for (const attempt of [
    { date: '2026-09-20', mastery: 'Solved Independently', next: 'Sep 27, 2026', count: '1' },
    { date: '2026-09-22', mastery: 'Partial Recall', next: 'Sep 24, 2026', count: '2' },
  ]) {
    await page.getByRole('button', { name: 'Record attempt for Two Sum' }).click()
    await page.getByLabel('Completion date').fill(attempt.date)
    await page.getByRole('combobox', { name: 'Mastery level', exact: true }).selectOption(attempt.mastery)
    await page.getByRole('button', { name: 'Save attempt' }).click()
    await expect(page.getByRole('dialog')).not.toBeVisible()
    const row = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Two Sum' }) })
    await expect(row.getByRole('cell').nth(3)).toHaveText(attempt.mastery)
    await expect(row.getByRole('cell').nth(4)).toContainText(attempt.next)
    await expect(row.getByRole('cell').nth(5)).toHaveText(attempt.count)
  }
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await page.getByLabel('Problem number').fill('1')
  await page.getByLabel('Name', { exact: true }).fill('Duplicate')
  await page.getByLabel('Topic', { exact: true }).fill('Arrays')
  await page.getByRole('checkbox', { name: 'Record my first attempt' }).uncheck()
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByRole('alert')).toHaveText('Problem already exists')
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Duplicate')
  await page.getByLabel('Problem number').fill('206')
  await page.getByLabel('Name', { exact: true }).fill('Reverse Linked List')
  await page.getByLabel('Topic', { exact: true }).fill('Linked List')
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByRole('rowheader', { name: 'Reverse Linked List' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('cell', { name: 'Partial Recall', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Not reviewed', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Add problem', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.screenshot({ path: 'test-results/mobile-form.png', fullPage: true })
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()

  await page.route('**/api/problems/summary', route => route.fulfill({ status: 503, body: '' }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Request failed (503)')
  await expect(page.getByRole('rowheader', { name: 'Two Sum' })).toBeVisible()
  await page.unroute('**/api/problems/summary')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('alert')).not.toBeVisible()
})


test('add a problem with its first attempt in one request', async ({ page }) => {
  const writes: string[] = []
  page.on('request', request => { if (request.method() === 'POST') writes.push(new URL(request.url()).pathname) })
  await page.goto('/')
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await page.getByLabel('Problem number').fill('70')
  await page.getByLabel('Name', { exact: true }).fill('Climbing Stairs')
  await page.getByLabel('Topic', { exact: true }).fill('Dynamic Programming')
  await expect(page.getByRole('checkbox', { name: 'Record my first attempt' })).toBeChecked()
  await expect(page.getByRole('combobox', { name: 'Mastery level', exact: true })).toHaveValue('')
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  expect(writes).toEqual([])
  await page.getByLabel('Completion date').fill('2026-09-29')
  await page.getByRole('combobox', { name: 'Mastery level', exact: true }).selectOption('Learned Solution')
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(writes).toEqual(['/api/problems'])
  const row = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Climbing Stairs' }) })
  await expect(row.getByRole('cell').nth(3)).toHaveText('Learned Solution')
  await expect(row.getByRole('cell').nth(4)).toContainText('Sep 30, 2026')
  await expect(row.getByRole('cell').nth(5)).toHaveText('1')
  await page.reload()
  await expect(row.getByRole('cell').nth(5)).toHaveText('1')
})


test('review badges distinguish overdue, today, near and distant calendar dates', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-31T12:00:00-07:00') })
  const dates = ['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-06', '2026-11-07', null]
  await page.route('**/api/problems/summary', route => route.fulfill({ json: dates.map((next_review, index) => ({
    number: index + 1, name: `Example ${index + 1}`, difficulty: 'Easy', topic: 'Arrays',
    mastery_level: next_review ? 'Partial Recall' : null, next_review, attempts: next_review ? 1 : 0, notes: '',
  })) }))
  await page.goto('/')
  const badges = page.locator('.review-date')
  for (const [index, label, tone] of [[0, '1d overdue', 'review-due'], [1, 'Due today', 'review-due'], [2, 'In 1d', 'review-soon'], [3, 'In 6d', 'review-soon'], [4, 'In 7d', 'review-later']] as const) {
    await expect(badges.nth(index)).toContainText(label)
    await expect(badges.nth(index)).toHaveClass(new RegExp(tone))
  }
  await expect(page.getByText('Not scheduled', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/review-badges.png', fullPage: true })
  await page.clock.fastForward(24 * 60 * 60 * 1000)
  await expect(badges.nth(1)).toContainText('1d overdue')
  await expect(badges.nth(2)).toContainText('Due today')
})

test('filters combine and all sort directions preserve missing values last', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-31T12:00:00-07:00') })
  const summaries = [
    { number: 1, name: 'Alpha', topic: 'Trees', difficulty: 'Hard', mastery_level: 'Mastered', next_review: '2026-11-07', attempts: 10, notes: '' },
    { number: 2, name: 'Beta', topic: 'Arrays', difficulty: 'Easy', mastery_level: 'Learned Solution', next_review: '2026-10-30', attempts: 2, notes: '' },
    { number: 3, name: 'Gamma', topic: 'Graphs', difficulty: 'Medium', mastery_level: 'Partial Recall', next_review: '2026-10-31', attempts: 3, notes: '' },
    { number: 4, name: 'Delta', topic: 'Arrays', difficulty: 'Easy', mastery_level: null, next_review: null, attempts: 0, notes: '' },
  ]
  let loads = 0
  await page.route('**/api/problems/summary', route => { loads++; return route.fulfill({ json: summaries }) })
  await page.goto('/')
  const rows = page.getByRole('rowheader')
  await expect(rows).toHaveText(['Beta', 'Gamma', 'Alpha', 'Delta'])
  const initialLoads = loads
  for (const [sort, asc, desc] of [
    ['next_review', ['Beta', 'Gamma', 'Alpha', 'Delta'], ['Alpha', 'Gamma', 'Beta', 'Delta']],
    ['mastery', ['Beta', 'Gamma', 'Alpha', 'Delta'], ['Alpha', 'Gamma', 'Beta', 'Delta']],
    ['attempts', ['Delta', 'Beta', 'Gamma', 'Alpha'], ['Alpha', 'Gamma', 'Beta', 'Delta']],
    ['difficulty', ['Beta', 'Delta', 'Gamma', 'Alpha'], ['Alpha', 'Gamma', 'Beta', 'Delta']],
    ['topic', ['Beta', 'Delta', 'Gamma', 'Alpha'], ['Alpha', 'Gamma', 'Beta', 'Delta']],
  ] as const) {
    await page.getByRole('combobox', { name: 'Sort by', exact: true }).selectOption(sort)
    await page.getByRole('combobox', { name: 'Direction', exact: true }).selectOption('asc')
    await expect(rows).toHaveText([...asc])
    await page.getByRole('combobox', { name: 'Direction', exact: true }).selectOption('desc')
    await expect(rows).toHaveText([...desc])
  }
  await page.getByRole('combobox', { name: 'Show', exact: true }).selectOption('due')
  await expect(rows).toHaveText(['Gamma', 'Beta'])
  await page.getByRole('combobox', { name: 'Filter by topic', exact: true }).selectOption('Arrays')
  await expect(rows).toHaveText(['Beta'])
  await page.getByRole('combobox', { name: 'Filter by mastery', exact: true }).selectOption('Mastered')
  await expect(page.getByText('No matching problems')).toBeVisible()
  await expect(page.getByText('Showing 0 of 4 problems')).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await page.getByRole('combobox', { name: 'Show', exact: true }).selectOption('unreviewed')
  await expect(rows).toHaveText(['Delta'])
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await expect(rows).toHaveCount(4)
  expect(loads).toBe(initialLoads)
  await page.screenshot({ path: 'test-results/filter-toolbar.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(page.getByRole('combobox', { name: 'Direction', exact: true })).toBeVisible()
})

test('delete cancels without request, handles errors, and persists through reload', async ({ page }) => {
  await page.goto('/')
  let deletes = 0
  page.on('request', r => { if (r.method() === 'DELETE') deletes++ })
  await page.getByRole('button', { name: 'Delete Two Sum', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('2 recorded attempts')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(deletes).toBe(0)
  await page.getByRole('button', { name: 'Delete Two Sum', exact: true }).click()
  await page.route('**/api/problems/1', route => route.fulfill({ status: 500, json: { detail: 'Delete failed' } }))
  await dialog.getByRole('button', { name: 'Delete problem', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Delete failed')
  await expect(page.getByRole('rowheader', { name: 'Two Sum', exact: true })).toBeVisible()
  await page.unroute('**/api/problems/1')
  await page.route('**/api/problems/summary', route => route.fulfill({ status: 503, body: '' }))
  await dialog.getByRole('button', { name: 'Delete problem', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('#1 Two Sum deleted.', { exact: true })).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Two Sum', exact: true })).toHaveCount(0)
  await expect(page.getByRole('alert')).toContainText('503')
  await page.unroute('**/api/problems/summary')
  await page.reload()
  await expect(page.getByRole('rowheader', { name: 'Reverse Linked List' })).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Two Sum', exact: true })).toHaveCount(0)
})

test('delete handles pending state, last topic, empty list and revealed notes', async ({ page }) => {
  const problem = { number: 500, name: 'Deletion example', topic: 'Unique topic', difficulty: 'Easy', mastery_level: null, next_review: null, attempts: 0, notes: 'Hidden solution' }
  let summaries = [problem]
  await page.route('**/api/problems/summary', route => route.fulfill({ json: summaries }))
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/problems/500', async route => { await pending; summaries = []; await route.fulfill({ json: { deleted: true } }) })
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Filter by topic', exact: true }).selectOption('Unique topic')
  await page.getByRole('button', { name: 'Show notes' }).click()
  await page.getByRole('button', { name: 'Delete Deletion example' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('0 recorded attempts')
  await page.screenshot({ path: 'test-results/delete-confirmation.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/delete-mobile.png', fullPage: true })
  await dialog.getByRole('button', { name: 'Delete problem', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Deleting…' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  release()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('A fresh start for your practice')).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Filter by topic', exact: true })).toHaveValue('')
  summaries = [problem]
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByRole('rowheader', { name: problem.name })).toBeVisible()
  await expect(page.getByText('Hidden solution', { exact: true })).not.toBeVisible()
})
