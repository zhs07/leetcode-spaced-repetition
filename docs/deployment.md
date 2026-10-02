# Public deployment plan

Status: Supabase project and initial provider configuration completed October 2,
2026. PostgreSQL storage and email authentication are implemented locally.
The local hosted backend now connects successfully as the restricted runtime
role. Real confirmation/recovery flows and public hosting remain unfinished.
Running without hosted environment settings still selects SQLite.

## Provider setup progress

Project `leetcode-tracker` (`stqydfklcxicvffqoycs`) is active in `us-west-1`.
Creation was quoted at $0/month and approved by the user; recheck pricing before
changing the plan or provisioning additional resources.

- Applied the exact contents of `001_user_owned_tracker.sql` through the
  Supabase connector, wrapped with the schema/history setup from `migrate.py`.
  Supabase records this as `bootstrap_tracker_schema_and_runtime_role`.
  The application migration table separately records the original filename and
  SHA-256 `55d0255b21d2614fd18075e7a563224222c129e9cc09d00996236dbd32615d48`,
  preserving compatibility with the application's migration runner. Do not
  replay the bootstrap SQL or modify the applied migration file.
- Created `tracker_runtime` with the documented table/sequence grants, no schema
  creation or migration-history writes, and no elevated role attributes. It is
  now a LOGIN role with a generated random password stored only in the ignored,
  owner-readable `.env` (mode 0600). Supabase received a SCRAM-SHA-256 verifier;
  no administrator credentials were used by the application.
- Verified `anon` and `authenticated` have no schema access or read/write grants
  on any tracker table. A live anonymous REST request selecting the `tracker`
  schema returned HTTP 406 / `PGRST106`; only `public` and `graphql_public` were
  exposed. A real authenticated REST probe is still pending. Security advisors
  returned no findings. No personal records were imported.
- Verified email sign-in and confirmation are enabled, and the public JWKS
  advertises an ES256 key. Anonymous sign-ins were disabled at initial setup;
  they were later enabled with approval and verified below. Saved an eight-character
  minimum password setting in the dashboard.
- Set Site URL to `http://127.0.0.1:5173/` and verified both that URL and
  `http://127.0.0.1:5173/?auth=recovery` in the redirect allowlist.
- Created ignored `frontend/.env.local` with the project URL and public
  publishable key. Its API URL now explicitly targets `http://127.0.0.1:8001`
  so a restart cannot accidentally route hosted requests to the original local
  SQLite server on port 8000. The backend `.env` supplies hosted configuration,
  the runtime session-pooler URL, and the local certificate bundle path.
- Python on this Mac initially failed TLS certificate verification fetching the
  JWKS. The request succeeded with `SSL_CERT_FILE` pointing to the existing
  `certifi.where()` bundle. Use this when starting the local hosted backend:
  `SSL_CERT_FILE="$(.venv/bin/python -m certifi)" .venv/bin/python -m uvicorn main:app --env-file .env`.
  This keeps certificate verification enabled and requires no package install.

The runtime connects through the dashboard-provided session pooler
`aws-0-us-west-1.pooler.supabase.com:5432` using the username
`tracker_runtime.stqydfklcxicvffqoycs`. Live checks verified schema compatibility,
client-to-pooler TLS, and denied schema/migration-history modifications. The
database-side `pg_stat_ssl` describes the separate pooler-to-database hop; use
`connection.pgconn.ssl_in_use` to inspect the local client connection.
The application currently uses `sslmode=require`; a separate `verify-full`
probe using the public certifi bundle failed certificate validation. Full
database certificate/hostname verification is not yet configured.

A live storage smoke test used two generated owner UUIDs and verified separate
records for the same number, reviews, statements, archive/delete isolation, and
cascading deletion. All synthetic rows were removed and all three data tables
were verified empty afterward. This is storage-layer evidence, not a test of
two real authenticated users. The running backend returned 200 for `/health`
and 401 for unauthenticated `/problems`.

Local hosted integration startup (two terminals):

```bash
# Repository root; .env already includes SSL_CERT_FILE on this Mac.
.venv/bin/python -m uvicorn main:app --env-file .env --host 127.0.0.1 --port 8001

# frontend/; .env.local explicitly selects backend port 8001.
npm run dev -- --port 5173 --strictPort
```

