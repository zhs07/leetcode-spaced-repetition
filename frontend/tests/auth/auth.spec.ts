import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const alice = '11111111-1111-4111-8111-111111111111'
const bob = '22222222-2222-4222-8222-222222222222'
const guest = '33333333-3333-4333-8333-333333333333'
function session(id = alice, expired = false) {
  const exp = Math.floor(Date.now() / 1000) + (expired ? -60 : 3600)
  const payload = Buffer.from(JSON.stringify({ sub: id, exp, aud: 'authenticated', is_anonymous: id === guest })).toString('base64url')
  return {
    access_token: `eyJhbGciOiJFUzI1NiJ9.${payload}.synthetic-signature`,
    token_type: 'bearer', expires_in: 3600, expires_at: exp, refresh_token: `refresh-${id}`,
    user: { id, aud: 'authenticated', role: 'authenticated', is_anonymous: id === guest, email: id === guest ? '' : id === alice ? 'alice@example.test' : 'bob@example.test', email_confirmed_at: '2026-01-01T00:00:00Z', app_metadata: { provider: id === guest ? 'anonymous' : 'email' }, user_metadata: {}, created_at: '2026-01-01T00:00:00Z' },
  }
}

async function mockServices(page: Page, options: { expiredLink?: boolean; callbackFailure?: boolean; apiUnauthorized?: boolean; guestDisabled?: boolean } = {}) {
  const calls: { path: string; body: Record<string, unknown> | null; authorization?: string }[] = []
  const guestProblems: Record<string, unknown>[] = []
  await page.route('https://tracker-auth-test.supabase.co/**', async route => {
    const url = new URL(route.request().url())
    const body = route.request().postDataJSON()
    calls.push({ path: url.pathname + url.search, body })
    if (url.pathname.endsWith('/token')) {
      if (options.expiredLink && url.searchParams.get('grant_type') === 'pkce') {
        return route.fulfill({ status: 400, headers: { 'x-supabase-api-version': '2024-01-01', 'access-control-expose-headers': 'X-Supabase-Api-Version' }, json: { code: 'otp_expired', msg: 'Email link expired' } })
      }
      if (options.callbackFailure && url.searchParams.get('grant_type') === 'pkce') {
        return route.fulfill({ status: 400, headers: { 'x-supabase-api-version': '2024-01-01', 'access-control-expose-headers': 'X-Supabase-Api-Version' }, json: { code: 'bad_code_verifier', msg: 'Code verifier mismatch' } })
      }
      if (body?.password === 'wrong-password') return route.fulfill({ status: 400, json: { code: 'invalid_credentials', msg: 'Invalid login credentials' } })
      const id = body?.refresh_token === `refresh-${guest}` ? guest : body?.email === 'bob@example.test' ? bob : alice
      return route.fulfill({ json: session(id) })
    }
    if (url.pathname.endsWith('/signup') && !body?.email) {
      if (options.guestDisabled) return route.fulfill({ status: 422, headers: { 'x-supabase-api-version': '2024-01-01', 'access-control-expose-headers': 'X-Supabase-Api-Version' }, json: { code: 'anonymous_provider_disabled', msg: 'Anonymous sign-ins are disabled' } })
      return route.fulfill({ json: session(guest) })
    }
    if (url.pathname.endsWith('/signup') || url.pathname.endsWith('/user')) return route.fulfill({ json: session().user })
    if (url.pathname.endsWith('/logout')) return route.fulfill({ status: 204 })
    return route.fulfill({ json: {} })
  })
  await page.route('**/api/**', async route => {
    const authorization = route.request().headers().authorization
    calls.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON(), authorization })
    if (options.apiUnauthorized) return route.fulfill({ status: 401, json: { detail: 'Expired' } })
    const token = authorization?.replace('Bearer ', '') || ''
    const id = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).sub
    if (id === guest) {
      const body = route.request().postDataJSON()
      if (route.request().method() === 'POST' && new URL(route.request().url()).pathname === '/api/problems') {
        guestProblems.push({ ...body, archived: false, mastery_level: null, next_review: null, attempts: 0 })
        return route.fulfill({ status: 201, json: body })
      }
      return route.fulfill({ json: guestProblems })
    }
    return route.fulfill({ json: [{ number: 1, name: id === alice ? 'Alice problem' : 'Bob problem', difficulty: 'Easy', topic: 'Arrays', notes: 'Private notes', mastery_level: null, next_review: null, attempts: 0, archived: false }] })
  })
  return calls
}

