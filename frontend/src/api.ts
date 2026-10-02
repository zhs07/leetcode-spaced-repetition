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
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    })
  } catch { throw new Error('Cannot reach the server. Check your connection and try again.') }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (typeof data?.detail === 'string') throw new Error(data.detail)
    if (Array.isArray(data?.detail)) throw new Error(data.detail.map((e: {loc?: string[]; msg: string}) => `${e.loc?.slice(1).join('.') || 'Input'}: ${e.msg}`).join('; '))
    if (response.status >= 500) throw new Error(`The server encountered an error (${response.status}). Check the FastAPI terminal for details, then try again.`)
    throw new Error(`Request failed (${response.status}). Check that FastAPI is running.`)
  }
  return response.json() as Promise<T>
}
