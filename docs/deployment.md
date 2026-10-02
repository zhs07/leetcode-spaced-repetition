# Public deployment plan

Status: PostgreSQL storage milestone implemented, October 2, 2026. Hosting has
not been provisioned. The running API still uses local SQLite without
authentication; PostgreSQL is not wired into public routes yet.

## Preserved local version

`local-version` preserves the working SQLite app without authentication at
commit `ca1c172`. Continue deployment development on `main`. The branches share
history but future commits to `main` do not move `local-version`.

With a clean working tree, use `git switch local-version` to run or inspect the
original app and `git switch main` to return to deployment development. Stop
running development servers before switching. Untracked and ignored files,
including `tracker.db`, are not separate copies per branch; the branch preserves
code and documentation, not personal data or installed dependencies.

The branch currently exists locally only. Publishing it to the remote is a
separate Git push. Keep it as the local app baseline unless intentionally fixing
that version; do not merge deployment changes into it.

## Target architecture

- Render static site serves the existing React application.
- Render web service runs FastAPI and the existing Python scheduling logic.
- Supabase provides PostgreSQL and authentication. Email sign-in is selected;
  the working implementation is email/password with verification and recovery.
- React signs in through Supabase, then sends an access token in the
  `Authorization: Bearer ...` header to FastAPI.
- FastAPI verifies the token before choosing the user whose records it accesses.
  The browser never supplies an authoritative owner ID.