async function signIn(page: Page, email = 'alice@example.test', password = 'test-password') {
  await openSignIn(page)
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
}

async function openSignIn(page: Page) {
  if (!await page.getByLabel('Email', { exact: true }).isVisible()) await page.getByRole('button', { name: 'Sign in', exact: true }).click()
}

async function requestEmailLink(page: Page, recovery = false) {
  await page.goto('/')
  await openSignIn(page)
  await page.getByRole('button', { name: recovery ? 'Forgot password?' : 'Create an account' }).click()
  await page.getByLabel('Email', { exact: true }).fill('alice@example.test')
  if (!recovery) await page.getByLabel('Password', { exact: true }).fill('test-password')
  await page.getByRole('button', { name: recovery ? 'Send reset link' : 'Create account', exact: true }).click()
  await expect(page.getByRole('status')).toContainText(recovery ? 'If an account exists' : 'Check your email')
}

test('sign-in gates API access and switching users clears the previous table', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sample review space' })).toBeVisible()
  await openSignIn(page)
  await expect(page.getByRole('heading', { name: 'Sign in to your review space' })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('sign-in-desktop.png') })
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
  await signIn(page, 'alice@example.test', 'wrong-password')
  await expect(page.getByRole('alert')).toContainText('Invalid login credentials')
  await signIn(page)
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
  expect(calls.find(call => call.path.startsWith('/api'))?.authorization).toMatch(/^Bearer /)
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByText('Alice problem', { exact: true })).toHaveCount(0)
  await signIn(page, 'bob@example.test')
  await expect(page.getByText('Bob problem', { exact: true })).toBeVisible()
  await expect(page.getByText('Alice problem', { exact: true })).toHaveCount(0)
})

test('sign-up asks for email confirmation without fetching private records', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await openSignIn(page)
  await page.getByRole('button', { name: 'Create an account' }).click()
  await page.getByLabel('Email', { exact: true }).fill('alice@example.test')
  await page.getByLabel('Password', { exact: true }).fill('test-password')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Check your email')
  expect(calls.some(call => call.path.startsWith('/auth/v1/signup'))).toBeTruthy()
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
})

test('password recovery exchanges the link and saves a matching new password', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await openSignIn(page)
  await page.getByRole('button', { name: 'Forgot password?' }).click()
  await page.getByLabel('Email', { exact: true }).fill('alice@example.test')
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByRole('status')).toContainText('If an account exists')
  expect(calls.find(call => call.path.startsWith('/auth/v1/recover'))?.path).toContain('auth%3Drecovery')
  await page.goto('/?code=synthetic-reset-code&auth=recovery')
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible()
  await expect(page).not.toHaveURL(/code=/)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible()
  await page.getByLabel('New password', { exact: true }).fill('new-password')
  await page.getByLabel('Confirm new password', { exact: true }).fill('different-password')
  await page.getByRole('button', { name: 'Save new password' }).click()
  await expect(page.getByRole('alert')).toContainText('do not match')
  await page.getByLabel('Confirm new password', { exact: true }).fill('new-password')
  await page.getByRole('button', { name: 'Save new password' }).click()
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
  expect(calls.some(call => call.path === '/auth/v1/user' && call.body?.password === 'new-password')).toBeTruthy()
})

test('expired confirmation link produces a recoverable message', async ({ page }) => {
  const calls = await mockServices(page, { expiredLink: true })
  await requestEmailLink(page)
  await page.goto('/?code=expired')
  await expect(page.getByRole('alert')).toContainText('invalid or expired')
  expect(calls.some(call => call.path.includes('grant_type=pkce'))).toBeTruthy()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
  await expect(page).not.toHaveURL(/code=/)
})

