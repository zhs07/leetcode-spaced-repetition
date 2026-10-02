import { createClient } from '@supabase/supabase-js'
import type { Session } from '@supabase/supabase-js'

const mode = import.meta.env.VITE_TRACKER_MODE || (import.meta.env.PROD ? 'hosted' : 'local')
export const hosted = mode === 'hosted'
const url = import.meta.env.VITE_SUPABASE_URL || ''
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
export const authConfigurationError = !['local', 'hosted'].includes(mode)
  ? 'This site has an invalid sign-in configuration.'
  : hosted && (!url.startsWith('https://') || !key)
    ? 'Sign-in is not configured for this site yet.' : ''

export const supabase = hosted && !authConfigurationError
  ? createClient(url, key, { auth: { flowType: 'pkce', detectSessionInUrl: false, persistSession: true, autoRefreshToken: true } })
  : null

type AuthState = { session: Session | null; loading: boolean; recovering: boolean; error: string }
let state: AuthState = { session: null, loading: hosted && !authConfigurationError, recovering: false, error: '' }
let epoch = 0
const listeners = new Set<() => void>()
function update(next: Partial<AuthState>) {
  const previousId = state.session?.user.id
  state = { ...state, ...next }
  if (previousId !== state.session?.user.id) epoch++
  listeners.forEach(listener => listener())
}
export const getAuthState = () => state
export function subscribeAuth(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
export function authRedirect(recovery = false) {
  return `${window.location.origin}${window.location.pathname}${recovery ? '?auth=recovery' : ''}`
}
export function finishRecovery() {
  window.history.replaceState({}, '', window.location.pathname)
  update({ recovering: false, error: '' })
}

// Initialize once, outside React's StrictMode effect replay. Handle PKCE codes
// explicitly so expired links produce a visible error instead of a blank page.
if (supabase) {
  const client = supabase
  let initializing = true
  client.auth.onAuthStateChange((event, session) => {
    update({ session, ...(initializing ? {} : { loading: false }),
      ...(event === 'PASSWORD_RECOVERY' ? { recovering: true } : {}),
      ...(event === 'SIGNED_IN' ? { error: '' } : {}),
      ...(event === 'SIGNED_OUT' ? { recovering: false } : {}),
    })
  })
  void (async () => {
    try {
      const params = new URLSearchParams(window.location.search)
      const fragment = new URLSearchParams(window.location.hash.slice(1))
      if (params.has('error') || fragment.has('error')) {
        window.history.replaceState({}, '', window.location.pathname)
        throw new Error('This email link is invalid or expired. Please request a new one.')
      }
      if (params.has('code')) {
        const recovering = params.get('auth') === 'recovery'
        const { data, error } = await client.auth.exchangeCodeForSession(params.get('code')!)
        window.history.replaceState({}, '', authRedirect(recovering))
        if (error) throw new Error('This email link is invalid or expired. Open a new link in the same browser that requested it.')
        update({ session: data.session, recovering })
      } else {
        const { data, error } = await client.auth.getSession()
        if (error) throw error
        update({ session: data.session, recovering: !!data.session && params.get('auth') === 'recovery' })
      }
    } catch (error) {
      update({ error: error instanceof Error ? error.message : 'Could not restore your session.' })
    } finally {
      initializing = false
      update({ loading: false })
    }
  })()
}

export async function apiIdentity() {
  const requestEpoch = epoch
  if (!hosted) return { token: null, epoch: requestEpoch }
  if (!supabase || !state.session) throw new Error('Please sign in to continue.')
  const { data, error } = await supabase.auth.getSession()
  if (requestEpoch !== epoch) throw new Error('Your signed-in account changed. Please try again.')
  if (error || !data.session) throw new Error('Your session expired. Please sign in again.')
  return { token: data.session.access_token, epoch: requestEpoch }
}
export function assertCurrentIdentity(requestEpoch: number) {
  if (requestEpoch !== epoch) throw new Error('Your signed-in account changed. Please try again.')
}
export function rejectSession() {
  update({ session: null, loading: true, error: 'Your session expired. Please sign in again.' })
  // Never await an SDK operation inside its own auth-event callback.
  void (async () => {
    try { await supabase?.auth.signOut({ scope: 'local' }) }
    catch { /* The private view is already cleared; allow a fresh sign-in. */ }
    finally { update({ loading: false }) }
  })()
}
