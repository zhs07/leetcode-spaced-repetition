import { Fragment, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { masteryLevels, request } from './api'
import type { ProblemSummary } from './api'

function localToday() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
function displayDate(value: string) {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
// Compare calendar dates, not elapsed local hours (which vary at daylight saving).
function calendarDay(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return Date.UTC(year, month - 1, day) / 86400000
}
function ReviewDate({ value, today }: { value: string | null; today: string }) {
  if (!value) return <span className="text-slate-400">Not scheduled</span>
  const days = calendarDay(value) - calendarDay(today)
  const tone = days <= 0 ? 'review-due' : days < 7 ? 'review-soon' : 'review-later'
  const label = days < 0 ? `${-days}d overdue` : days === 0 ? 'Due today' : `In ${days}d`
  return <span className={`review-date ${tone}`}>
    <time dateTime={value}>{displayDate(value)}</time>
    <span className="review-countdown">{label}</span>
  </span>
}
const masteryColors: Record<string, string> = {
  'Learned Solution': 'mastery-learned',
  'Partial Recall': 'mastery-partial',
  'Solved with Struggle': 'mastery-struggle',
  'Solved Independently': 'mastery-independent',
  'Mastered': 'mastery-mastered',
}
type Editor = { kind: 'problem' } | { kind: 'attempt'; problem: ProblemSummary }

function EntryDialog({ editor, onClose, onSaved }: { editor: Editor; onClose: () => void; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [saving, setSaving] = useState(false)
  const [includeFirstAttempt, setIncludeFirstAttempt] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => element.close()
  }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    const data = new FormData(event.currentTarget)
    const value = (name: string) => String(data.get(name) ?? '')
    setSaving(true)
    setError('')
    try {
      if (editor.kind === 'problem') {
        await request('/problems', { number: Number(value('number')), name: value('name').trim(), difficulty: value('difficulty'), topic: value('topic').trim(), notes: value('notes'),
          ...(includeFirstAttempt ? { first_attempt: { reviewed_on: value('reviewed_on'), mastery_level: value('mastery_level') } } : {}),
        })
      } else {
        await request('/reviews', { problem_number: editor.problem.number, reviewed_on: value('reviewed_on'), mastery_level: value('mastery_level') })
      }
      onSaved()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not save. Please try again.')
      setSaving(false)
    }
  }
  return <dialog ref={dialog} aria-labelledby="dialog-title" onCancel={event => { event.preventDefault(); if (!saving) onClose() }}>
    <form onSubmit={submit} className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div><p className="eyebrow">{editor.kind === 'problem' ? 'Grow your practice' : `Problem #${editor.problem.number}`}</p>
          <h2 id="dialog-title" className="text-2xl font-semibold mt-2">{editor.kind === 'problem' ? 'Add a problem' : 'Record an attempt'}</h2>
          {editor.kind === 'attempt' && <p className="mt-2 text-slate-500">{editor.problem.name}</p>}</div>
        <button type="button" className="icon-button" aria-label="Close form" disabled={saving} onClick={onClose}>×</button>
      </div>
      <fieldset disabled={saving} className="space-y-4">
        {editor.kind === 'problem' ? <>
          <div className="grid grid-cols-2 gap-4">
            <label>Problem number<input name="number" type="number" min="1" step="1" required autoFocus placeholder="e.g. 1" /></label>
            <label>Difficulty<select name="difficulty" defaultValue="Easy"><option>Easy</option><option>Medium</option><option>Hard</option></select></label>
          </div>
          <label>Name<input name="name" required pattern=".*\S.*" placeholder="e.g. Two Sum" /></label>
          <label>Topic<input name="topic" required pattern=".*\S.*" placeholder="e.g. Arrays & Hashing" /></label>
          <label>Notes <span className="font-normal text-slate-400">(optional)</span><textarea name="notes" rows={3} placeholder="Your approach, insights, or a reminder…" /></label>
          <p className="text-sm text-slate-500">Notes stay hidden until you choose to reveal them.</p>
          <div className="border-t border-slate-100 pt-4">
            <label className="flex items-center gap-3">
              <input type="checkbox" className="m-0 h-4 w-4 accent-indigo-600" checked={includeFirstAttempt} onChange={event => setIncludeFirstAttempt(event.target.checked)} aria-describedby="first-attempt-help" />
              Record my first attempt
            </label>
            <p id="first-attempt-help" className="mt-2 text-sm text-slate-500">Uncheck to save this problem for later without recording an attempt.</p>
          </div>
        </> : null}
        {(editor.kind === 'attempt' || includeFirstAttempt) && <>
          <label>Completion date<input type="date" name="reviewed_on" defaultValue={localToday()} required autoFocus={editor.kind === 'attempt'} /></label>
          <label>Mastery level<select name="mastery_level" required defaultValue=""><option value="" disabled>How did this attempt go?</option>{masteryLevels.map(level => <option key={level}>{level}</option>)}</select></label>
          <p className="text-sm leading-6 text-slate-500">Choose based on this attempt. Your next review is scheduled from its completion date.</p>
        </>}
      </fieldset>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="flex justify-end gap-3 pt-2">
        <button type="button" className="secondary" disabled={saving} onClick={onClose}>Cancel</button>
        <button className="primary" disabled={saving}>{saving ? 'Saving…' : editor.kind === 'problem' ? 'Add problem' : 'Save attempt'}</button>
      </div>
    </form>
  </dialog>
}

export default function App() {
  const [today, setToday] = useState(localToday)
  useEffect(() => {
    const update = () => setToday(localToday())
    const timer = window.setInterval(update, 30000)
    window.addEventListener('focus', update)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', update) }
  }, [])
  const [problems, setProblems] = useState<ProblemSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editor, setEditor] = useState<Editor | null>(null)
  const [visibleNotes, setVisibleNotes] = useState<Set<number>>(new Set())
  const [view, setView] = useState('all')
  const [topic, setTopic] = useState('')
  const [mastery, setMastery] = useState('')
  const [sortBy, setSortBy] = useState('next_review')
  const [direction, setDirection] = useState('asc')
  const topics = [...new Set(problems.map(problem => problem.topic))].sort((a, b) => a.localeCompare(b))
  const shownProblems = problems.filter(problem =>
    (view === 'all' || (view === 'due' ? problem.next_review !== null && problem.next_review <= today : problem.mastery_level === null)) &&
    (!topic || problem.topic === topic) && (!mastery || problem.mastery_level === mastery)
  ).sort((a, b) => {
    const value = (problem: ProblemSummary): string | number | null => {
      switch (sortBy) {
        case 'attempts': return problem.attempts
        case 'difficulty': return ['Easy', 'Medium', 'Hard'].indexOf(problem.difficulty)
        case 'mastery': return problem.mastery_level === null ? null : masteryLevels.indexOf(problem.mastery_level)
        case 'topic': return problem.topic
        default: return problem.next_review
      }
    }
    const left = value(a), right = value(b)
    // Keep unscheduled/unreviewed entries last in either direction.
    if (left === null) return right === null ? a.number - b.number : 1
    if (right === null) return -1
    const comparison = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right))
    return comparison * (direction === 'asc' ? 1 : -1) || a.number - b.number
  })
  function clearFilters() { setView('all'); setTopic(''); setMastery('') }
  const latestRequest = useRef(0)
  async function refresh() {
    const id = ++latestRequest.current
    setLoading(true); setError('')
    try { const data = await request<ProblemSummary[]>('/problems/summary'); if (id === latestRequest.current) setProblems(data) }
    catch (failure) { if (id === latestRequest.current) setError(failure instanceof Error ? failure.message : 'Could not load your problems.') }
    finally { if (id === latestRequest.current) setLoading(false) }
  }
  useEffect(() => {
    let active = true
    request<ProblemSummary[]>('/problems/summary')
      .then(data => { if (active) setProblems(data) })
      .catch(failure => { if (active) setError(failure instanceof Error ? failure.message : 'Could not load your problems.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  function toggleNotes(number: number) {
    setVisibleNotes(previous => { const next = new Set(previous); if (next.has(number)) next.delete(number); else next.add(number); return next })
  }
  return <main className="mx-auto max-w-[1440px] px-5 py-12 sm:px-10 sm:py-16">
    <header className="text-center mb-12">
      <p className="eyebrow mb-3">A little practice. Lasting recall.</p>
      <h1 className="text-5xl font-semibold tracking-tight text-slate-900">LeetCode<span className="text-indigo-500">.</span></h1>
      <p className="mt-4 text-slate-500">Your practice, one attempt at a time.</p>
      <button className="primary mt-6" onClick={() => setEditor({ kind: 'problem' })}><span aria-hidden="true">＋ </span>Add problem</button>
    </header>
    <section aria-labelledby="table-title" className="table-card">
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5 border-b border-slate-100">
        <div className="flex items-center gap-3"><h2 id="table-title" className="font-semibold">Your problems</h2><span className="count">{problems.length}</span></div>
        <button className="text-button" onClick={() => { setNotice(''); void refresh() }} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>
      <div className="border-b border-slate-100 bg-slate-50/50 px-6 py-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-xs text-slate-500">Show<select value={view} onChange={event => setView(event.target.value)}><option value="all">All problems</option><option value="due">Due & overdue</option><option value="unreviewed">Not reviewed</option></select></label>
          <label className="text-xs text-slate-500">Filter by topic<select value={topic} onChange={event => setTopic(event.target.value)}><option value="">All topics</option>{topics.map(item => <option key={item}>{item}</option>)}</select></label>
          <label className="text-xs text-slate-500">Filter by mastery<select value={mastery} onChange={event => setMastery(event.target.value)}><option value="">All mastery levels</option>{masteryLevels.map(item => <option key={item}>{item}</option>)}</select></label>
          <label className="text-xs text-slate-500">Sort by<select value={sortBy} onChange={event => setSortBy(event.target.value)}><option value="next_review">Next review</option><option value="attempts">Attempts</option><option value="difficulty">Difficulty</option><option value="mastery">Mastery level</option><option value="topic">Topic</option></select></label>
          <label className="text-xs text-slate-500">Direction<select value={direction} onChange={event => setDirection(event.target.value)}><option value="asc">Ascending ↑</option><option value="desc">Descending ↓</option></select></label>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500" role="status">Showing {shownProblems.length} of {problems.length} problems</p>
          {(view !== 'all' || topic || mastery) && <button className="text-button" onClick={clearFilters}>Clear filters</button>}
        </div>
      </div>
      {notice && <p role="status" className="px-6 pt-4 text-sm text-emerald-700">{notice}</p>}
      {error && <div role="alert" className="error m-5">{error} {problems.length > 0 && 'Showing the last loaded data.'} <button className="underline font-semibold" onClick={() => void refresh()}>Try again</button></div>}
      {loading && problems.length === 0 ? <p role="status" className="empty-state">Loading your practice history…</p> :
        problems.length === 0 && !error ? <div className="empty-state">
          <div className="empty-icon" aria-hidden="true">&lt;/&gt;</div><h3 className="text-xl font-semibold text-slate-800 mt-5">A fresh start for your practice</h3>
          <p className="mt-2">Add a problem with your first attempt, or save it to practice later.</p>
          <button className="text-button mt-5" onClick={() => setEditor({ kind: 'problem' })}>Add your first problem →</button>
        </div> : problems.length > 0 && shownProblems.length === 0 ? <div className="empty-state"><h3 className="text-lg font-semibold text-slate-700">No matching problems</h3><p className="mt-2">Try another filter combination to see more of your list.</p><button className="text-button mt-4" onClick={clearFilters}>Show all problems</button></div> : problems.length > 0 && <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Problems table; scroll horizontally on small screens">
          <table><thead><tr>{['Number', 'Name', 'Difficulty', 'Topic', 'Mastery Level', 'Next review', 'Attempts', 'Notes', 'Action'].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
            <tbody>{shownProblems.map(problem => <Fragment key={problem.number}><tr>
              <td className="text-slate-400 font-mono">{problem.number}</td><th scope="row" className="problem-name">{problem.name}</th>
              <td><span className={`badge ${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span></td><td className="text-slate-500">{problem.topic}</td>
              <td><span className={problem.mastery_level ? `mastery-badge ${masteryColors[problem.mastery_level] ?? ''}` : 'text-slate-400'}>{problem.mastery_level ?? 'Not reviewed'}</span></td>
              <td className="whitespace-nowrap text-slate-600"><ReviewDate value={problem.next_review} today={today} /></td>
              <td className="font-mono">{problem.attempts}</td>
              <td>{problem.notes ? <button className="text-button whitespace-nowrap" aria-expanded={visibleNotes.has(problem.number)} aria-controls={`notes-${problem.number}`} onClick={() => toggleNotes(problem.number)}>{visibleNotes.has(problem.number) ? 'Hide notes' : 'Show notes'}</button> : <span className="text-slate-400">No notes</span>}</td>
              <td><button className="row-button" onClick={() => setEditor({ kind: 'attempt', problem })} aria-label={`Record attempt for ${problem.name}`}>Record attempt</button></td>
            </tr>{visibleNotes.has(problem.number) && <tr id={`notes-${problem.number}`}><td colSpan={9} className="notes-cell"><p className="eyebrow mb-2">Your notes · {problem.name}</p><p className="whitespace-pre-wrap break-words max-w-3xl">{problem.notes}</p></td></tr>}</Fragment>)}</tbody>
          </table>
        </div>}
    </section>
    <p className="mt-5 text-center text-xs text-slate-400">Recall changes. Every attempt is a new starting point.</p>
    {editor && <EntryDialog editor={editor} onClose={() => setEditor(null)} onSaved={() => {
      setNotice(editor.kind === 'problem' ? 'Problem added.' : 'Attempt recorded.'); setEditor(null); void refresh()
    }} />}
  </main>
}