Render's free web service has an ephemeral filesystem and sleeps after idle
periods. The hosted database must therefore live outside that service. See
[Render Free](https://render.com/docs/free). Expect delayed first requests after
inactivity; the UI should explain waiting without retrying writes automatically.

## Ownership and database keys

Today `problems.number` is a global primary key. Replace that identity in the
hosted database with the pair `(user_id, number)`. `user_id` is the immutable UUID
from the verified Supabase token's `sub` claim, not a GitHub username or email.

For example, `(Alice, 1)` and `(Bob, 1)` are separate saved problems. Alice's
review of #1 cannot change Bob's schedule, even though both use `/problems/1`.

| Table | Key and relationship | Data retained |
| --- | --- | --- |
| `problems` | Primary key `(user_id, number)` | Name, difficulty, topic, notes, archive flag, due override, historical attempt count |
| `reviews` | Generated `id`; composite foreign key `(user_id, problem_number)` to `problems` | Review date and mastery |
| `problem_statements` | Primary key `(user_id, problem_number)`; same composite foreign key | Statement HTML and optional title slug |

Use PostgreSQL UUID, DATE, BOOLEAN, and integer types. Keep positive problem
numbers and nonnegative historical counts as database constraints. Both child
tables cascade on deletion of their own parent problem. Index reviews by
`(user_id, problem_number, reviewed_on, id)` for ownership and history lookups.

For the first release, all statement caches are per user, including fetched
public descriptions. This preserves the current delete behavior and prevents
pasted content from being shared. A shared public cache can be considered later.

## Backend implementation decisions

Keep the existing root module layout and dataclasses. Add a PostgreSQL storage
implementation using Psycopg 3 and parameterized SQL; an ORM is unnecessary for
these three tables. The `local-version` branch retains the SQLite implementation
and its legacy repair tests. On `main`, retain them during the transition as
needed; the public version does not require permanently maintaining two storage
backends solely to preserve the original app.

Add an explicit storage interface, with an owner-scoped store constructed by a
FastAPI dependency. Every hosted storage operation requires a verified user;
there is no default hosted owner or fallback to anonymous SQLite. Translate
database-specific errors into common duplicate/not-found/storage errors so
routes no longer depend on SQLite error strings in hosted mode.

Use explicit, versioned SQL migrations for PostgreSQL, with a migration-version
table and transactional execution. Run migrations as a deliberate deployment
step using separate migration credentials; application startup should check
schema compatibility rather than silently changing production tables.

For the runtime connection, use TLS and a small bounded connection pool. Choose
the Supabase session pooler if the hosting network requires IPv4; copy connection
details from the provider rather than constructing hostnames. See
[Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres).

Keep app tables in a schema excluded from Supabase's Data API. Use a dedicated
runtime database role with only required table/sequence access, not schema-owner
credentials. All tracker access goes through FastAPI's owner-scoped queries;
direct SQL connections do not automatically acquire a Supabase user's identity.
Verify anonymous and authenticated Data API clients cannot access these tables.
See [Supabase API security](https://supabase.com/docs/guides/api/securing-your-api).

## API behavior to preserve and verify

- Every tracker route, including import preview and statement retrieval, requires
  authentication in hosted mode. A separate minimal health endpoint can be public.
- Verify token signature, allowed signing algorithm, expiry, issuer, audience,
  and UUID subject using the configured project's signing keys. Reject malformed
  or invalid tokens; never merely decode them. Support signing-key rotation.
  See [Supabase signing keys](https://supabase.com/docs/guides/auth/signing-keys).
- Lists, summaries, random practice, reviews, deletes, archive, restore, and
  statement reads/writes operate only within the authenticated user's records.
  A number absent from that user's list returns 404 even if someone else owns it.
- Duplicate problem creation returns 409 only within the same user's collection.
- Import duplicate checks are per user. Use a unique constraint and
  `ON CONFLICT ... DO NOTHING RETURNING ...` for concurrent imports; add the
  imported review only when the parent insert succeeded. Commit the entire batch
  together or roll it all back. Do not port SQLite's `BEGIN IMMEDIATE` literally.
- Creating a problem with its first attempt remains one transaction. Recording a
  review and clearing its due override also remain one transaction.
- Preserve existing scheduling, same-day review ordering, historical totals,
  restore idempotence, and the rule that picking a problem records no attempt.

## Frontend and environment configuration

Implement sign-up, sign-in, sign-out, email confirmation, and password recovery
through Supabase Auth. Passwords go to Supabase, not the tracker API or database.
Use configured callback URLs and clear signed-in user data on sign-out/session
changes. Test expired confirmation/recovery links and account switching.

Public email sign-up requires an email delivery provider: Supabase's default
sender only delivers to project team members. Select a suitable SMTP service
and check its free allowance and sender/domain requirements before provisioning;
a fully zero-cost public email setup has not yet been established. Do not disable
email verification to bypass this requirement. See
[Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp) and
[email/password auth](https://supabase.com/docs/guides/auth/passwords).

Add a production API base URL to `frontend/src/api.ts`; retain `/api` for Vite's
local proxy. Allow only configured frontend origins through FastAPI CORS,
including the Authorization header. CORS does not replace authentication.

The frontend may contain the Supabase URL and publishable key. Database
passwords, migration credentials, and privileged Supabase keys must never be
placed in `VITE_*` variables or committed. Add placeholder example configuration
when implementing each setting. Production configuration must fail closed when
authentication or database settings are missing.

## Milestones and completion checks

1. **Ownership design:** this document; inspect existing route and storage contracts.
2. **PostgreSQL storage:** migrations, owner-scoped storage, transactions, and
   disposable PostgreSQL tests. Existing SQLite tests alone cannot verify it.
3. **Authentication:** verified FastAPI identity, React sign-in/session handling,
   and tests for invalid tokens and every route's authentication requirement.
4. **Isolation and regression:** two users can save the same number; neither
   can read, modify, import over, or delete the other's data. Test pasted
   statements, concurrent imports, rollback, and the existing browser workflows.
5. **Provision and deploy:** configure free provider projects, email delivery,
   secrets, migrations, API URL, CORS, and callback URLs. Verify actual
   login, persistence across backend restarts, and Data API isolation before
   calling the deployment ready for other users.

Use disposable databases throughout implementation. Leave the personal SQLite
database and backups untouched. Moving personal records is a separate explicit
operation: a Notion import cannot preserve all local review history and archive
state, so do not describe it as a full SQLite migration.

## Implemented PostgreSQL milestone

- `postgres_storage.py`: an immutable `PostgresStore(pool, user_id)` for each
  verified UUID. All reads and writes scope records to that owner. A small
  connection pool wraps each operation in a commit/rollback transaction.
- `migrations/001_user_owned_tracker.sql`: composite ownership keys, cascading
  child deletion, typed dates/booleans, and checks for valid numbers/counts.
- `migrate.py`: transactional migrations with a database lock and checksums.
  Startup compatibility checks reject missing or changed migration history;
  they never migrate automatically. Applied SQL files must not be edited.
- `storage_errors.py`: duplicate, missing-parent, and general storage failures
  that the API can translate without depending on driver-specific messages.
- `tests/test_postgres_storage.py`: real PostgreSQL tests using fresh temporary
  databases and a restricted runtime role. They cover ownership, statements,
  deletion, scheduling, import totals, rollback, concurrent imports/reviews,
  migration consistency, and schema permissions.

Install the updated Python requirements in `.venv`. For integration tests,
install PostgreSQL binaries (macOS: `brew install postgresql@17`). No permanent
database service is needed. Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_postgres_storage.py
```

The tests find `initdb` on PATH or in Homebrew's PostgreSQL 17 directory;
alternatively set `PG_BIN` to the PostgreSQL binary directory. They start a
private Unix-socket-only server, create disposable databases, then stop the
server and remove its temporary files. They never read a database URL from your
environment or use `tracker.db`. Tests that need PostgreSQL explicitly skip if
the binaries are missing; a skipped run does not verify the storage layer.
Restricted environments may need permission to initialize/start the test server.

When provider setup is ready, set `TRACKER_MIGRATION_DATABASE_URL` privately
and run `.venv/bin/python migrate.py`. The command requires TLS. Use a dedicated
database/project and migration credentials. Runtime role creation, minimum
grants, Supabase Data API configuration, and authenticated API integration are
still deployment tasks; this migration does not provision accounts or roles.
The test suite verifies the intended grants locally, not the live Supabase API.

The next milestone is verified Supabase email authentication and wiring the
owner-scoped store into FastAPI, followed by React session handling.
Account setup and live deployment will require the user's provider access;
do not collect credentials in chat. Git staging, commits, and pushes remain
user-operated unless explicitly authorized.
