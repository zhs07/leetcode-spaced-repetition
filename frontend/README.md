# Tracker frontend

React + TypeScript + Vite + Tailwind CSS. Run commands below from `frontend/`.

```bash
npm ci
npm run dev
```

Run FastAPI separately from the repository root with `fastapi dev main.py`.
Open the URL printed by Vite (normally http://127.0.0.1:5173).

## Appearance

The interface defaults to neutral graphite with a muted blue accent. The top-left theme button switches between dark and light palettes and saves the preference in browser local storage (`tracker-theme`). The HTML head applies the saved preference before React loads to avoid a theme flash. If storage is blocked, switching still works for the current page. Mastery badges progress through red (learned), orange (partial recall), yellow (struggle), green (independent), and blue (mastered). Due and overdue countdowns use red. Both palettes use shared semantic CSS variables in `src/index.css`, including dialogs and the practice reader. Mobile controls reflow while the table scrolls horizontally.

## How data moves

- `src/main.tsx` mounts React in the HTML page.
- `src/App.tsx` renders the table and forms. State holds loaded summaries, open notes, the current form, and loading/error messages.
- `src/api.ts` sends JSON requests and converts FastAPI errors into readable messages.
- `vite.config.ts` forwards `/api/*` to FastAPI on port 8000, removing `/api`.
- Adding a problem, saving an attempt, importing, deleting, archiving, or restoring triggers a fresh GET `/problems/summary`.
- `src/ImportDialog.tsx` reads the selected CSV and sends its text to POST `/imports/notion/preview`. The preview shows valid problems, invalid logical CSV rows, empty-row counts, and hidden notes without database writes.
- Confirmation sends the same CSV text to POST `/imports/notion`, which validates it again and saves new problems in one transaction. Existing numbers are skipped; total attempts include the preserved older count. Choosing another file clears the previous preview.
- A successful import closes the dialog, clears filters to show active problems, and reports imported/skipped counts. Its success message remains visible if fetching fresh summaries fails; use Try again to refresh without repeating the import.
- The default Active problems view excludes archived records. Archived problems retain their mastery, attempts, and hidden notes; their review column displays Reviews paused.
- Archive and Restore send POST requests to `/problems/{number}/archive` and `/problems/{number}/restore`. Restore makes a problem due immediately; recording an attempt resumes its normal schedule.
- The UI applies confirmed archive status before refreshing. If refresh fails after a restore, it asks for a refresh to get the review date, rather than guessing a date. A successful write and a failed refresh have separate messages.
- Delete remains permanent and asks for confirmation including the attempt count.
- Python owns mastery, next-review dates, and attempt counts. The UI only formats them.
- `src/PracticeDialog.tsx` opens from Random pick and calls POST `/practice/random`. The server draws from saved due/overdue active problems using the existing scheduling policy, independent of table filters.
- The dialog renders statement nodes with React and hides identity/notes/history. Reveal details fetches GET `/problems/{number}/summary` only when requested. Record attempt uses the selected internal number and the existing POST `/reviews`, then refreshes summaries.
- Descriptions are fetched on demand and cached in SQLite. If a statement is unavailable, retry loads the same problem; a plain-text paste can be saved once as a fallback. Switching problems resets reveal/form state. Picking never creates a review.
- Mastery choices currently mirror `scheduler.REVIEW_INTERVALS`; update both if labels change.

The proxy is for local development. A production deployment must route `/api` to FastAPI separately; `npm run build` does not deploy the app or include the Python server.

## Guest access and email authentication

`AuthGate.tsx` wraps the tracker in hosted mode. `auth.ts` uses the Supabase SDK
for email/password sign-in, sign-up confirmation, PKCE callback handling, password
recovery, anonymous guest sign-in, and refreshed sessions. Signed-out visitors
see `App` in preview mode with handwritten examples from `sampleProblems.ts`;
this mode makes no tracker API requests. The Guest button creates a private empty
workspace using the existing API. Sample action buttons also start a guest;
filters and notes remain interactive in the sample view.
The header exposes Create account directly beside a quieter Sign in action.
For an active guest, Guest is a muted status badge that opens persistence details;
Create account opens the upgrade flow. From the sample preview, Create account
opens ordinary email/password registration. Permanent accounts show their email
and Sign out (or Finish account setup while an upgrade is unfinished).

Guest sessions return in the same browser until its session/storage is lost.
Signing into an existing permanent account replaces the guest session without
transferring records; the form explains this before submission. Guests can instead
choose Create account to attach a new email to their current UUID, confirm it,
then set a password in `GuestUpgrade.tsx`. A UUID-only browser marker resumes
unfinished setup after reload; ownership and API verification remain unchanged.
Existing-email conflicts do not merge or switch accounts. Guest sign-in is enabled and
real guest save/reload has been verified. Evidence, temporary verification server
commands, live upgrade evidence, and remaining public-launch
abuse controls are in the deployment guide.
Account changes remount the tracker and clear
its state; API requests attach the current access token and reject stale responses.

Vite development defaults to local mode. Production builds default to hosted
mode and show a configuration error without Supabase settings. Use the public
values in `.env.example` as a template for `.env.local`; never add a secret or
service-role key. `VITE_API_BASE_URL` is the production backend origin or `/api`
for the local proxy. See the [deployment guide](../docs/deployment.md) for setup.

Run `npm run test:auth` for the hosted UI on port 5175 with mocked Supabase
responses. It uses the real SDK but no live accounts or email; provider-level
verification remains a separate step. Existing `npm run test:e2e` uses local mode.

## Checks

```bash
npm run build
npm run lint
npx playwright install chromium
npm run test:e2e
```

Browser tests start the existing backend with a disposable SQLite database on port 8011 and Vite on 5174. They require the repository's `.venv` and never use `tracker.db`. They exercise creation, hidden notes, scheduling, filtering/sorting, blind practice, CSV preview/import/reimport, deletion, archive/restore, persistence, mobile layout, and error recovery. Blind-practice checks use cached synthetic statements or mocked source responses; they do not make live LeetCode requests.