The original SQLite backend on port 8000 was left running separately. The
frontend was restarted and the real Supabase account-creation form was opened;
the user must enter their own account password. No sign-up email was sent by
the assistant. GitHub account linking was reported by the user; repository
integration has not been configured.

The first real account received its confirmation email and was confirmed in
Supabase. Automatic callback sign-in displayed an invalid/expired-link message;
the exact cause remains unverified (a browser mismatch is one possibility).
Ordinary email/password sign-in then succeeded. The protected hosted
`/problems/summary` returned HTTP 200, and the UI showed the empty account.
The signed-in session also survived a page reload. Do not ask this user to
register again to resolve the earlier callback error.

Later live verification on October 2 found 68 problems, 68 review rows, and one
cached statement for one owner in Supabase. The signed-in frontend displayed
all 68 active problems. After a controlled restart of only the hosted backend
on port 8001 and a page reload, every displayed table row matched the baseline,
including attempts, mastery, and review dates; the account stayed signed in.
This verifies persistence of the existing collection across backend restarts.
No records were added, modified, or deleted during this check, and the original
SQLite backend and personal database were left untouched. The earlier
empty-table smoke-test result describes the state before these records existed.

Callback errors now distinguish provider-reported expiry from other exchange
failures. For an unsuccessful confirmation exchange, the UI suggests trying
ordinary sign-in because the email may already be confirmed. Failed recovery
links instead suggest requesting a new reset link. The cause of the earlier
live callback incident remains unverified; improved messages do not establish
that the underlying live confirmation/recovery flows are reliable.

Frontend build, lint, and all 13 mocked auth browser tests passed after this
change. The tests separately exercise provider-reported expiry, a failed code
exchange, a missing browser verifier, and successful confirmation/recovery.
They do not send real email or replace the remaining live-account checks.

Still required: guest abuse controls and cleanup before public launch; SMTP for
public email sign-up; live confirmation callback and recovery
checks; two-real-account isolation tests; an authenticated Data API rejection
probe; full database certificate/hostname verification; and hosting. The later
configuration checklist describes the full setup, including completed steps.

## Fully free launch preparation

