# Tracker frontend

React + TypeScript + Vite + Tailwind CSS. Run commands below from `frontend/`.

```bash
npm ci
npm run dev
```

Run FastAPI separately from the repository root with `fastapi dev main.py`.
Open the URL printed by Vite (normally http://127.0.0.1:5173).

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
- Mastery choices currently mirror `scheduler.REVIEW_INTERVALS`; update both if labels change.

The proxy is for local development. A production deployment must route `/api` to FastAPI separately; `npm run build` does not deploy the app or include the Python server.

## Checks

```bash
npm run build
npm run lint
npx playwright install chromium
npm run test:e2e
```

Browser tests start the existing backend with a disposable SQLite database on port 8011 and Vite on 5174. They require the repository's `.venv` and never use `tracker.db`. They exercise creation, hidden notes, scheduling, filtering/sorting, CSV preview/import/reimport, deletion, archive/restore, persistence, mobile layout, and error recovery.
