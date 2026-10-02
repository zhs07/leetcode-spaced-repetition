import { useState, useSyncExternalStore } from 'react'
import type { FormEvent } from 'react'
import App from './App'
import { authConfigurationError, authRedirect, dismissAuthError, finishRecovery, getAuthState, hosted, subscribeAuth, supabase } from './auth'

export default function AuthGate() {
  const { session, loading, recovering, error: sessionError } = useSyncExternalStore(subscribeAuth, getAuthState)
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showAuth, setShowAuth] = useState(false)
  const isGuest = session?.user.is_anonymous === true

  async function startGuest() {
    if (!supabase || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await supabase.auth.signInAnonymously()
      if (result.error) {
        if (result.error.code === 'anonymous_provider_disabled') throw new Error('Guest access is not enabled yet. You can still explore the sample tracker or sign in.')
        throw result.error
      }
      if (!result.data.session) throw new Error('Could not start your guest workspace. Please try again.')
      setShowAuth(false)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not start your guest workspace. Please try again.')
    } finally { setBusy(false) }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!supabase || busy) return
    const data = new FormData(event.currentTarget)
    const email = String(data.get('email') || '').trim()
    const password = String(data.get('password') || '')
    setBusy(true); setError(''); setNotice('')
    try {
      if (recovering) {
        if (password !== data.get('confirmation')) throw new Error('The passwords do not match.')
        const result = await supabase.auth.updateUser({ password })
        if (result.error) throw result.error
        finishRecovery()
      } else if (mode === 'signin') {
        const result = await supabase.auth.signInWithPassword({ email, password })
        if (result.error) throw result.error
        setShowAuth(false)
      } else if (mode === 'signup') {
        const result = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: authRedirect() } })
        if (result.error) throw result.error
        setNotice('Check your email to confirm your account. Open the link in this browser. If you already have an account, sign in or reset your password.')
      } else {
        const result = await supabase.auth.resetPasswordForEmail(email, { redirectTo: authRedirect(true) })
        if (result.error) throw result.error
        setNotice('If an account exists for this email, a reset link is on its way. Open it in this browser.')
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Unable to complete sign-in. Please try again.')
    } finally { setBusy(false) }
  }
  async function signOut() {
    if (!supabase || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await supabase.auth.signOut({ scope: 'local' })
      if (result.error) throw result.error
      finishRecovery()
      setMode('signin')
      setShowAuth(false)
    } catch { setError('Could not sign out. Please try again.') }
    finally { setBusy(false) }
  }

  if (authConfigurationError) return <main className="auth-shell"><p role="alert" className="error">{authConfigurationError}</p></main>
  if (!hosted) return <App />
  if (loading) return <main className="auth-shell"><p role="status">Restoring your session…</p></main>
  if (session && !recovering && (!isGuest || !showAuth)) return <>
    <div className="account-bar">
      {isGuest ? <><span>Guest workspace · return using this browser. Clearing browser data loses access.</span><button className="quiet-button" disabled={busy} onClick={() => { setMode('signin'); setShowAuth(true); setError(''); setNotice('') }}>Sign in</button></> : <><span>{session.user.email}</span><button className="quiet-button" disabled={busy} onClick={() => void signOut()}>{busy ? 'Signing out…' : 'Sign out'}</button></>}
      {(error || sessionError) && <p role="alert" className="error">{error || sessionError}</p>}
    </div>
    <App key={session.user.id} />
  </>

  if (!showAuth && !recovering && !sessionError) return <>
    <div className="preview-bar">
      <div><p className="eyebrow">Sample tracker</p><p className="text-muted mt-2">Explore these examples, or try a private guest workspace. No account details needed.</p><p className="text-faint mt-2">Filters and notes work here. Action buttons start a fresh guest workspace.</p></div>
      <div className="flex flex-wrap gap-3"><button className="primary" disabled={busy} onClick={() => void startGuest()}>{busy ? 'Starting guest…' : 'Try as guest'}</button><button className="secondary" disabled={busy} onClick={() => { setShowAuth(true); setError(''); setNotice('') }}>Sign in</button></div>
      {error && <p role="alert" className="error preview-error">{error}</p>}
    </div>
    <App key="sample" preview onStartGuest={() => { if (!busy) void startGuest() }} />
  </>

  const title = recovering ? 'Choose a new password' : mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : 'Sign in to your review space'
  return <main className="auth-shell">
    <section className="auth-card" aria-labelledby="auth-title">
      <p className="eyebrow">LeetCode review tracker</p>
      <h1 id="auth-title" className="text-2xl font-semibold mt-3">{title}</h1>
      <p className="text-muted mt-3 mb-6">{recovering ? 'Save a new password to return to your practice.' : isGuest ? "Signing in opens your account and replaces this guest session. Guest progress will not transfer, and you will lose access to it. Go back to keep practicing as a guest." : 'Keep your problems, notes, and review history in your own account.'}</p>
      <form key={recovering ? 'recovery' : mode} onSubmit={submit}>
        <fieldset disabled={busy} className="space-y-4">
          {!recovering && <label>Email<input name="email" type="email" autoComplete="email" required /></label>}
          {(recovering || mode !== 'reset') && <label>{recovering ? 'New password' : 'Password'}<input name="password" type="password" minLength={mode === 'signin' && !recovering ? 1 : 8} autoComplete={mode === 'signin' && !recovering ? 'current-password' : 'new-password'} required /></label>}
          {recovering && <label>Confirm new password<input name="confirmation" type="password" minLength={8} autoComplete="new-password" required /></label>}
          <button className="primary w-full" disabled={busy}>{busy ? 'Please wait…' : recovering ? 'Save new password' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
        </fieldset>
      </form>
      {(error || sessionError) && <p role="alert" className="error mt-4">{error || sessionError}</p>}
      {notice && <p role="status" className="text-muted mt-4">{notice}</p>}
      <div className="flex flex-wrap gap-4 mt-5">
        {recovering ? <button className="quiet-button" disabled={busy} onClick={() => void signOut()}>Cancel and sign out</button> : isGuest ? <button className="quiet-button" disabled={busy} onClick={() => { setShowAuth(false); setError(''); setNotice('') }}>Back to guest workspace</button> : <>
          <button className="quiet-button" disabled={busy} onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError(''); setNotice('') }}>{mode === 'signin' ? 'Create an account' : 'Back to sign in'}</button>
          {mode === 'signin' && <button className="quiet-button" disabled={busy} onClick={() => { setMode('reset'); setError(''); setNotice('') }}>Forgot password?</button>}
        </>}
      </div>
      {!recovering && !isGuest && <button className="text-button mt-5" disabled={busy} onClick={() => { dismissAuthError(); setShowAuth(false); setError(''); setNotice('') }}>Explore sample tracker</button>}
    </section>
  </main>
}