test('failed confirmation exchange suggests sign-in without claiming the email expired', async ({ page }) => {
  const calls = await mockServices(page, { callbackFailure: true })
  await requestEmailLink(page)
  await page.goto('/?code=unexchangeable')
  await expect(page.getByRole('alert')).toContainText('Your email may already be confirmed; try signing in')
  await expect(page.getByRole('alert')).not.toContainText('expired')
  await expect(page).not.toHaveURL(/code=/)
  expect(calls.some(call => call.path.includes('grant_type=pkce'))).toBeTruthy()
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
  await signIn(page)
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('failed recovery exchange asks for a new reset link without showing the tracker', async ({ page }) => {
  const calls = await mockServices(page, { callbackFailure: true })
  await requestEmailLink(page, true)
  await page.goto('/?code=unexchangeable&auth=recovery')
  await expect(page.getByRole('alert')).toContainText('Request a new reset link')
  await expect(page.getByRole('alert')).not.toContainText('already be confirmed')
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toHaveCount(0)
  await expect(page).not.toHaveURL(/code=/)
  expect(calls.some(call => call.path.includes('grant_type=pkce'))).toBeTruthy()
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
})

test('confirmation callback without a browser verifier gives sign-in guidance', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/?code=from-another-browser')
  await expect(page.getByRole('alert')).toContainText('same browser where you signed up')
  await expect(page.getByRole('alert')).not.toContainText('expired')
  await expect(page).not.toHaveURL(/code=/)
  expect(calls).toHaveLength(0)
})

test('provider-reported expired link removes callback parameters and explains retry', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/?error=access_denied&error_code=otp_expired')
  await expect(page.getByRole('alert')).toContainText('invalid or expired')
  await expect(page).not.toHaveURL(/error=/)
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
})

test('API rejection clears the private view and asks for sign-in', async ({ page }) => {
  await mockServices(page, { apiUnauthorized: true })
  await page.goto('/')
  await signIn(page)
  await expect(page.getByRole('heading', { name: 'Sign in to your review space' })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('expired')
  await expect(page.getByRole('heading', { name: 'Your review space', exact: true })).toHaveCount(0)
})

test('expired stored session refreshes before requesting records', async ({ page }) => {
  const calls = await mockServices(page)
  await page.addInitScript(value => localStorage.setItem('sb-tracker-auth-test-auth-token', JSON.stringify(value)), session(alice, true))
  await page.goto('/')
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
  expect(calls.some(call => call.path.includes('grant_type=refresh_token'))).toBeTruthy()
  const token = calls.find(call => call.path.startsWith('/api'))!.authorization!.split(' ')[1]
  expect(JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).exp).toBeGreaterThan(Date.now() / 1000)
})

test('email form fits mobile viewport', async ({ page }) => {
  await mockServices(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await openSignIn(page)
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: test.info().outputPath('sign-in-mobile.png') })
})

test('confirmation link opens the signed-in tracker', async ({ page }) => {
  await mockServices(page)
  await page.goto('/')
  await openSignIn(page)
  await page.getByRole('button', { name: 'Create an account' }).click()
  await page.getByLabel('Email', { exact: true }).fill('alice@example.test')
  await page.getByLabel('Password', { exact: true }).fill('test-password')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Check your email')
  await page.goto('/?code=synthetic-confirmation')
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toHaveCount(0)
  await expect(page).not.toHaveURL(/code=/)
})

test('late response from the previous account cannot repopulate the table', async ({ page }) => {
  await mockServices(page)
  let release!: () => void
  const waiting = new Promise<void>(resolve => { release = resolve })
  let started!: () => void
  const requested = new Promise<void>(resolve => { started = resolve })
  await page.route('**/api/**', async route => {
    const token = route.request().headers().authorization.split(' ')[1]
    const id = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).sub
    if (id !== alice) return route.fallback()
    started()
    await waiting
    await route.fulfill({ json: [{ number: 1, name: 'Old private problem', difficulty: 'Easy', topic: 'Arrays', notes: 'old private note', mastery_level: null, next_review: null, attempts: 0, archived: false }] })
  })
  await page.goto('/')
  await signIn(page)
  await requested
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await signIn(page, 'bob@example.test')
  await expect(page.getByText('Bob problem', { exact: true })).toBeVisible()
  release()
  await expect(page.getByText('Old private problem', { exact: true })).toHaveCount(0)
})

