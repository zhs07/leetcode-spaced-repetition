# LeetCode tracker — continuation handoff

Prepared September 29, 2026. This is a continuation guide, not a verbatim transcript. Read current files before assuming this snapshot is unchanged.

## Suggested opening prompt

Continue as my project tutor and collaborator. Read this handoff and the referenced local artifacts. I implement meaningful backend tasks with your guidance; when I say “check,” inspect saved code and run appropriate isolated tests without editing. You take the larger frontend implementation role. We have a working tracker with optional first attempts, date/mastery badges, and filters/sorting. The next requested feature is deleting a problem and its attempts. Start with a small backend task and explain unfamiliar SQL; do not implement the whole backend for me or restart completed lessons.

## Purpose and working relationship

The enduring goal is to learn Python/backend/software engineering by building something the user actually uses, and explain its decisions and bugs confidently in internship/co-op interviews. The app replaces their personal Notion LeetCode practice tracker. A co-op application deadline is approaching, but no exact deadline was provided. Do not invent one or promise a completion date.

The user wants a usable, deliberately simple product. They are excited by the working frontend and increasingly propose improvements based on actual use. Preserve that momentum while keeping hands-on backend ownership. They prefer conceptual frontend understanding to memorizing React/TypeScript/CSS syntax. They explicitly authorize a larger assistant implementation role for frontend work.

Authoring boundaries remain important:

- Backend: teach one meaningful step, offer skeletons or targeted snippets, let the user save their implementation, then review/test. Do not edit their code unless requested.
- “Check,” “done,” and similar messages during an exercise mean inspect saved files and verify. Do not assume it is correct just because they finished.
- Frontend: implement agreed behavior, explain briefly, verify build/lint and relevant browser behavior. Do not silently change backend logic during UI work.
- No automatic commits or pushes. User performs those. Keep feature milestones coherent, stage explicit paths, and use `git --no-pager diff` when giving commands: they previously got stuck in the pager; `q` exits it.
- Never use personal `tracker.db` for automated writes. Use temporary databases; TestClient and browser form submissions really write records.
- No need to repeatedly ask permission for read-only checks or already approved frontend work. Do not create a long repetitive exercise curriculum.

## Where to find authoritative details

Repository: `~/Desktop/leetcode-spaced-repitition` (intentional spelling). Use the actual home directory, not an older conversation workspace. Paths below are relative to this repository.

Avoid duplicating the existing artifacts; consult them for details:

- `leetcode-project-handoff-2026-09-21.txt`: extensive older background, product rules, early learning history, and backend code map. Its “next steps” and frontend-not-built statements are obsolete. Prefer current code and this handoff's continuation point.
- `README.md`: project purpose, setup, and deferred features.
- `frontend/README.md`: frontend data flow, development proxy, commands, and isolated browser-test setup. Feature descriptions may lag subsequent UI additions.
- `scheduler.py`, `models.py`, `tracker.py`: canonical labels/intervals, domain records, and review logic. Do not infer mastery ordering alphabetically or change canonical string casing.
- `storage.py`, `schemas.py`, `main.py`: persistence, request validation, and API routes.
- `summaries.py`: conversion to table summaries.
- `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/api.ts`: current interface, styles, and fetch/error helper.
- `tests/`, `frontend/tests/tracker.spec.ts`, `frontend/playwright.config.ts`, `frontend/tests/api_server.py`: saved tests and test infrastructure.

## Verified repository state at handoff

Read-only status inspection during this handoff found no tracked modifications. Untracked items: `.vscode/` and the older handoff `.txt`. Do not add these automatically.

Branch: `main`, matching the locally recorded `origin/main`. No live remote fetch was performed, so do not present that as independent verification of GitHub's current state.

Latest commits (read their diffs for implementation details rather than reconstructing them):

- `27e3cd3` — Add sorting and filtering by selected property
- `cc6a0d3` — Add Color to Mastery Level and Next Review date
- `969eab9` — Support optional first attempt when adding a problem
- `6dcd153` — Add React frontend for problem tracking and review recording
- `857b39e` — Add problem summaries for tracker table

The user has committed the UI work that earlier conversational messages called uncommitted. Trust this latest inspection.

## Current product and design decisions

The above commits and code are the feature specification. Rationale/context that matters for future work:

