import { test, expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import type { PracticePick, StatementNode } from '../src/api'

const statement = 'Given a sequence of values, return a result.\n\nExample:\nInput: [1, 2]\nOutput: 3\n\nConstraints:\nThe sequence is non-empty.'
async function seed(request: APIRequestContext, number = 13001, date = '2000-01-01') {
  const response = await request.post('/api/problems', { data: {
    number, name: 'Hidden interview title', difficulty: 'Hard', topic: 'Hidden topic hint', notes: 'Hidden solution text',
    first_attempt: { reviewed_on: date, mastery_level: 'Mastered' },
  } })
  expect(response.status()).toBe(201)
}
async function cache(request: APIRequestContext) {
  expect((await request.put('/api/practice/13001/statement', { data: { text: statement } })).status()).toBe(200)
}
const node = (tag: string, ...children: StatementNode[]): StatementNode => ({ tag, children, src: null, alt: null })
const richPick: PracticePick = {
  problem_number: 13001, statement_error: null, leetcode_url: 'https://leetcode.com/problems/hidden-title/description/',
  statement: [
    node('p', 'Given a sequence of integers ', node('code', 'values'), ', return the length of the longest contiguous segment whose values are all distinct.'),
    node('p', node('strong', 'Example 1:')),
    node('pre', node('strong', 'Input: '), 'values = [1,2,1,3]\n', node('strong', 'Output: '), '3\n', node('strong', 'Explanation: '), 'The segment [2,1,3] has three distinct values.'),
    node('p', node('strong', 'Constraints:')),
    node('ul', node('li', node('code', '1 <= values.length <= 10'), node('sup', '5')), node('li', 'Values are integers.')),
  ],
}
async function open(page: Page) {
  await page.getByRole('button', { name: 'Random pick', exact: true }).click()
  return page.getByRole('dialog', { name: 'Practice problem' })
}

test.afterEach(async ({ request }) => {
  for (const number of [13001, 13002, 13003, 13004]) await request.delete(`/api/problems/${number}`)
})

test('real due selection stays blind, cached statements persist, and recording updates the chosen problem', async ({ page }) => {
  await seed(page.request)
  await seed(page.request, 13002, '2999-01-01')
  await seed(page.request, 13003)
  await page.request.post('/api/problems/13003/archive')
  expect((await page.request.post('/api/problems', { data: { number: 13004, name: 'Unreviewed example', difficulty: 'Easy', topic: 'Other topic' } })).status()).toBe(201)
  await cache(page.request)
  await page.goto('/')
  // Toolbar filters do not reveal or constrain the random draw's topic.
  await page.getByRole('combobox', { name: 'Show', exact: true }).selectOption('archived')
  const dialog = await open(page)
  await expect(dialog.getByRole('article', { name: 'Problem statement' })).toContainText('Given a sequence of values')
  for (const hidden of ['Hidden interview title', 'Hidden topic hint', 'Hidden solution text', 'Mastered', '#13001']) {
    await expect(dialog.getByText(hidden, { exact: false })).toHaveCount(0)
  }
  await expect(dialog.getByRole('link', { name: 'Open on LeetCode' })).toHaveCount(0)
  expect((await (await page.request.get('/api/reviews')).json()).filter((review: { problem_number: number }) => review.problem_number === 13001)).toHaveLength(1)
  await dialog.getByRole('button', { name: 'Reveal details', exact: true }).click()
  await expect(dialog.getByRole('region', { name: 'Revealed details' })).toContainText('#13001 Hidden interview title')
  await expect(dialog.getByText('Hidden solution text', { exact: true })).not.toBeVisible()
  await dialog.getByText('Show notes', { exact: true }).click()
  await expect(dialog.getByText('Hidden solution text', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Hide details', exact: true }).click()
  await expect(dialog.getByRole('region', { name: 'Revealed details' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Record attempt', exact: true }).click()
  await dialog.getByLabel('Completion date').fill('2999-01-01')
  await dialog.getByRole('combobox', { name: 'Mastery level', exact: true }).selectOption('Solved Independently')
  await dialog.getByRole('button', { name: 'Save attempt', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('Attempt recorded.', { exact: true })).toBeVisible()
  const summary = await (await page.request.get('/api/problems/13001/summary')).json()
  expect(summary.attempts).toBe(2)
  expect(summary.next_review).toBe('2999-01-08')
  await page.reload()
  await open(page)
  await expect(dialog.getByRole('alert')).toContainText('no due or overdue problems')
})

test('rich statement preserves code, examples and constraints with visible desktop/mobile controls', async ({ page }) => {
  let picks = 0
  let details = 0
  await page.route('**/api/practice/random', route => { picks++; return route.fulfill({ json: richPick }) })
  await page.route('**/api/problems/13001/summary', route => { details++; return route.fulfill({ json: { number: 13001, name: 'Hidden interview title', difficulty: 'Hard', topic: 'Hidden topic hint', notes: 'Hidden solution text', archived: false, attempts: 4, next_review: '2000-01-15', mastery_level: 'Mastered' } }) })
  await page.goto('/')
  const dialog = await open(page)
  await expect(dialog.locator('article pre')).toContainText('Input: values = [1,2,1,3]')
  await expect(dialog.locator('article code').first()).toHaveText('values')
  await expect(dialog.locator('article sup')).toHaveText('5')
  await expect(dialog.locator('article li')).toHaveCount(2)
  await expect(dialog.getByRole('link')).toHaveCount(0)
  expect(picks).toBe(1)
  expect(details).toBe(0)
  await page.screenshot({ path: 'test-results/blind-practice-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(dialog.getByRole('button', { name: 'Record attempt', exact: true })).toBeInViewport()
  await expect(dialog.getByRole('button', { name: 'Reveal details', exact: true })).toBeInViewport()
  await page.screenshot({ path: 'test-results/blind-practice-mobile.png', fullPage: true })
  await dialog.getByRole('button', { name: 'Reveal details', exact: true }).click()
  await expect(dialog.getByRole('link', { name: 'Open on LeetCode' })).toHaveAttribute('href', richPick.leetcode_url!)
  await dialog.getByRole('button', { name: 'Pick another', exact: true }).click()
  await expect(dialog.locator('article pre')).toBeVisible()
  await expect(dialog.getByRole('region', { name: 'Revealed details' })).toHaveCount(0)
  await expect(dialog.getByRole('link')).toHaveCount(0)
  expect(picks).toBe(2)
})

test('empty/error response retries without duplicate initial draws and can close during loading', async ({ page }) => {
  let picks = 0
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/practice/random', async route => {
    picks++
    if (picks === 1) await route.fulfill({ status: 404, json: { detail: "You're caught up. There are no due or overdue problems." } })
    else { await pending; await route.fulfill({ json: richPick }) }
  })
  await page.goto('/')
  const dialog = await open(page)
  await expect(dialog.getByRole('alert')).toContainText("You're caught up")
  expect(picks).toBe(1)
  await dialog.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Try again', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('status')).toContainText('Picking a due problem')
  await dialog.getByRole('button', { name: 'Close practice' }).click()
  await expect(dialog).not.toBeVisible()
  release()
  expect(picks).toBe(2)
})

test('missing statement retries same selection, saves a safe paste and uses it on the next pick', async ({ page }) => {
  await seed(page.request)
  const missing: PracticePick = { problem_number: 13001, statement: null, statement_error: 'Statement unavailable. Paste it below.', leetcode_url: null }
  let picks = 0
  let retries = 0
  await page.route('**/api/practice/random', route => { picks++; return route.fulfill({ json: missing }) })
  await page.route('**/api/practice/13001/statement/load', route => { retries++; return route.fulfill({ json: missing }) })
  await page.goto('/')
  const dialog = await open(page)
  await expect(dialog).toContainText('Statement unavailable')
  await expect(dialog.getByRole('button', { name: 'Record attempt', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Retry statement', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Retry statement', exact: true })).toBeEnabled()
  expect(retries).toBe(1)
  expect(picks).toBe(1)
  await dialog.getByRole('button', { name: 'Reveal details', exact: true }).click()
  await expect(dialog.getByRole('region', { name: 'Revealed details' })).toContainText('Hidden interview title')
  const paste = 'A pasted prompt.\nInput: <script>window.unexpected = true</script>'
  await dialog.getByLabel('Paste problem statement').fill(paste)
  await dialog.getByRole('button', { name: 'Save statement', exact: true }).click()
  await expect(dialog.getByRole('article')).toContainText(paste)
  await expect(dialog.getByRole('region', { name: 'Revealed details' })).toHaveCount(0)
  expect(await page.evaluate(() => 'unexpected' in window)).toBe(false)
  await dialog.getByRole('button', { name: 'Close practice' }).click()
  await page.unroute('**/api/practice/random')
  await page.unroute('**/api/practice/13001/statement/load')
  await page.reload()
  await open(page)
  await expect(dialog.getByRole('article')).toContainText(paste)
  await expect(dialog.getByText('Hidden interview title')).toHaveCount(0)
})

test('attempt errors and pending saves preserve blind selection; confirmed save survives a failed refresh', async ({ page }) => {
  await seed(page.request)
  await cache(page.request)
  await page.goto('/')
  const dialog = await open(page)
  await expect(dialog.getByRole('article')).toBeVisible()
  await dialog.getByRole('button', { name: 'Record attempt', exact: true }).click()
  await dialog.getByLabel('Completion date').fill('2999-01-01')
  await dialog.getByRole('combobox', { name: 'Mastery level', exact: true }).selectOption('Mastered')
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  let saves = 0
  await page.route('**/api/reviews', async route => {
    saves++
    expect(route.request().postDataJSON().problem_number).toBe(13001)
    await pending
    await route.fulfill({ status: 503, json: { detail: 'Could not save this attempt' } })
  })
  await dialog.getByRole('button', { name: 'Save attempt', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Saving…' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Close practice' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Pick another' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  expect(saves).toBe(1)
  release()
  await expect(dialog.getByRole('alert')).toHaveText('Could not save this attempt')
  await expect(dialog.getByText('Hidden interview title')).toHaveCount(0)
  await page.unroute('**/api/reviews')
  await page.route('**/api/problems/summary', route => route.fulfill({ status: 503, body: '' }))
  await dialog.getByRole('button', { name: 'Save attempt', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('Attempt recorded.', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('503')
  const reviews = await (await page.request.get('/api/reviews')).json()
  expect(reviews.filter((review: { problem_number: number }) => review.problem_number === 13001)).toHaveLength(2)
})
