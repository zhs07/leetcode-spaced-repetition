# LeetCode Review Tracker

A spaced-repetition app for technical interview practice. Track attempts, keep
notes, and know which problems to revisit next.

**[Open the live app →](https://leetcode-tracker-web.onrender.com/)**

Explore the sample tracker without signing in, or choose **Guest** to start your
own workspace. Create an account to keep access across browsers and devices.

The API runs on free hosting and may take about a minute to wake after inactivity.
If a confirmation or password-reset email is missing, check your Spam folder and
open the link in the browser that requested it.

## Why I built it

I started tracking LeetCode practice in Notion, then built this app to make that
review routine easier to maintain. I wanted to record how each attempt went,
schedule the next review, and practice without seeing the topic or solution notes
in advance. It grew into a full-stack project I use myself and can share with
others preparing for interviews.

## What it does

- **Review scheduling:** record attempts and use self-assessed mastery to set the next review date.
- **Blind practice:** randomly pick a due problem and read its statement before revealing its name, topic, difficulty, or notes.
- **Problem management:** filter and sort your collection, save notes, and archive problems without losing their history.
- **Notion import:** preview CSV rows from the supported Notion layout, preserve historical attempt totals, and avoid duplicate problems. See the [expected format](docs/development.md#importing-from-notion).
- **Private workspaces:** start as a guest, then create an account while keeping your progress. Guests can save up to 50 problems.
- **Simple interface:** light and dark modes with clear mastery and due-date indicators.

## Review intervals

After each attempt, choose a mastery level. Your next review is scheduled from
that attempt's date using these intervals:

| Mastery | Next review |
| --- | --- |
| Learned Solution | 1 day |
| Partial Recall | 3 days |
| Solved with Struggle | 7 days |
| Solved Independently | 14 days |
| Mastered | 30 days |

## Built with

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI
- **Data and authentication:** PostgreSQL and Supabase Auth for the hosted app; SQLite for local use
- **Hosting:** Render static frontend and API
- **Testing:** pytest and Playwright with isolated test databases

## Explore the code

- [Development guide](docs/development.md): local setup, tests, import behavior, and statement retrieval.
- [Frontend guide](frontend/README.md): UI architecture, API flow, and browser tests.
- [Deployment notes](docs/deployment.md): hosted configuration, verification, and current limitations.