- “Add problem” serves two real workflows: record a problem just practiced, or put an unattempted problem on a future-practice list (as the user did in Notion).
- Optional first-attempt checkbox is checked by default. Mastery has no assumed default; the user chooses it. Unchecked entries have no history or review schedule. A planned first-practice date is a distinct future feature, not implemented.
- Learned Solution counts as an attempt. Zero attempts means no recorded practice, not failure or looking up a solution.
- The user implemented the atomic storage operation and API wiring with tutoring. Retain their ownership and build on this understanding.
- Frontend success notices clear on manual Refresh. A successful save and a failed subsequent summary fetch are separate outcomes; do not encourage re-submitting a saved attempt just because refresh failed.
- Countdown badges were deliberately changed from stacked date/countdown to side-by-side with divider and aligned widths because the user disliked the visual asymmetry.
- Existing date colors, mastery colors, filter choices, and custom sort ordering are defined in the latest UI commits. Preserve them unless asked otherwise.
- Default sorting brings the oldest review dates first; null dates/mastery stay last in either sort direction. Filters combine and operate locally on fetched summaries without additional API requests. Filter state is not persisted across full reloads.
- Notes are hidden to prevent practice spoilers, not to provide confidentiality. They are already present in loaded summary data.
- UI due status uses the browser's local calendar date. Existing backend `/problems/due` uses server `date.today()`; if deployment spans timezones this deserves an explicit decision. Do not silently rewrite scheduling for the deletion task.

## Exact next task: deletion (requested, not implemented)

The user's latest substantive request: explain persistence and allow removing unwanted problems, since additions currently remain forever.

The assistant explained SQLite persistence and proposed:

- Permanently delete the selected problem AND its recorded attempts.
- Use one database transaction: delete matching reviews first, then the problem; commit together, rollback on failure.
- Add `DELETE /problems/{problem_number}`.
- Frontend row action with confirmation explicitly mentioning the problem and attempt count, e.g. “Delete [problem] and its 4 recorded attempts? This cannot be undone.”
- Distinguish deletion from later archive/restore, which preserves history.

No deletion storage function, route, or UI exists yet (verified by source inspection). No personal records have been deleted. The user requested the feature but paused for this handoff before starting implementation. HTTP success/missing-resource behavior and storage return value have not yet been settled; propose a clear small contract rather than pretending these were already agreed.

Recommended continuation:

1. Read current storage schema and functions. Give the user one deletion storage exercise, building on their existing transaction pattern. Explain parameterized `DELETE ... WHERE ...`, the reason for child-before-parent order, and the missing-problem return/error contract. Do not require a schema migration/cascade redesign just to implement the feature.
2. Review their saved work with isolated verification. Save meaningful tests: deletion with and without reviews, preservation of other problems/reviews, missing target behavior, rollback if the second deletion fails.
3. Guide the small API wiring and integration test; choose a consistent response contract.
4. Assistant implements frontend confirmation, pending/error handling, and refresh after success. `frontend/src/api.ts` currently assumes GET or POST and parses successful responses as JSON: inspect it before adding DELETE, particularly if choosing a 204 response.
5. Check filters/visible notes after deletion (including deletion of the last matching topic or last visible problem). Do not leave a stale success UI on a failed delete. Verify cancel makes no request.
6. User tests personally, then commits/pushes the completed feature.

The immediate lesson should remain small; this list is a roadmap, not one huge assignment.

## Learning state and useful explanations

They understand logic but sometimes forget syntax. Be respectful, concrete, and explain the exact boundary instead of assuming ignorance of the whole concept.

Recently learned through their own code:

- One connection + two INSERTs + one commit creates an atomic operation; two existing save functions with separate commits do not.
- Rollback undoes the earlier problem INSERT when the review INSERT fails; bare `raise` propagates failure to the caller.
- A saved rollback test uses a test-only SQLite trigger with `RAISE(ABORT, ...)` to force the second INSERT to fail. This is test infrastructure, not a production rule or syntax to memorize.
- `pytest.raises` surrounds the failing call; assertions checking persisted state belong after the block.
- Schema inheritance: define `AttemptCreate` first, then `ReviewCreate(AttemptCreate)` adds `problem_number`. Parent fields/validator need not be copied. Parentheses in a class definition mean inheritance, not function arguments.
- Nested first-attempt request data differs from the flat summary response. `reviewed_on` is completion date; `next_review` is calculated date.

Recurring mistakes worth watching:

