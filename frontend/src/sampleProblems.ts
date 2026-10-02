import type { ProblemSummary } from './api'

// Handwritten examples only. Never load a real user's collection for the preview.
export function sampleProblems(today: string): ProblemSummary[] {
  const later = new Date(`${today}T12:00:00`)
  later.setDate(later.getDate() + 7)
  const nextWeek = `${later.getFullYear()}-${String(later.getMonth() + 1).padStart(2, '0')}-${String(later.getDate()).padStart(2, '0')}`
  return [
    { number: 1, name: 'Two Sum', difficulty: 'Easy', topic: 'Arrays & Hashing', mastery_level: 'Partial Recall', next_review: today, attempts: 2, notes: 'Sample note: use a hash map to look up the complement.', archived: false },
    { number: 20, name: 'Valid Parentheses', difficulty: 'Easy', topic: 'Stack', mastery_level: 'Solved Independently', next_review: nextWeek, attempts: 3, notes: 'Sample note: match each closing bracket with the top of the stack.', archived: false },
    { number: 200, name: 'Number of Islands', difficulty: 'Medium', topic: 'Graphs', mastery_level: null, next_review: null, attempts: 0, notes: '', archived: false },
  ]
}