The user selected a fully free setup on October 2. Keep the existing Supabase
project on Free, use Render's free static site and free web service, and use
their supplied HTTPS subdomains. No domain purchase is required for hosting.
Avoid adding a payment method or upgrading any plan during this setup. Render
documents suspension/build limits when included usage is exhausted without a
payment method; the backend also sleeps after 15 idle minutes and can take
about a minute to wake. See [Render Free](https://render.com/docs/free).

Email delivery remains unresolved. A free sending allowance does not establish
that an account can send reliable authentication email without a domain:

- [Resend](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain)
  limits its test domain to the account owner's address; other recipients need
  an owned, verified domain.
- [SMTP2GO](https://www.smtp2go.com/blog/smtp2go-questions-answered/)
  has a free plan but does not allow Gmail/Yahoo addresses at signup.
- [Mailjet](https://documentation.mailjet.com/hc/en-us/articles/360042759253-How-to-add-a-sender-address)
  permits individual sender verification but warns that freemail senders can
  fail delivery. This has not been provisioned or tested for this project.

The recommended domain-free alternative is
[GitHub sign-in through Supabase](https://supabase.com/docs/guides/auth/social-login/auth-github).
This would let public users sign in with GitHub instead of receiving signup or
password-reset email from the tracker. It is a proposed login choice, not yet
selected, implemented, or configured. Preserve the existing email account and
its owner UUID/records. Linking the developer's GitHub account to Supabase or
Render is separate from configuring GitHub as a tracker login provider.

### Prepared Render Blueprint

`render.yaml` defines the two hosting services with automatic deploys disabled,
the API explicitly on `plan: free`, and dashboard prompts for configuration.
It creates no Render database, disk, or migration job. Creating a Blueprint
still triggers an initial public deployment: do not apply it until the
remaining live isolation, authentication, and database TLS checks are complete.
No Render resources have been created during this preparation.

| Service | Dashboard value | How to fill it |
| --- | --- | --- |
| API | `TRACKER_DATABASE_URL` | Restricted runtime-role session-pooler URL with the verified TLS configuration; never migration/admin credentials |
| API | `SUPABASE_URL` | Existing Supabase HTTPS project origin |
| API | `TRACKER_ALLOWED_ORIGINS` | Actual frontend HTTPS origin, without a trailing slash; add the local origin only if intentionally testing it |
| Frontend | `VITE_SUPABASE_URL` | Same Supabase HTTPS project origin |
| Frontend | `VITE_SUPABASE_PUBLISHABLE_KEY` | Public publishable key only |
| Frontend | `VITE_API_BASE_URL` | Actual API HTTPS origin, without `/api` or a trailing slash |

Use the actual URLs assigned by Render instead of guessing them from the
service names. Review these values before the initial deploy; changing a
`VITE_*` value requires rebuilding the frontend. Add the final frontend URL
and exact callback URLs to Supabase's redirect allowlist before testing public
login. Do not copy the Mac-specific `SSL_CERT_FILE` path to Render or upload
the local `.env` file. Python/Node versions and Blueprint fields follow
[Render's configuration reference](https://render.com/docs/blueprint-spec).
This file is prepared locally; a real Render build/start has not yet verified
the selected runtime versions and dependency installation.

## Guest access decision and implementation

On October 2 the user chose guest access and authorized selecting the simplest
free implementation. Selected **Supabase anonymous sign-in**. Browser-only guest
storage also has no service fee, but would require a second implementation of
the Python scheduling, imports, statement retrieval, and storage operations.
Supabase guests reuse the existing verified-token and owner-scoped PostgreSQL
path. No new packages, migrations, paid plans, or OAuth providers were added.
The permanent public login choice remains unresolved; existing email login is
preserved.

The hosted landing flow now works as follows:

1. Restore an existing session if present. Otherwise show the real tracker UI
   with three clearly labeled, handwritten sample problems. Filtering, sorting,
   notes, and theme switching work without any tracker API requests. Viewing the
   samples creates no auth user or database rows.
2. **Guest** calls `supabase.auth.signInAnonymously()` on demand. Sample
   action buttons also start a fresh guest workspace; the sample records are
   never saved into it. A guest starts with an empty private collection.
3. The SDK retains and refreshes the guest session in this browser. FastAPI
   still verifies signature, issuer, audience, expiry, role, and UUID subject.
   Only the rejection of valid anonymous accounts changed. Guests have their
   own UUIDs and use the same ownership predicates as permanent accounts.
4. **Sign in** opens the existing account form. Guests can go back without
   replacing their session. The form explains that successful account sign-in
   replaces guest access and does not transfer guest records. Guest-to-account
   identity linking or merging has not been implemented.

Clearing browser data, losing the session, or signing into another account can
lose access to the guest collection. No cross-device recovery is promised.
Supabase is cloud storage, while browser-only guests store their records on the
device. Both can cost $0; Supabase usage remains subject to the project's Free
quotas. See [pricing](https://supabase.com/pricing) and
[anonymous sign-ins](https://supabase.com/docs/guides/auth/auth-anonymous).

After explicit user approval on October 2, enabled and saved **Allow anonymous
sign-ins** in the live Supabase dashboard. The saved setting and a successful
real guest sign-in both verified activation. The project remains on Free;
email confirmation stays **enabled**, and manual identity linking stays
**disabled**. The anonymous-user rate limit remains 30 sign-ins per hour per IP.

### Real guest save and reload verification

Used a separate local origin `http://127.0.0.1:5176/` and hosted API on port 8002
to keep browser storage separate from the original frontend on port 5173.
Both connect to the existing Supabase project; this was a live cloud test,
not a mocked auth test or a disposable database test. The original backend
on port 8001 had already been restarted with the updated verifier.

- Opened the sample tracker, then clicked **Try as guest** to create a real
  anonymous session. The new workspace was empty, without personal or sample
  records copied into it.
- Saved synthetic problem #1, **Guest verification: Two Sum**, topic **Guest
  test**, with a first attempt dated October 2, **Partial Recall**, and clearly
  labeled synthetic notes. The backend returned HTTP 201; the UI showed one
  attempt and next review **October 4, 2026**.
- Revealed the notes, captured the table's visible text, reloaded the page,
  revealed notes again, and compared the complete table text: exact match.
  The guest label remained visible, and there were no error alerts. Real
  authenticated GET requests returned HTTP 200 after reload.
- A read-only live database aggregate joined owners to `auth.users` and
  confirmed permanent accounts still had **68 problems and 68 reviews**;
  the anonymous guest had **one problem and one review**. No personal records
  were written or deleted. No sign-in/sign-out was performed on the original
  frontend; it showed the sample preview when inspected afterward.
- Left the synthetic guest, its test record, and the guest browser session
  available for further testing. No cleanup or account deletion was performed.

The subsequent UI refinement uses **Your review space** for both preview and
signed-in views, with compact **Guest** and **Sign in** controls in the topbar.
Clicking Guest in an active session reveals its browser persistence details.
The retained live test record was renamed to **Two Sum**, topic **Arrays &
Hashing**; its attempt and review date stayed unchanged and were visible after
reload. Frontend build, lint, 20 auth browser tests, and 18 tracker browser tests
passed; desktop and mobile layouts were inspected.

Guest verification servers were left running at completion:

```bash
# Repository root: isolated guest API; existing ignored .env supplies credentials.
TRACKER_ALLOWED_ORIGINS=http://127.0.0.1:5176 .venv/bin/python -m uvicorn main:app --env-file .env --host 127.0.0.1 --port 8002

# frontend/: isolated guest browser origin.
VITE_API_BASE_URL=http://127.0.0.1:8002 npm run dev -- --port 5176 --strictPort
```

The normal application at port 5173 continues to target the hosted API on 8001.
No credential/configuration file was modified for this test. A visual proof of
the guest after reload is saved outside the repository at
`/private/tmp/leetcode-guest-live-after-reload-2026-10-02.jpg`. Recheck listeners
before relying on these temporary verification servers in a later session.

Before public guest launch, configure CAPTCHA/Turnstile and pass its token to
the SDK, verify rate limits, choose guest record/operation limits, and define
cleanup for both auth users and tracker records. Supabase has no automatic
anonymous-user cleanup. Tracker rows do not reference `auth.users`, so deleting
an auth user alone will leave application records. No cleanup job or guest
limits were implemented in this change; do not apply the Render Blueprint yet.

Verification for this change: frontend build and lint; **20 mocked auth/guest
browser tests**; **18 existing local tracker browser tests** using disposable
SQLite; **134 backend tests** including disposable PostgreSQL and guest-to-guest
and guest-to-permanent-account isolation; `git diff --check`. The browser guest
tests do not create live Supabase users. All existing callback regression tests
remain covered. No personal collection, applied migration, or Git branch was
modified, and no staging/commit/push was performed.

The live security advisor returned one warning for disabled leaked-password
protection. This feature requires Pro or above according to
[Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
Retained the Free plan and existing password settings; no table-access finding
was reported.

Interview explanation: "Visitors needed to see and try the tracker before
registering. I chose anonymous authentication because it reused our existing
API and per-user database design, keeping scheduling in one implementation.
Each guest gets a verified UUID, so avoiding an email form doesn't mean sharing
data. I separated sample content from saved records, tested isolation and session
restoration, and made the session-loss tradeoff clear. Public launch also needs
abuse controls and cleanup to keep resource use within the free allowance."

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
- Supabase provides PostgreSQL and authentication. Email/password login with
  verification and recovery is implemented; anonymous guest login is enabled
  and real guest save/reload behavior has been verified against the live project.
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
grants, Supabase Data API configuration, and live provider integration are
still deployment tasks; this migration does not provision accounts or roles.
The test suite verifies the intended grants locally, not the live Supabase API.

## Implemented authentication milestone

`TRACKER_MODE=hosted` requires a PostgreSQL URL, Supabase HTTPS project URL, and
an explicit comma-separated list of frontend origins. Invalid configuration
stops startup; Render cannot start in local mode. `main.py` checks the schema
and opens the pool without migrating. Every tracker route (including import
preview) verifies a bearer token before constructing its `PostgresStore`.
Only `/health` and the API documentation are public. Health reports process
readiness, not ongoing database or email-provider availability.

`auth.py` verifies ES256/RS256 signatures using the configured project's JWKS,
with expiry, issuer, audience, issue time, role, and UUID-subject checks.
Valid anonymous accounts are accepted with the same UUID ownership checks;
malformed anonymous claims and legacy HS256 tokens are rejected. Configure asymmetric
signing keys in Supabase. Public keys are cached for five minutes, and an unknown
key ID triggers refresh. A key-service outage returns 503; invalid sessions
return 401. Verification is local after keys are cached: access tokens remain
valid until expiry even after sign-out. Use an appropriate Supabase token expiry.

The React client handles email/password sign-up and sign-in, confirmation,
password recovery, session refresh, and sign-out through the official Supabase
SDK. Passwords are never sent to FastAPI. PKCE confirmation/recovery links must
open in the same browser that requested them. Expired links show a retry message.
Access tokens accompany API requests; account changes remount the tracker and
discard late responses from the previous account. API 401s clear the private
view. Sign-out uses local scope (this browser), not all devices.

### Local verification without a provider account

The backend auth tests use locally signed synthetic tokens and disposable
PostgreSQL. Browser auth tests mock Supabase network responses: they exercise
the real JavaScript SDK and forms but do not send email or validate a live project.

```bash
# Repository root: backend auth and PostgreSQL regression suite
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider

# frontend/: synthetic hosted-auth browser tests on port 5175
npm run test:auth

# frontend/: existing local workflows, disposable SQLite, ports 8011/5174
npm run test:e2e
```

### Provider configuration still required

1. Create the Supabase project and enable email/password sign-in, email
   confirmation, and a password minimum of at least eight characters. Select
   asymmetric JWT signing keys supported above. Enable anonymous sign-ins for
   the selected guest flow after confirming the live change, and complete the
   guest abuse controls and cleanup requirements above before public launch.
2. Configure SMTP for public confirmation/recovery email. Verify sender/domain
   requirements and free limits before choosing a provider. Do not disable
   confirmation as a workaround for the default sender restriction.
3. Apply the migration with migration credentials. Create a separate login role
   for the runtime: grant USAGE on `tracker`, SELECT on `schema_migrations`,
   SELECT/INSERT/UPDATE/DELETE on the three data tables, and USAGE on their
   sequences. Do not grant schema creation or migration-table writes. Keep
   `tracker` outside Supabase's exposed Data API schemas and verify browser roles
   have no direct grants. Our application role uses explicit owner predicates;
   RLS policies are not being used to impersonate the token's user over SQL.
4. Copy the root `.env.example` to `.env` and fill it locally with the runtime
   database URL, Supabase project origin, and exact frontend origin(s). Launch
   with `.venv/bin/python -m uvicorn main:app --env-file .env`. The Python code
   itself does not automatically load `.env`; production uses service variables.
5. Copy `frontend/.env.example` to `frontend/.env.local` and set the project URL
   and **publishable** key. Never put a secret/service-role key or DB password
   in `VITE_*` variables. Restart Vite after changes. Production builds default
   to hosted mode; missing auth settings show a configuration error.
6. Set the Supabase Site URL and allow exact confirmation/recovery redirects:
   `http://127.0.0.1:5173/` and `http://127.0.0.1:5173/?auth=recovery` for local
   integration, then the equivalent HTTPS production URLs. Set `VITE_API_BASE_URL`
   to the backend HTTPS origin for production; use `/api` for the Vite proxy.
7. Verify with two real accounts: confirmation, login, reload, recovery, sign-out,
   and separate records for the same problem number. Confirm that the Data API
   cannot read tracker tables and records persist across backend restarts.

Sources: [Supabase password auth](https://supabase.com/docs/guides/auth/passwords),
[PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow),
[signing keys](https://supabase.com/docs/guides/auth/signing-keys).

The next milestone is provider setup and live integration, followed by hosting.
Account setup and live deployment will require the user's provider access;
do not collect credentials in chat. Git staging, commits, and pushes remain
user-operated unless explicitly authorized.
