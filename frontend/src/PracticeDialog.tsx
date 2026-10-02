import useModalDialog from './useModalDialog'
import { createElement, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { masteryLevels, request } from './api'
import type { PracticePick, ProblemSummary, StatementNode } from './api'

const allowedTags = new Set(['p', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 'pre', 'code', 'ul', 'ol', 'li', 'sup', 'sub', 'br', 'hr', 'h2', 'h3', 'h4', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'blockquote'])
function renderStatement(nodes: StatementNode[]): ReactNode[] {
  return nodes.map((node, index) => {
    if (typeof node === 'string') return node
    if (node.tag === 'img') {
      try {
        const url = new URL(node.src ?? '')
        if (url.protocol !== 'https:' || url.username || url.password || !['assets.leetcode.com', 'leetcode.com', 's3-lc-upload.s3.amazonaws.com'].includes(url.hostname)) return null
      } catch { return null }
      return <img key={index} src={node.src!} alt="Problem diagram" referrerPolicy="no-referrer" />
    }
    if (!allowedTags.has(node.tag)) return null
    // React escapes text; fetched HTML is never inserted with innerHTML.
    return createElement(node.tag, { key: index }, ...renderStatement(node.children))
  })
}

function today() {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export default function PracticeDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const dialog = useModalDialog()
  const active = useRef(true)
  const pending = useRef(false)
  const initialRequest = useRef<Promise<PracticePick> | null>(null)
  const [pick, setPick] = useState<PracticePick | null>(null)
  const [details, setDetails] = useState<ProblemSummary | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [showAttempt, setShowAttempt] = useState(false)
  const [busy, setBusy] = useState<'pick' | 'statement' | 'details' | 'save' | null>('pick')
  const [error, setError] = useState('')
  const [pastedText, setPastedText] = useState('')

  useEffect(() => {
    active.current = true
    // StrictMode replays effects; share one request for the initial draw.
    initialRequest.current ??= request<PracticePick>('/practice/random', undefined, 'POST')
    initialRequest.current.then(data => { if (active.current) setPick(data) })
      .catch(failure => { if (active.current) setError(failure instanceof Error ? failure.message : 'Could not pick a problem.') })
      .finally(() => { if (active.current) setBusy(null) })
    return () => { active.current = false }
  }, [])

  async function run(operation: 'pick' | 'statement' | 'details' | 'save', action: () => Promise<void>) {
    if (pending.current || busy !== null) return
    pending.current = true; setBusy(operation); setError('')
    try { await action() }
    catch (failure) { if (active.current) setError(failure instanceof Error ? failure.message : 'Please try again.') }
    finally { pending.current = false; if (active.current) setBusy(null) }
  }
  function pickAnother() {
    void run('pick', async () => {
      setPick(null); setDetails(null); setShowDetails(false); setShowAttempt(false); setPastedText('')
      const data = await request<PracticePick>('/practice/random', undefined, 'POST')
      if (active.current) setPick(data)
    })
  }
  function reveal() {
    if (!pick) return
    if (showDetails) { setShowDetails(false); return }
    if (details) { setShowDetails(true); return }
    void run('details', async () => {
      const data = await request<ProblemSummary>(`/problems/${pick.problem_number}/summary`)
      if (active.current) { setDetails(data); setShowDetails(true) }
    })
  }
  function retryStatement() {
    if (!pick) return
    void run('statement', async () => {
      const data = await request<PracticePick>(`/practice/${pick.problem_number}/statement/load`, undefined, 'POST')
      if (active.current) setPick(data)
    })
  }
  async function saveStatement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!pick) return
    await run('statement', async () => {
      const data = await request<PracticePick>(`/practice/${pick.problem_number}/statement`, { text: pastedText }, 'PUT')
      if (active.current) { setPick(data); setShowDetails(false); setPastedText('') }
    })
  }
  async function saveAttempt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!pick) return
    const data = new FormData(event.currentTarget)
    await run('save', async () => {
      await request('/reviews', {
        problem_number: pick.problem_number,
        reviewed_on: String(data.get('reviewed_on')),
        mastery_level: String(data.get('mastery_level')),
      })
      if (active.current) onSaved()
    })
  }

  return <dialog ref={dialog} className="practice-dialog" aria-labelledby="practice-title" onCancel={event => {
    event.preventDefault()
    if (busy !== 'save' && busy !== 'statement') onClose()
  }}>
    <div className="flex shrink-0 items-start justify-between gap-4 border-b border-line pb-4">
      <div><p className="eyebrow">Blind practice</p><h2 id="practice-title" className="text-2xl font-semibold mt-2">Practice problem</h2></div>
      <button className="icon-button" aria-label="Close practice" disabled={busy === 'save' || busy === 'statement'} onClick={onClose}>×</button>
    </div>
    <div className="practice-content">
      {busy === 'pick' && <p role="status" className="py-12 text-center text-sm text-muted">Picking a due problem and loading its statement…</p>}
      {pick?.statement && <article className="problem-statement" aria-label="Problem statement">{renderStatement(pick.statement)}</article>}
      {pick && !pick.statement && <div className="space-y-4 py-4">
        <p role="status" className="text-sm leading-6 text-muted">{pick.statement_error}</p>
        <button className="secondary" disabled={busy !== null} onClick={retryStatement}>{busy === 'statement' ? 'Loading…' : 'Retry statement'}</button>
        <form onSubmit={saveStatement} className="space-y-3 border-t border-line pt-4">
          <p className="text-xs leading-5 text-muted">Reveal details to find the problem, then paste its statement, examples, and constraints once. Future picks will use the saved copy.</p>
          <label>Paste problem statement<textarea rows={7} value={pastedText} onChange={event => setPastedText(event.target.value)} disabled={busy !== null} required maxLength={100000} /></label>
          <button className="primary" disabled={busy !== null || !pastedText.trim()}>Save statement</button>
        </form>
      </div>}
      {showDetails && details && <section className="practice-details" aria-label="Revealed details">
        <h3 className="font-semibold">#{details.number} {details.name}</h3>
        <p className="mt-2 text-sm text-muted">{details.difficulty} · {details.topic} · {details.mastery_level ?? 'Not reviewed'} · {details.attempts} {details.attempts === 1 ? 'attempt' : 'attempts'}</p>
        <p className="mt-2 text-sm text-muted">Next review: {details.next_review ?? 'Not scheduled'}{details.archived ? ' · Archived' : ''}</p>
        {pick?.leetcode_url && <a className="text-button inline-block mt-3" href={pick.leetcode_url} target="_blank" rel="noreferrer">Open on LeetCode ↗</a>}
        {details.notes && <details className="mt-3"><summary className="text-button cursor-pointer">Show notes</summary><p className="mt-2 whitespace-pre-wrap break-words text-sm text-muted">{details.notes}</p></details>}
      </section>}
      {showAttempt && pick?.statement && <form onSubmit={saveAttempt} className="space-y-4 border-t border-line pt-5 mt-5">
        <h3 className="font-semibold">Record this attempt</h3>
        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={busy !== null}>
          <label>Completion date<input name="reviewed_on" type="date" defaultValue={today()} required /></label>
          <label>Mastery level<select name="mastery_level" defaultValue="" required><option value="" disabled>How did this attempt go?</option>{masteryLevels.map(level => <option key={level}>{level}</option>)}</select></label>
        </fieldset>
        <div className="flex justify-end gap-3">
          <button type="button" className="secondary" disabled={busy !== null} onClick={() => setShowAttempt(false)}>Cancel attempt</button>
          <button className="primary" disabled={busy !== null}>{busy === 'save' ? 'Saving…' : 'Save attempt'}</button>
        </div>
      </form>}
      {error && <p role="alert" className="error mt-4">{error}</p>}
    </div>
    <div className="flex shrink-0 flex-wrap justify-end gap-3 border-t border-line pt-4 mt-4">
      <button className="secondary mr-auto" disabled={busy !== null} onClick={pickAnother}>{pick ? 'Pick another' : 'Try again'}</button>
      {pick && <button className="secondary" disabled={busy !== null} onClick={reveal}>{busy === 'details' ? 'Loading…' : showDetails ? 'Hide details' : 'Reveal details'}</button>}
      {pick?.statement && <button className="primary" disabled={busy !== null || showAttempt} onClick={() => setShowAttempt(true)}>Record attempt</button>}
    </div>
  </dialog>
}
