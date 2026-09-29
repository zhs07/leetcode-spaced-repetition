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

## Planned functionality
- Randomly select a due problem, with options to hide its topic,
  name, and difficulty + from specific curated list if user want(nc 250/150, blind 75/grind 75 etc.)
- Support archiving and restoring problems.
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
