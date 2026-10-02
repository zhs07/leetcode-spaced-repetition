# LeetCode Review Tracker

A spaced repetition tracker inspired by my personal Notion workflow.

I am building this project to learn fullstack development with Python
and create a tool I will use for reviewing LeetCode problems.

## Current functionality
- Calculate the next review date from a manually selected mastery level.
- Schedule reviews relative to the actual completion date.
- Problems and reviews are now stored in SQLite
- The Api can create problems, record attempts, and retrieve due problems
- Request validation and automated tests exist
- React interface for adding problems, recording attempts, and viewing summaries with hidden notes
- Delete unwanted problems and their attempts, with confirmation.
- Archive problems to pause reviews while keeping their history; restore them to make them due immediately. A new attempt resumes the normal schedule.
- Import a Notion CSV with a preview, row errors, confirmation, and preserved attempt totals. Existing problems are skipped.

## Importing from Notion

Click **Import CSV**, choose the exported CSV (prefer the fuller `_all.csv`
export), and click **Preview import**. Check the valid problems and reported
row errors, then confirm. Nothing is saved during preview. Invalid and empty
rows are excluded; existing problem numbers keep their data and history.

The supported columns are `Problem`, `Difficulty`, `Topic`, `Last Reviewed`,
`Mastery`, `Pattern/Trick`, and `Reviews`. Titles must end with a positive
problem number, dates use a format such as `September 10, 2026`, and mastery
supports the exported labels 🔵 Mastered, 🟢 Solved Independently, and
🟡 Solved With Struggle. If `Review Interval (Days)` is included, it must match
the app's mastery schedule. Relative exported review-status text is ignored.

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

## Planned functionality
- Randomly select a due problem, with options to hide its topic,
  name, and difficulty + from specific curated list if user want(nc 250/150, blind 75/grind 75 etc.)
- Explore automatic archiving based on repeated mastered attempts
  and problem difficulty.

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
See [frontend/README.md](frontend/README.md) for the data flow and browser tests.
