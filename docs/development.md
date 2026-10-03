# Development guide

Commands below run from the repository root unless stated otherwise.
See the [project overview](../README.md) for the motivation and main features.

## Blind practice

Click **Random pick** to open one randomly selected active problem whose review
date is today or earlier. The draw uses your entire saved due list, independent
of table filters. Archived, future-scheduled, and unscheduled problems are excluded.

The dialog shows only the statement, examples, and constraints. Name, number,
topic, difficulty, history, notes, and the LeetCode link stay hidden until
**Reveal details**. **Record attempt** saves directly to the selected problem
without revealing its identity and uses the usual mastery schedule. Picking or
closing a problem never records an attempt.

On the first pick, FastAPI looks up the problem number in LeetCode's public index
and retrieves that one description. It caches the description in SQLite;
subsequent picks use the saved copy without another LeetCode request. The public
endpoints may change or be unavailable. Premium/unavailable statements have a
retry and plain-text paste fallback. Paste a statement once and later picks use
that local copy. No LeetCode login or new dependencies are required.

Formatting is converted to allowed display nodes and rendered with React.
Scripts, source styles, interactive links, and arbitrary HTML attributes are
excluded; HTTPS diagrams are allowed only from recognized LeetCode image hosts.

API: POST `/practice/random`, POST `/practice/{number}/statement/load`,
PUT `/practice/{number}/statement` with `{"text": "..."}`, and
GET `/problems/{number}/summary` for an explicit reveal. Statement caches have
a foreign key to the saved problem and are removed when it is deleted.

## Importing from Notion

This importer supports the original project's Notion layout, rather than
arbitrary CSV files or every Notion database. The expected format is below.

Click **Import CSV**, choose the exported CSV (prefer the fuller `_all.csv`
export), and click **Preview import**. Check the valid problems and reported
row errors, then confirm. Nothing is saved during preview. Invalid and empty
rows are excluded; existing problem numbers keep their data and history.

The supported columns are `Problem`, `Difficulty`, `Topic`, `Last Reviewed`,
`Mastery`, `Pattern/Trick`, and `Reviews`. Titles must end with a positive
problem number, dates use a format such as `September 10, 2026`, and mastery
supports the exported labels 🔵 Mastered, 🟢 Solved Independently, and
🟡 Solved With Struggle. Exported `Review Interval (Days)` and review-status
columns are ignored; the app uses its current [review intervals](../README.md#review-intervals).

Notion exports contain only the latest review and total attempts. The import
stores that one review plus an older-attempt count, without inventing review
history. Notes (including commas and newlines) are preserved. Next review dates
come from the latest review and the app's scheduling rules.

`POST /imports/notion/preview` and `POST /imports/notion` both accept JSON
`{"csv_text": "..."}`. Confirmation reparses the CSV on the server and saves
the accepted batch in one transaction. Reimporting the same file adds no
duplicate reviews; any database failure rolls back the whole batch.

Startup also repairs the earlier nullable/TEXT `historical_attempts` column
if it is present: missing older counts become zero, valid counts and review
records are retained, and the column gets its integer/default/check constraints.
Before this repair, it saves a SQLite backup beside the database as
`tracker.db.before-import-counts.bak` (ignored by Git).

## Local setup

Developed with Python 3.14.

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
fastapi dev main.py
```

The activation command above is for macOS/Linux.

Open http://127.0.0.1:8000/docs to explore the API.
The SQLite database is created automatically on startup.

## Running tests

With the virtual environment active:

```bash
python -m pytest
```

The PostgreSQL deployment storage has a separate real-database integration
suite. See [the deployment guide](deployment.md#verification)
for prerequisites and its disposable database setup. Those tests skip when
PostgreSQL binaries are unavailable; the default local API still uses SQLite.
Hosted mode requires authentication and PostgreSQL configuration; see the
[authentication setup](deployment.md#supabase-setup).

## Frontend development

Requires Node.js 24 LTS and npm. Keep FastAPI running in one terminal.
In a second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints (normally http://127.0.0.1:5173).
The frontend forwards `/api` requests to FastAPI at http://127.0.0.1:8000.
See [frontend/README.md](../frontend/README.md) for the data flow and browser tests.
