import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Session } from '@supabase/supabase-js'
import { authRedirect, dismissAuthError, getAuthState, markGuestUpgrade, refreshUpgradeUser, supabase } from './auth'

export default function GuestUpgrade({ session, sessionError, onBack }: {
  session: Session; sessionError: string; onBack: () => void;
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const verified = session.user.is_anonymous === false && !!session.user.email_confirmed_at
  const pending = getAuthState().upgradeUserId === session.user.id

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!supabase || busy) return
    const data = new FormData(event.currentTarget)
    const owner = session.user.id
    setBusy(true); setError(''); setNotice(''); dismissAuthError()
    try {
      if (getAuthState().session?.user.id !== owner) throw new Error('Your account changed. Return to your workspace before continuing.')
      if (verified) {
        const password = String(data.get('password') || '')
        if (password !== data.get('confirmation')) throw new Error('The passwords do not match.')
        const user = await refreshUpgradeUser(owner)
        if (user.is_anonymous || !user.email_confirmed_at) throw new Error('Confirm your email before choosing a password.')
        const result = await supabase.auth.updateUser({ password })
        if (result.error) throw result.error
        if (result.data.user.id !== owner) throw new Error('Your account changed. Please reload before continuing.')
        await refreshUpgradeUser(owner)
        markGuestUpgrade(null)
        onBack()
      } else {
        const email = String(data.get('email') || '').trim()
        markGuestUpgrade(owner)
        const result = await supabase.auth.updateUser({ email }, { emailRedirectTo: authRedirect() })
        if (result.error) {
          if (!pending) markGuestUpgrade(null)
          if (result.error.code === 'email_exists' || result.error.code === 'user_already_exists') throw new Error('This email already belongs to an account. Use a different email to keep this guest progress. Signing into an existing account will not transfer it.')
          if (result.error.code === 'manual_linking_disabled') throw new Error('Account upgrades are not enabled yet. Your guest workspace is still available.')
          throw result.error
        }
        if (result.data.user.id !== owner) throw new Error('Your account changed. Please reload before continuing.')
        setNotice('Check your email and open the confirmation link in this browser. Then choose a password. Your progress stays in this workspace.')
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not finish account setup. Please try again.')
    } finally { setBusy(false) }
  }

  async function checkConfirmation() {
    if (busy) return
    setBusy(true); setError(''); setNotice(''); dismissAuthError()
    try {
      const user = await refreshUpgradeUser(session.user.id)
      if (user.is_anonymous || !user.email_confirmed_at) setNotice('Your email is not confirmed yet. Open the confirmation link, then check again.')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not check confirmation. Please try again.')
    } finally { setBusy(false) }
  }

  return <main className="auth-shell"><section className="auth-card" aria-labelledby="upgrade-title">
    <p className="eyebrow">LeetCode review tracker</p>
    <h1 id="upgrade-title" className="text-2xl font-semibold mt-3">{verified ? 'Choose your password' : 'Create an account and keep your progress'}</h1>
    <p className="text-muted mt-3 mb-6">{verified ? 'Your email is confirmed. Set a password to sign in again from any device. Your problems and review history stay with this account.' : 'Create a new account using an email you have not used here before. Confirm your email first, then choose a password. Your problems, notes, and review history stay with you.'}</p>
    <form key={verified ? 'password' : 'email'} onSubmit={submit}><fieldset disabled={busy} className="space-y-4">
      {verified ? <>
        <p className="text-muted">{session.user.email}</p>
        <label>Password<input name="password" type="password" minLength={8} autoComplete="new-password" required /></label>
        <label>Confirm password<input name="confirmation" type="password" minLength={8} autoComplete="new-password" required /></label>
      </> : <label>Email<input name="email" type="email" autoComplete="email" defaultValue={session.user.new_email || ''} required /></label>}
      <button className="primary w-full" disabled={busy}>{busy ? 'Please wait…' : verified ? 'Save password' : 'Send confirmation link'}</button>
    </fieldset></form>
    {(error || sessionError) && <p role="alert" className="error mt-4">{error || sessionError}</p>}
    {notice && <p role="status" className="text-muted mt-4">{notice}</p>}
    {!verified && pending && !notice && <p role="status" className="text-muted mt-4">Waiting for email confirmation. Open the link in this browser, or request another link above.</p>}
    <div className="flex flex-wrap gap-4 mt-5">
      {!verified && pending && <button className="quiet-button" disabled={busy} onClick={() => void checkConfirmation()}>Check confirmation</button>}
      <button className="quiet-button" disabled={busy} onClick={onBack}>Back to workspace</button>
    </div>
  </section></main>
}
