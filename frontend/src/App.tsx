import useModalDialog from './useModalDialog'
import { Fragment, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { masteryLevels, request } from './api'
import type { ProblemSummary } from './api'
import ImportDialog from './ImportDialog'
import PracticeDialog from './PracticeDialog'
import { sampleProblems } from './sampleProblems'

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
  if (!value) return <span className="text-faint">Not scheduled</span>
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
  const dialog = useModalDialog()
  const [saving, setSaving] = useState(false)
  const [includeFirstAttempt, setIncludeFirstAttempt] = useState(true)
  const [error, setError] = useState('')
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
          {editor.kind === 'attempt' && <p className="mt-2 text-muted">{editor.problem.name}</p>}</div>
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
          <label>Notes <span className="font-normal text-faint">(optional)</span><textarea name="notes" rows={3} placeholder="Your approach, insights, or a reminder…" /></label>
          <p className="text-sm text-muted">Notes stay hidden until you choose to reveal them.</p>
          <div className="border-t border-line pt-4">
            <label className="flex items-center gap-3">
              <input type="checkbox" className="m-0 h-4 w-4" checked={includeFirstAttempt} onChange={event => setIncludeFirstAttempt(event.target.checked)} aria-describedby="first-attempt-help" />
              Record my first attempt
            </label>
            <p id="first-attempt-help" className="mt-2 text-sm text-muted">Uncheck to save this problem for later without recording an attempt.</p>
          </div>
        </> : null}
        {(editor.kind === 'attempt' || includeFirstAttempt) && <>
          <label>Completion date<input type="date" name="reviewed_on" defaultValue={localToday()} required autoFocus={editor.kind === 'attempt'} /></label>
          <label>Mastery level<select name="mastery_level" required defaultValue=""><option value="" disabled>How did this attempt go?</option>{masteryLevels.map(level => <option key={level}>{level}</option>)}</select></label>
          <p className="text-sm leading-6 text-muted">Choose based on this attempt. Your next review is scheduled from its completion date.</p>
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

function DeleteDialog({ problem, onClose, onDeleted }: { problem: ProblemSummary; onClose: () => void; onDeleted: () => void }) {
  const dialog = useModalDialog()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  async function remove() {
    if (deleting) return
    setDeleting(true); setError('')
    try {
      await request(`/problems/${problem.number}`, undefined, 'DELETE')
      onDeleted()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not delete. Please try again.')
      setDeleting(false)
    }
  }
  return <dialog ref={dialog} aria-labelledby="delete-title" aria-describedby="delete-description" onCancel={event => { event.preventDefault(); if (!deleting) onClose() }}>
    <h2 id="delete-title" className="text-2xl font-semibold">Delete problem?</h2>
    <p id="delete-description" className="mt-4 text-sm leading-6 text-muted">Delete #{problem.number} {problem.name} and its {problem.attempts} recorded {problem.attempts === 1 ? 'attempt' : 'attempts'}? This cannot be undone.</p>
    {error && <p role="alert" className="error mt-4">{error}</p>}
    <div className="flex justify-end gap-3 mt-6">
      <button className="secondary" autoFocus disabled={deleting} onClick={onClose}>Cancel</button>
      <button className="danger" disabled={deleting} onClick={() => void remove()}>{deleting ? 'Deleting…' : 'Delete problem'}</button>
    </div>
  </dialog>
}

export default function App({ preview = false, onStartGuest, accountControls, accountFeedback }: {
  preview?: boolean; onStartGuest?: () => void; accountControls?: ReactNode; accountFeedback?: ReactNode;
}) {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#18191c' : '#f4f5f7')
    try { localStorage.setItem('tracker-theme', theme) } catch { /* Appearance still works when browser storage is unavailable. */ }
  }, [theme])
  const [today, setToday] = useState(localToday)
  useEffect(() => {
    const update = () => setToday(localToday())
    const timer = window.setInterval(update, 30000)
    window.addEventListener('focus', update)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', update) }
  }, [])
  const [problems, setProblems] = useState<ProblemSummary[]>(() => preview ? sampleProblems(localToday()) : [])
  const [loading, setLoading] = useState(!preview)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [noticeView, setNoticeView] = useState<'all' | 'archived' | null>(null)
  const [archivePending, setArchivePending] = useState<number | null>(null)
  const [actionError, setActionError] = useState('')
  const [reviewDatesPending, setReviewDatesPending] = useState<Set<number>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<ProblemSummary | null>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [practiceOpen, setPracticeOpen] = useState(false)
  const [visibleNotes, setVisibleNotes] = useState<Set<number>>(new Set())
  const [view, setView] = useState('all')
  const [topic, setTopic] = useState('')
  const [mastery, setMastery] = useState('')
  const [sortBy, setSortBy] = useState('next_review')
  const [direction, setDirection] = useState('asc')
  const scopeProblems = problems.filter(problem => view === 'archived' ? problem.archived : !problem.archived)
  const topics = [...new Set(scopeProblems.map(problem => problem.topic))].sort((a, b) => a.localeCompare(b))
  const shownProblems = scopeProblems.filter(problem =>
    (view === 'all' || view === 'archived' || (view === 'due' ? problem.next_review !== null && problem.next_review <= today : problem.mastery_level === null)) &&
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
  const hasFilters = view === 'due' || view === 'unreviewed' || topic || mastery
  function clearFilters() { if (view !== 'archived') setView('all'); setTopic(''); setMastery('') }
  function changeView(nextView: string) {
    if ((view === 'archived') !== (nextView === 'archived')) { setTopic(''); setMastery('') }
    setView(nextView)
  }
  function clearStaleTopic(data: ProblemSummary[]) {
    if (topic && !data.some(problem => problem.topic === topic && (view === 'archived' ? problem.archived : !problem.archived))) setTopic('')
  }
  const latestRequest = useRef(0)
  async function refresh() {
    if (preview) { setProblems(sampleProblems(localToday())); return }
    const id = ++latestRequest.current
    setLoading(true); setError('')
    try {
      const data = await request<ProblemSummary[]>('/problems/summary')
      if (id === latestRequest.current) { setProblems(data); setReviewDatesPending(new Set()); clearStaleTopic(data) }
    }
    catch (failure) { if (id === latestRequest.current) setError(failure instanceof Error ? failure.message : 'Could not load your problems.') }
    finally { if (id === latestRequest.current) setLoading(false) }
  }
  useEffect(() => {
    if (preview) return
    let active = true
    request<ProblemSummary[]>('/problems/summary')
      .then(data => { if (active) setProblems(data) })
      .catch(failure => { if (active) setError(failure instanceof Error ? failure.message : 'Could not load your problems.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [preview])
  function toggleNotes(number: number) {
    setVisibleNotes(previous => { const next = new Set(previous); if (next.has(number)) next.delete(number); else next.add(number); return next })
  }
  async function changeArchive(problem: ProblemSummary) {
    if (preview) { onStartGuest?.(); return }
    if (archivePending !== null || loading) return
    const action = problem.archived ? 'restore' : 'archive'
    setArchivePending(problem.number); setActionError(''); setNotice(''); setNoticeView(null)
    try {
      await request(`/problems/${problem.number}/${action}`, undefined, 'POST')
      // Apply the confirmed status immediately, even if fetching fresh dates fails.
      const updated = problems.map(item => item.number === problem.number ? { ...item, archived: !problem.archived, next_review: null } : item)
      setProblems(updated)
      clearStaleTopic(updated)
      setVisibleNotes(previous => { const next = new Set(previous); next.delete(problem.number); return next })
      if (action === 'restore') setReviewDatesPending(previous => new Set(previous).add(problem.number))
      setNotice(`#${problem.number} ${problem.name} ${action === 'archive' ? 'archived. Your history is preserved.' : 'restored to active problems.'}`)
      setNoticeView(action === 'archive' ? 'archived' : 'all')
      await refresh()
    } catch (failure) {
      setActionError(`Could not ${action} #${problem.number} ${problem.name}: ${failure instanceof Error ? failure.message : 'Please try again.'}`)
    } finally { setArchivePending(null) }
  }
  return <main className="app-shell">
    <div className="topbar">
      <button className="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
          {theme === 'dark' ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></> : <path d="M20 14A8.5 8.5 0 0 1 10 4a8.5 8.5 0 1 0 10 10Z" />}
        </svg>
        {theme === 'dark' ? 'Light mode' : 'Dark mode'}
      </button>
      {accountControls && <div className="account-controls">{accountControls}</div>}
    </div>
    {accountFeedback}
    <header className="page-header">
      <div>
        <h1>Your review space</h1>
        <p className="header-description">Practice, track, and revisit LeetCode problems for technical interviews and online assessments.</p>
      </div>
      <div className="header-actions">
        <button className="primary practice-button" disabled={loading || archivePending !== null} onClick={() => preview ? onStartGuest?.() : setPracticeOpen(true)}><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m17 3 4 4-4 4M3 17h3c5 0 7-10 12-10h3M17 13l4 4-4 4M3 7h3c2 0 3 1 4 3m4 4c1 2 2 3 4 3h3" /></svg>Random pick</button>
        <button className="secondary" disabled={archivePending !== null} onClick={() => preview ? onStartGuest?.() : setEditor({ kind: 'problem' })}><span aria-hidden="true">＋ </span>Add problem</button>
        <button className="quiet-button" disabled={loading || archivePending !== null} onClick={() => preview ? onStartGuest?.() : setImportOpen(true)}>Import CSV</button>
      </div>
    </header>
    <section aria-labelledby="table-title" className="table-card">
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5 border-b border-line">
        <div className="flex items-center gap-3"><h2 id="table-title" className="font-semibold">{view === 'archived' ? 'Archived problems' : preview ? 'Sample problems' : 'Your problems'}</h2><span className="count">{scopeProblems.length}</span></div>
        <button className="text-button" onClick={() => { setNotice(''); setNoticeView(null); setActionError(''); void refresh() }} disabled={loading || archivePending !== null}>{loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>
      <div className="border-b border-line bg-surface-soft px-6 py-4">
        <div className="filter-grid">
          <label className="text-xs text-muted">Show<select value={view} onChange={event => changeView(event.target.value)}><option value="all">Active problems</option><option value="due">Due & overdue</option><option value="unreviewed">Not reviewed</option><option value="archived">Archived</option></select></label>
          <label className="text-xs text-muted">Filter by topic<select value={topic} onChange={event => setTopic(event.target.value)}><option value="">All topics</option>{topics.map(item => <option key={item}>{item}</option>)}</select></label>
          <label className="text-xs text-muted">Filter by mastery<select value={mastery} onChange={event => setMastery(event.target.value)}><option value="">All mastery levels</option>{masteryLevels.map(item => <option key={item}>{item}</option>)}</select></label>
          <label className="text-xs text-muted">Sort by<select value={sortBy} onChange={event => setSortBy(event.target.value)}><option value="next_review">Next review</option><option value="attempts">Attempts</option><option value="difficulty">Difficulty</option><option value="mastery">Mastery level</option><option value="topic">Topic</option></select></label>
          <label className="text-xs text-muted">Direction<select value={direction} onChange={event => setDirection(event.target.value)}><option value="asc">Ascending ↑</option><option value="desc">Descending ↓</option></select></label>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-muted" role="status">Showing {shownProblems.length} of {scopeProblems.length} {view === 'archived' ? 'archived problems' : 'problems'}</p>
          {hasFilters && <button className="text-button" onClick={clearFilters}>Clear filters</button>}
        </div>
      </div>
      {view === 'archived' && <p className="px-6 pt-4 text-xs text-muted">Review scheduling is paused. Restore a problem when you want to practice it again.</p>}
      {notice && <p role="status" className="px-6 pt-4 text-sm text-success">{notice} {noticeView && noticeView !== view && scopeProblems.length > 0 && <button className="text-button underline" onClick={() => changeView(noticeView)}>{noticeView === 'archived' ? 'View archived' : 'View active problems'}</button>}</p>}
      {actionError && <p role="alert" className="error m-5">{actionError}</p>}
      {error && <div role="alert" className="error m-5">{error} {problems.length > 0 && 'Showing the last loaded data.'} <button className="underline font-semibold" onClick={() => void refresh()}>Try again</button></div>}
      {loading && problems.length === 0 ? <p role="status" className="empty-state">Loading your practice history…</p> :
        problems.length === 0 && !error && view !== 'archived' ? <div className="empty-state">
          <div className="empty-icon" aria-hidden="true">&lt;/&gt;</div><h3 className="text-xl font-semibold text-strong mt-5">A fresh start for your practice</h3>
          <p className="mt-2">Add a problem with your first attempt, or save it to practice later.</p>
          <button className="text-button mt-5" onClick={() => preview ? onStartGuest?.() : setEditor({ kind: 'problem' })}>Add your first problem →</button>
        </div> : scopeProblems.length === 0 && !error ? <div className="empty-state"><h3 className="text-lg font-semibold text-strong">{view === 'archived' ? 'No archived problems' : 'Your active list is clear'}</h3><p className="mt-2">{view === 'archived' ? 'Problems you archive will appear here with their history.' : 'Your saved problems are archived. Restore one whenever you want to practice it again.'}</p><button className="text-button mt-4" onClick={() => changeView(view === 'archived' ? 'all' : 'archived')}>{view === 'archived' ? 'View active problems' : 'View archived'}</button></div> : scopeProblems.length > 0 && shownProblems.length === 0 ? <div className="empty-state"><h3 className="text-lg font-semibold text-strong">No matching problems</h3><p className="mt-2">Try another filter combination to see more of your list.</p><button className="text-button mt-4" onClick={clearFilters}>{view === 'archived' ? 'Show archived problems' : 'Show active problems'}</button></div> : scopeProblems.length > 0 && <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Problems table; scroll horizontally on small screens">
          <table className="problems-table"><thead><tr>{['#', 'Problem', 'Difficulty', 'Topic', 'Mastery', 'Next review', 'Attempts', 'Notes', 'Actions'].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
            <tbody>{shownProblems.map(problem => <Fragment key={problem.number}><tr>
              <td className="text-faint font-mono">{problem.number}</td><th scope="row" className="problem-name">{problem.name}</th>
              <td><span className={`badge ${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span></td><td className="text-muted">{problem.topic}</td>
              <td><span className={problem.mastery_level ? `mastery-badge ${masteryColors[problem.mastery_level] ?? ''}` : 'text-faint'}>{problem.mastery_level ?? 'Not reviewed'}</span></td>
              <td className="whitespace-nowrap text-muted">{problem.archived ? <span className="archive-badge">Reviews paused</span> : reviewDatesPending.has(problem.number) ? <span className="text-muted">Refresh for review date</span> : <ReviewDate value={problem.next_review} today={today} />}</td>
              <td className="font-mono">{problem.attempts}</td>
              <td>{problem.notes ? <button className="text-button whitespace-nowrap" aria-expanded={visibleNotes.has(problem.number)} aria-controls={`notes-${problem.number}`} onClick={() => toggleNotes(problem.number)}>{visibleNotes.has(problem.number) ? 'Hide notes' : 'Show notes'}</button> : <span className="text-faint">No notes</span>}</td>
              <td><div className="flex flex-col items-start gap-2">
                {!problem.archived && <button className="row-button" disabled={loading || archivePending !== null} onClick={() => preview ? onStartGuest?.() : setEditor({ kind: 'attempt', problem })} aria-label={`Record attempt for ${problem.name}`}>Record attempt</button>}
                <div className="flex items-center gap-1">
                  <button className={problem.archived ? 'row-button' : 'archive-link'} disabled={loading || archivePending !== null} onClick={() => void changeArchive(problem)} aria-label={`${problem.archived ? 'Restore' : 'Archive'} ${problem.name}`} title={problem.archived ? 'Resume reviews; this problem becomes due immediately.' : 'Pause reviews and keep your history.'}>{archivePending === problem.number ? problem.archived ? 'Restoring…' : 'Archiving…' : problem.archived ? 'Restore' : 'Archive'}</button>
                  <button className="delete-link" disabled={loading || archivePending !== null} aria-label={`Delete ${problem.name}`} onClick={() => { setNotice(''); setNoticeView(null); setActionError(''); if (preview) onStartGuest?.(); else setDeleteTarget(problem) }}>Delete</button>
                </div>
              </div></td>
            </tr>{visibleNotes.has(problem.number) && <tr id={`notes-${problem.number}`}><td colSpan={9} className="notes-cell"><p className="eyebrow mb-2">Your notes · {problem.name}</p><p className="whitespace-pre-wrap break-words max-w-3xl">{problem.notes}</p></td></tr>}</Fragment>)}</tbody>
          </table>
        </div>}
    </section>
    <p className="mt-5 text-center text-xs text-faint">Built around spaced repetition.</p>
    {deleteTarget && <DeleteDialog problem={deleteTarget} onClose={() => setDeleteTarget(null)} onDeleted={() => {
      const remaining = problems.filter(problem => problem.number !== deleteTarget.number)
      setProblems(remaining)
      setVisibleNotes(previous => { const next = new Set(previous); next.delete(deleteTarget.number); return next })
      clearStaleTopic(remaining)
      setReviewDatesPending(previous => { const next = new Set(previous); next.delete(deleteTarget.number); return next })
      setNotice(`#${deleteTarget.number} ${deleteTarget.name} deleted.`)
      setDeleteTarget(null)
      void refresh()
    }} />}
    {practiceOpen && <PracticeDialog onClose={() => setPracticeOpen(false)} onSaved={() => {
      setPracticeOpen(false); setNotice('Attempt recorded.'); setNoticeView(null); setActionError(''); void refresh()
    }} />}
    {importOpen && <ImportDialog onClose={() => setImportOpen(false)} onImported={result => {
      setImportOpen(false)
      setView('all'); setTopic(''); setMastery('')
      setNotice(`Imported ${result.imported_numbers.length} ${result.imported_numbers.length === 1 ? 'problem' : 'problems'}. Skipped ${result.skipped_existing_numbers.length} existing ${result.skipped_existing_numbers.length === 1 ? 'problem' : 'problems'}, ${result.errors.length} invalid ${result.errors.length === 1 ? 'row' : 'rows'}, and ${result.skipped_rows} empty ${result.skipped_rows === 1 ? 'row' : 'rows'}.`)
      setNoticeView(null); setActionError('')
      // Keep this success notice if the subsequent refresh fails.
      void refresh()
    }} />}
    {editor && <EntryDialog editor={editor} onClose={() => setEditor(null)} onSaved={() => {
      setNotice(editor.kind === 'problem' ? 'Problem added.' : 'Attempt recorded.'); setNoticeView(null); setActionError(''); setEditor(null); void refresh()
    }} />}
  </main>
}