test('landing shows labeled samples with interactive filters and no account or API calls', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sample review space' })).toBeVisible()
  await expect(page.getByText('Two Sum', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Email', { exact: true })).toHaveCount(0)
  await page.getByLabel('Filter by topic').selectOption('Stack')
  await expect(page.getByText('Valid Parentheses', { exact: true })).toBeVisible()
  await expect(page.getByText('Two Sum', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Show notes' }).click()
  await expect(page.getByText('Sample note: match each closing bracket with the top of the stack.')).toBeVisible()
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  expect(calls).toHaveLength(0)
  await page.screenshot({ path: test.info().outputPath('sample-desktop.png') })
})

test('guest creates a private workspace, saves a problem and returns after reload', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Try as guest' }).click()
  await expect(page.getByText(/Guest workspace ·/)).toBeVisible()
  await expect(page.getByText('A fresh start for your practice')).toBeVisible()
  await expect(page.getByText('Two Sum', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Add problem', exact: true }).click()
  await page.getByLabel('Problem number').fill('42')
  await page.getByLabel('Name', { exact: true }).fill('Guest example')
  await page.getByLabel('Topic', { exact: true }).fill('Arrays')
  await page.getByLabel('Record my first attempt').uncheck()
  await page.getByRole('button', { name: 'Add problem', exact: true }).last().click()
  await expect(page.getByText('Guest example', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Guest example', { exact: true })).toBeVisible()
  const signups = calls.filter(call => call.path === '/auth/v1/signup')
  expect(signups).toHaveLength(1)
  expect(signups[0].body).not.toHaveProperty('email')
  expect(signups[0].body).not.toHaveProperty('password')
  expect(calls.filter(call => call.path.startsWith('/api')).every(call => call.authorization?.startsWith('Bearer '))).toBeTruthy()
})

test('guest sign-in explains separate accounts and can return without replacing the session', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Try as guest' }).click()
  await expect(page.getByRole('heading', { name: 'Your review space', exact: true })).toBeVisible()
  await openSignIn(page)
  await expect(page.getByText(/Guest progress will not transfer/)).toBeVisible()
  await page.getByRole('button', { name: 'Back to guest workspace' }).click()
  await expect(page.getByText(/Guest workspace ·/)).toBeVisible()
  expect(calls.filter(call => call.path === '/auth/v1/signup')).toHaveLength(1)
  await signIn(page, 'bob@example.test')
  await expect(page.getByText('Bob problem', { exact: true })).toBeVisible()
  await expect(page.getByText(/Guest workspace ·/)).toHaveCount(0)
  await page.reload()
  await expect(page.getByText('Bob problem', { exact: true })).toBeVisible()
})

test('disabled guest provider gives a recoverable error and keeps samples visible', async ({ page }) => {
  const calls = await mockServices(page, { guestDisabled: true })
  await page.goto('/')
  await page.getByRole('button', { name: 'Try as guest' }).click()
  await expect(page.getByRole('alert')).toContainText('Guest access is not enabled yet')
  await expect(page.getByText('Two Sum', { exact: true })).toBeVisible()
  expect(calls.filter(call => call.path.startsWith('/api'))).toHaveLength(0)
  await signIn(page)
  await expect(page.getByText('Alice problem', { exact: true })).toBeVisible()
})

test('sample actions start a guest instead of writing sample records', async ({ page }) => {
  const calls = await mockServices(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Record attempt for Two Sum' }).click()
  await expect(page.getByText(/Guest workspace ·/)).toBeVisible()
  await expect(page.getByText('A fresh start for your practice')).toBeVisible()
  expect(calls.filter(call => call.path.startsWith('/api')).every(call => call.body === null)).toBeTruthy()
})

test('expired guest session refreshes as the same guest', async ({ page }) => {
  const calls = await mockServices(page)
  await page.addInitScript(value => localStorage.setItem('sb-tracker-auth-test-auth-token', JSON.stringify(value)), session(guest, true))
  await page.goto('/')
  await expect(page.getByText(/Guest workspace ·/)).toBeVisible()
  expect(calls.some(call => call.path.includes('grant_type=refresh_token'))).toBeTruthy()
  expect(calls.some(call => call.path === '/auth/v1/signup')).toBeFalsy()
})

test('sample preview fits mobile viewport and keeps guest entry visible', async ({ page }) => {
  await mockServices(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sample review space' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Try as guest' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: test.info().outputPath('sample-mobile.png') })
})
