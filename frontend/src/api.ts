export type ProblemSummary = {
  number: number; name: string; difficulty: string; topic: string;
  mastery_level: string | null; next_review: string | null; attempts: number; notes: string;
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
    throw new Error(`Request failed (${response.status}). Check that FastAPI is running.`)
  }
  return response.json() as Promise<T>
}
