import { useState, useSyncExternalStore } from 'react'
import type { FormEvent } from 'react'
import App from './App'
import GuestUpgrade from './GuestUpgrade'
import { authConfigurationError, authRedirect, dismissAuthError, finishRecovery, getAuthState, hosted, markGuestUpgrade, subscribeAuth, supabase } from './auth'

export default function AuthGate() {
  const { session, loading, recovering, error: sessionError, upgradeUserId } = useSyncExternalStore(subscribeAuth, getAuthState)
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showAuth, setShowAuth] = useState(false)
  const [showGuestInfo, setShowGuestInfo] = useState(false)
  const [showUpgrade, setShowUpgrade] = useState(!!upgradeUserId)
  const isGuest = session?.user.is_anonymous === true
  const upgrading = !!session && upgradeUserId === session.user.id

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
        markGuestUpgrade(null)
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
      markGuestUpgrade(null)
      finishRecovery()
      setMode('signin')
      setShowAuth(false)
    } catch { setError('Could not sign out. Please try again.') }
    finally { setBusy(false) }
  }

  if (authConfigurationError) return <main className="auth-shell"><p role="alert" className="error">{authConfigurationError}</p></main>
  if (!hosted) return <App />
  if (loading) return <main className="auth-shell"><p role="status">Restoring your session…</p></main>
  if (session && !recovering && showUpgrade && (isGuest || upgrading)) return <GuestUpgrade session={session} sessionError={sessionError} onBack={() => { setShowUpgrade(false); setShowAuth(false); dismissAuthError(); setError(''); setNotice('') }} />
  const createAccountButton = <button className="account-button account-button-featured" disabled={busy} onClick={() => {
    setShowGuestInfo(false); setError(''); setNotice(''); dismissAuthError()
    if (isGuest || upgrading) { setShowUpgrade(true); setShowAuth(false) }
    else { setMode('signup'); setShowAuth(true); setShowUpgrade(false) }
  }}>{upgrading ? 'Finish account setup' : 'Create account'}</button>
  const signInButton = <button className="account-button" disabled={busy} onClick={() => { setMode('signin'); setShowAuth(true); setShowGuestInfo(false); setError(''); setNotice('') }}>Sign in</button>
  const feedback = (error || sessionError) && <p role="alert" className="error mt-5">{error || sessionError}</p>
  if (session && !recovering && (!isGuest || !showAuth)) return <App key={session.user.id} accountFeedback={feedback} accountControls={isGuest ? <>
    <div className="guest-session">
      <button className="account-button guest-status" aria-expanded={showGuestInfo} aria-controls="guest-session-info" onClick={() => setShowGuestInfo(!showGuestInfo)}>Guest</button>
      {showGuestInfo && <p id="guest-session-info" className="guest-info">Your progress is saved for this browser. Clearing browser data or signing into another account loses access to it.</p>}
    </div>
    {createAccountButton}
    {signInButton}
  </> : <>
    <span className="account-email">{session.user.email}</span>{upgrading ? createAccountButton : <button className="account-button" disabled={busy} onClick={() => void signOut()}>{busy ? 'Signing out…' : 'Sign out'}</button>}
  </>} />

  if (!showAuth && !recovering && !sessionError) return <App key="sample" preview onStartGuest={() => { if (!busy) void startGuest() }} accountFeedback={feedback} accountControls={<>
    <button className="account-button" disabled={busy} onClick={() => void startGuest()}>{busy ? 'Starting…' : 'Guest'}</button>
    {createAccountButton}
    {signInButton}
  </>} />

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
        {recovering ? <button className="quiet-button" disabled={busy} onClick={() => void signOut()}>Cancel and sign out</button> : isGuest ? <>
          {createAccountButton}
          <button className="quiet-button" disabled={busy} onClick={() => { setShowAuth(false); setError(''); setNotice('') }}>Back to guest workspace</button>
        </> : <>
          <button className="quiet-button" disabled={busy} onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError(''); setNotice('') }}>{mode === 'signin' ? 'Create an account' : 'Back to sign in'}</button>
          {mode === 'signin' && <button className="quiet-button" disabled={busy} onClick={() => { setMode('reset'); setError(''); setNotice('') }}>Forgot password?</button>}
        </>}
      </div>
      {!recovering && !isGuest && <button className="text-button mt-5" disabled={busy} onClick={() => { dismissAuthError(); setShowAuth(false); setError(''); setNotice('') }}>Explore sample tracker</button>}
    </section>
  </main>
}
