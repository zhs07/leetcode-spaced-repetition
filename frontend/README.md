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
- Adding a problem or saving an attempt triggers a fresh GET `/problems/summary`.
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

Browser tests start the existing backend with a disposable SQLite database on port 8011 and Vite on 5174. They require the repository's `.venv` and never use `tracker.db`. They exercise problem creation, hidden notes, review scheduling, duplicate errors, persistence after reload, mobile layout, and recovery from a failed load.
