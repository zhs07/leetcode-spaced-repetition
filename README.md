# LeetCode Review Tracker

A focused spaced-repetition app for technical interview practice.

## Why I built it

I started tracking LeetCode practice in Notion. That gave me a review routine,
but I wanted more control over how I recorded attempts, scheduled reviews,
and chose what to practice next.

I built this app around that workflow while learning full-stack development.
It keeps a history of my attempts, schedules the next review from how an attempt
actually went, and lets me pause problems without losing their history.
Blind practice hides the problem's name, topic, difficulty, and notes so I can
try it without those advance clues.

The goal is a clear, minimal tool I want to use myself, and can eventually share
with other people preparing for interviews.

## What it does

- **Schedule reviews:** record an attempt and choose a mastery level to set the next review date.
- **Practice blind:** randomly pick an active due problem, read its statement, and reveal details when ready.
- **Keep useful history:** save notes, filter and sort problems, and archive or restore problems as needed.
- **Bring your Notion data:** preview a CSV import, see row errors, and preserve historical attempt totals without adding duplicates.
- **Stay focused:** a minimal interface with light and dark modes and clear mastery and due-date indicators.

## Built with

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Testing:** pytest and Playwright, using isolated test databases

## Run it locally or explore the code

The app currently runs locally. Public deployment is the next milestone.

- [Development guide](docs/development.md): local setup, tests, import behavior, and statement retrieval.
- [Frontend guide](frontend/README.md): UI architecture, API flow, and browser tests.

Review scheduling uses fixed intervals based on self-assessed mastery. This is
an independent personal project, not an official LeetCode product.