- Comparing a function reference to data instead of calling it (`get_all_reviews` versus `get_all_reviews(database_path)`).
- Missing comma between SQL string and parameter tuple, producing `'str' object is not callable`.
- Assertions indented inside a loop before all dictionary entries have been added.
- Passing a Python date where JSON expects a string, or using the request shape as the expected response shape.

Frontend concepts explained and understood: state, components, props, conditional rendering, GET/POST flow, type versus domain validation, persisted database versus browser snapshot, and why a failed refresh does not undo a successful write. They want explanations tied to behavior and interview questions, not a React syntax course.

Latest persistence explanation: SQLite is a local `tracker.db` file managed through SQL. App startup creates missing tables while retaining records; each successful write commits immediately; GET loads data for React. Launching the app does not itself save new attempts. Stopping servers or closing the browser does not erase the file.

## Verification and environment

Last actual checks in this conversation (not rerun during handoff):

- Python: 19 saved tests passed after first-attempt API work. Two preexisting dependency deprecation warnings (Starlette/httpx, AnyIO BlockingPortal).
- Frontend build and lint passed with filter/sort implementation.
- Four Playwright tests passed after adapting selectors for new filter controls. Coverage includes add/review/error workflows, optional first-attempt submission, date badge boundaries, and combined filters/all sort directions.
- Browser screenshots were inspected. Artifacts under ignored `frontend/test-results/`; they use synthetic data, not real tracker records.

Use root `.venv` for Python. Read-only-friendly check:
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=short`

Startup and frontend commands are in the READMEs; user often needs the two-terminal reminder. Stop with Ctrl+C. Do not assume servers are still running in a new task.

Playwright uses ports 8011 and 5174 and a disposable DB; it must not attach to the user's regular app for mutation tests. It may need narrow sandbox approval to bind local ports/launch Chromium. npm registry access may also require escalation. Dependencies and browser were already installed; don't reinstall reflexively.

Use role-based exact combobox/cell selectors in UI tests: adding toolbar options made loose `getByLabel('Mastery level')` and `getByText('Partial Recall')` ambiguous. Current tests contain the fixes.

Root `.gitignore` previously got overwritten by a virtual environment created in the repository root. It was repaired; root `bin/`, `include/`, `lib/`, and `pyvenv.cfg` are ignored leftovers. Do not delete these or rebuild environments as part of unrelated work. Personal DB, venvs, node_modules, build output, and test output must stay untracked.

## Longer-term vision and deferred decisions

The user wants to use the app regularly and collect real bugs/friction, then deploy and potentially share it with the LeetCode community. Prioritize correctness, everyday usability, visual improvements, then speculative features. Styling that improves readability is usability work.

Ideas discussed but not authorized as current implementation scope: pattern tab, DSA progression tree/NeetCode integration, planned practice dates, archive/restore, random due selection, curated lists, authentication/multiple users. Keep a backlog; don't turn the one-page tracker into a learning platform prematurely.

Deployment is educational and résumé-relevant, but not done. Vercel was suggested by a friend and discussed as a candidate, not chosen. It supports Vite and FastAPI; current writable local SQLite cannot simply be assumed persistent in Vercel Functions. Options discussed: backend with persistent disk, or separately hosted database. Reverify current provider docs/limits before deciding. No migration, deployment, account creation, costs, or public release has been authorized.

Public personal deployment, isolated public demo, and multi-user app are different scopes. Current app has no authentication or per-user isolation. Don't publish a shared writable personal tracker as if it gives every visitor separate data.

Résumé guidance: describe completed, demonstrable work accurately; add deployment/traction claims only when real. User prefers building first and then writing bullets. They wrote the backend with guidance; assistant wrote much of frontend. Explain that honestly without undermining their substantive work. Stars are optional; real usage and bug-fix stories are valuable evidence.

## Suggested skills

No special skill is needed for the next repository deletion/tutoring task; use normal file inspection and isolated tests.

If needed, invoke the relevant skill using the next environment's Skill tool (or read its SKILL.md if that is the available mechanism):

- `handoff`: when creating another continuation document; current skill path is `~/.agents/skills/handoff/SKILL.md`.
- `visualize:visualize`: only if an interactive concept explanation would materially help the user.
- `openai-docs`: only for actual Codex/OpenAI product questions, not ordinary React/backend work.

Do not route this existing repository through Sites or substitute a new stack. No agent delegation was requested.
