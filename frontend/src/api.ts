import { apiIdentity, assertCurrentIdentity, hosted, rejectSession } from './auth'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export type ProblemSummary = {
  number: number; name: string; difficulty: string; topic: string;
  mastery_level: string | null; next_review: string | null; attempts: number; notes: string; archived: boolean;
}
export type ImportedProblem = {
  problem: {
    number: number; name: string; difficulty: string; topic: string; notes: string;
    first_attempt: { reviewed_on: string; mastery_level: string } | null;
  };
  total_attempts: number;
}
export type ImportPreview = {
  problems: ImportedProblem[];
  errors: { row_number: number; message: string }[];
  skipped_rows: number;
}
export type ImportResult = {
  imported_numbers: number[];
  skipped_existing_numbers: number[];
  errors: ImportPreview['errors'];
  skipped_rows: number;
}
export type StatementNode = string | {
  tag: string; children: StatementNode[]; src: string | null; alt: string | null;
}
export type PracticePick = {
  problem_number: number;
  statement: StatementNode[] | null;
  statement_error: string | null;
  leetcode_url: string | null;
}
// Exact labels from scheduler.REVIEW_INTERVALS; Python owns scheduling.
export const masteryLevels = ['Learned Solution', 'Partial Recall', 'Solved with Struggle', 'Solved Independently', 'Mastered']
export async function request<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const identity = await apiIdentity()
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      method, headers: {
        ...(identity.token ? { Authorization: `Bearer ${identity.token}` } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      }, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch { throw new Error('Cannot reach the server. Check your connection and try again.') }
  assertCurrentIdentity(identity.epoch)
  if (hosted && response.status === 401) {
    rejectSession()
    throw new Error('Your session expired. Please sign in again.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (typeof data?.detail === 'string') throw new Error(data.detail)
    if (Array.isArray(data?.detail)) throw new Error(data.detail.map((e: {loc?: string[]; msg: string}) => `${e.loc?.slice(1).join('.') || 'Input'}: ${e.msg}`).join('; '))
    if (response.status >= 500) throw new Error(hosted
      ? 'The server is temporarily unavailable. Please try again shortly.'
      : `The server encountered an error (${response.status}). Check the FastAPI terminal for details, then try again.`)
    throw new Error(`Request failed (${response.status}). Please try again.`)
  }
  const data = await response.json() as T
  assertCurrentIdentity(identity.epoch)
  return data
}
