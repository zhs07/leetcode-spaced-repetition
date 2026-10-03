import useModalDialog from './useModalDialog'
import { useEffect, useRef, useState } from 'react'
import { masteryLevels, maxRequestBytes, request, requestSizeError } from './api'
import { hosted } from './auth'
import type { ImportPreview, ImportResult } from './api'

export default function ImportDialog({ onClose, onImported }: {
  onClose: () => void;
  onImported: (result: ImportResult) => void;
}) {
  const dialog = useModalDialog()
  const [format, setFormat] = useState<'standard' | 'notion'>('standard')
  const [file, setFile] = useState<File | null>(null)
  const [csvText, setCsvText] = useState('')
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'save' | null>(null)
  const [error, setError] = useState('')
  // State updates render asynchronously; this guard also blocks rapid clicks.
  const pending = useRef(false)
  const active = useRef(true)

  useEffect(() => {
    active.current = true
    return () => { active.current = false }
  }, [])

  async function loadPreview() {
    if (!file || pending.current) return
    pending.current = true
    setBusy('preview'); setError(''); setPreview(null); setCsvText('')
    try {
      if (hosted && file.size > maxRequestBytes) throw new Error(requestSizeError)
      const text = await file.text()
      if (!text.trim()) throw new Error('This file is empty. Choose a CSV file.')
      const data = await request<ImportPreview>(`/imports/${format}/preview`, { csv_text: text })
      if (active.current) { setPreview(data); setCsvText(text) }
    } catch (failure) {
      if (active.current) setError(failure instanceof Error ? failure.message : 'Could not preview this file.')
    } finally {
      pending.current = false
      if (active.current) setBusy(null)
    }
  }

  async function save() {
    if (!preview?.problems.length || pending.current) return
    pending.current = true
    setBusy('save'); setError('')
    try {
      // Send the exact CSV that was previewed. The server validates it again.
      const result = await request<ImportResult>(`/imports/${format}`, { csv_text: csvText })
      if (active.current) onImported(result)
    } catch (failure) {
      if (active.current) setError(failure instanceof Error ? failure.message : 'Could not import. Please try again.')
    } finally {
      pending.current = false
      if (active.current) setBusy(null)
    }
  }

  return <dialog ref={dialog} className="import-dialog" aria-labelledby="import-title" onCancel={event => {
    event.preventDefault()
    if (!pending.current) onClose()
  }}>
    <div className="import-content">
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="eyebrow">Bring your practice history</p>
        <h2 id="import-title" className="text-2xl font-semibold mt-2">Import CSV</h2>
        <p className="mt-2 text-sm leading-6 text-muted">Choose your exported CSV, check the preview, then confirm the import.</p>
      </div>
      <button className="icon-button" aria-label="Close import" disabled={busy !== null} onClick={onClose}>×</button>
    </div>

    <div className="mt-5 space-y-3">
      <label>CSV format
        <select value={format} disabled={busy !== null} autoFocus onChange={event => {
          setFormat(event.target.value as 'standard' | 'notion')
          setPreview(null); setCsvText(''); setError('')
        }}>
          <option value="standard">Standard CSV</option>
          <option value="notion">Notion export</option>
        </select>
      </label>
      {format === 'standard' ? <div className="text-xs leading-5 text-muted space-y-2">
        <p>Required columns: number, name, difficulty, topic. Optional: notes, reviewed_on, mastery_level, total_attempts.</p>
        <p>Leave review history blank for unreviewed problems (0 attempts). With both a review date (YYYY-MM-DD) and mastery, attempts default to 1.</p>
        <a className="text-button" href={`${import.meta.env.BASE_URL}standard-import-template.csv`} download>Download CSV template</a>
        <p>Replace the template’s example rows with your own problems.</p>
        <details><summary className="text-button cursor-pointer">Supported values</summary>
          <p className="mt-2">Difficulty: Easy, Medium, Hard. Mastery: {masteryLevels.join(', ')}.</p>
        </details>
      </div> : <p className="text-xs leading-5 text-muted">Use the original Notion layout: Problem, Difficulty, Topic, Last Reviewed, Mastery, Pattern/Trick, Reviews. Choose the fuller export ending in _all.csv when available.</p>}
      <label>CSV file
        <input type="file" accept=".csv,text/csv" disabled={busy !== null} onChange={event => {
          setFile(event.target.files?.[0] ?? null)
          setPreview(null); setCsvText(''); setError('')
        }} />
      </label>
      <p className="text-xs leading-5 text-muted">Existing problem numbers will be skipped, keeping their notes and history.</p>
      {!preview && <button className="secondary" disabled={!file || busy !== null} onClick={() => void loadPreview()}>{busy === 'preview' ? 'Reading CSV…' : 'Preview import'}</button>}
    </div>

    {preview && <div className="mt-6 space-y-4">
      <div className="import-summary" role="status">
        <strong className="text-strong">{preview.problems.length} valid {preview.problems.length === 1 ? 'problem' : 'problems'}</strong>
        <span>{preview.errors.length} invalid {preview.errors.length === 1 ? 'row' : 'rows'} · {preview.skipped_rows} empty {preview.skipped_rows === 1 ? 'row' : 'rows'} skipped</span>
      </div>
      <p className="text-sm leading-6 text-muted">Nothing has been saved yet. Import preserves supplied attempts and the latest review; next review dates follow the app’s schedule. Problems without review history stay unreviewed.</p>

      {preview.errors.length > 0 && <div className="import-errors">
        <h3 className="font-semibold">Rows that won’t be imported</h3>
        <p className="mt-1 text-xs">You can import the valid problems now, or correct these rows and select the updated file.</p>
        <ul className="mt-2 list-disc pl-5 space-y-1">
          {preview.errors.map(row => <li key={row.row_number}>Row {row.row_number}: {row.message}</li>)}
        </ul>
      </div>}

      {preview.problems.length > 0 ? <div className="import-preview-table" role="region" aria-label="Import preview; scroll to see all problems" tabIndex={0}>
        <table>
          <thead><tr>{['Problem', 'Last reviewed', 'Mastery', 'Attempts'].map(title => <th scope="col" key={title}>{title}</th>)}</tr></thead>
          <tbody>{preview.problems.map(item => <tr key={item.problem.number}>
            <th scope="row">
              <p className="font-semibold">#{item.problem.number} {item.problem.name}</p>
              <p className="mt-1 font-normal text-xs text-muted">{item.problem.difficulty} · {item.problem.topic}</p>
              {item.problem.notes && <details className="mt-2 font-normal">
                <summary className="text-button cursor-pointer">Show notes</summary>
                <p className="mt-2 whitespace-pre-wrap break-words text-muted">{item.problem.notes}</p>
              </details>}
            </th>
            <td className="whitespace-nowrap">{item.problem.first_attempt?.reviewed_on ?? 'Not reviewed'}</td>
            <td>{item.problem.first_attempt?.mastery_level ?? '—'}</td>
            <td className="font-mono">{item.total_attempts}</td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="text-sm text-muted">No valid problems to import. Correct the reported rows or choose another file.</p>}
    </div>}

    {error && <p role="alert" className="error mt-4">{error}</p>}
    </div>
    <div className="flex shrink-0 flex-wrap justify-end gap-3 border-t border-line pt-4 mt-4">
      <button className="secondary" disabled={busy !== null} onClick={onClose}>Cancel</button>
      {preview && <button className="primary" disabled={busy !== null || preview.problems.length === 0} onClick={() => void save()}>
        {busy === 'save' ? 'Importing…' : `Import ${preview.problems.length} valid ${preview.problems.length === 1 ? 'problem' : 'problems'}`}
      </button>}
    </div>
  </dialog>
}
