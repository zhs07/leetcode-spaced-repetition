# Deployment guide

The hosted app uses Render for the frontend and API, and Supabase for
PostgreSQL and authentication. For local SQLite setup, see the
[development guide](development.md).

## Architecture

- **React frontend:** served as a Render static site.
- **Supabase Auth:** email/password login, confirmation, recovery, and anonymous guests.
- **FastAPI:** verifies Supabase tokens and scopes every database operation to the authenticated user.
- **PostgreSQL:** stores problems, reviews, and cached statements in a private `tracker` schema.

The browser calls FastAPI for tracker data; it cannot access tracker tables
through Supabase's Data API. The runtime database connection verifies TLS
certificates and hostnames using the bundled [Supabase CA](../certificates/README.md).
Render's local filesystem is not used for persistent application data.

## Supabase setup

For a new deployment:

1. Create a Supabase project. Enable email/password login, email confirmation,
   anonymous sign-ins, and manual identity linking for guest upgrades. Set a
   password minimum of at least eight characters and use ES256 or RS256 signing keys.
2. Apply the versioned migrations with a separate migration credential. Set
   `TRACKER_MIGRATION_DATABASE_URL` privately in the shell, then run:

   ```bash
   .venv/bin/python migrate.py
   ```

   The script does not load `.env` automatically. The existing deployment is
   already migrated; do not replay its bootstrap SQL or edit applied migration files.
3. Create a restricted runtime login role with `USAGE` on `tracker`, `SELECT` on
   `schema_migrations`, read/write access to `problems`, `reviews`, and
   `problem_statements`, and `USAGE` on their sequences. Do not grant schema
   creation, migration-history writes, or elevated role privileges.
4. Keep `tracker` outside the exposed Data API schemas and deny schema/table
   access to `anon` and `authenticated`. FastAPI enforces ownership through its
   verified user identity and owner-scoped SQL queries.
5. Configure custom SMTP for public confirmation and recovery emails.
   Supabase's default sender is restricted to project team addresses.
   The current deployment uses Gmail SMTP: `smtp.gmail.com`, port `587`, the
   same Gmail address for sender and username, and a Google app password.
   Enter credentials directly in the provider dashboard.

Guest upgrades confirm the email before setting a password and retain the same
user UUID. Signing into an existing account does not merge guest progress.

References: [anonymous users and upgrades](https://supabase.com/docs/guides/auth/auth-anonymous),
[custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp),
[Google app passwords](https://support.google.com/accounts/answer/185833).

## Render configuration

[render.yaml](../render.yaml) defines a free FastAPI web service and a static
frontend. Creating a Blueprint triggers an initial public deployment.
Automatic service deploys are disabled in the file; the current Blueprint's
Auto Sync is also off. Deploy code changes manually after pushing them.

Set these values in the Render dashboard using your own provider details:

| Service | Variable | Value |
| --- | --- | --- |
| API | `TRACKER_MODE` | `hosted` (set by the Blueprint) |
| API | `TRACKER_DATABASE_URL` | Restricted runtime-role session-pooler connection URL |
| API | `SUPABASE_URL` | `https://YOUR_PROJECT.supabase.co` |
| API | `TRACKER_ALLOWED_ORIGINS` | Exact frontend HTTPS origin, without a trailing slash |
| Frontend | `VITE_TRACKER_MODE` | `hosted` (set by the Blueprint) |
| Frontend | `VITE_SUPABASE_URL` | Same Supabase project URL |
| Frontend | `VITE_SUPABASE_PUBLISHABLE_KEY` | Public publishable key |
| Frontend | `VITE_API_BASE_URL` | API HTTPS origin, without `/api` or a trailing slash |

Use the actual URLs assigned by Render. Once both are available, update the
cross-service settings and redeploy affected services. Changing any `VITE_*`
value requires rebuilding the frontend. In Supabase, set the Site URL to the
frontend URL and allow both exact callback URLs:

```text
https://YOUR_FRONTEND.onrender.com/
https://YOUR_FRONTEND.onrender.com/?auth=recovery
```

Confirmation and recovery links must open in the browser that requested them.
Keep database passwords, SMTP passwords, and privileged Supabase keys out of
Git and `VITE_*` variables. Use the placeholder configuration in
[.env.example](../.env.example) and [frontend/.env.example](../frontend/.env.example).
The API checks migration compatibility on startup; it does not run migrations.

## Verification

After deploying, check:

- `/health` returns 200; tracker routes reject missing or invalid tokens.
  CORS permits the configured frontend origin and rejects unrelated origins.
- Two real accounts have separate records, including for the same problem number;
  direct Supabase Data API requests cannot read tracker tables.
- Saved data survives reloads and API restarts. Signup confirmation, password
  recovery, later sign-in, and guest-to-account upgrades preserve the expected access and data.

The current public deployment has user-verified login, persistence, two-user
isolation, Data API rejection, and signup/recovery email flows. Guest upgrades
were verified earlier; a separate public upgrade test with Gmail SMTP has not
been recorded. These checks do not establish high-concurrency capacity.

For automated checks, run from the repository root:

```bash
.venv/bin/python -m pytest
npm --prefix frontend run test:auth
npm --prefix frontend run test:e2e
npm --prefix frontend run build
npm --prefix frontend run lint
```

PostgreSQL integration tests require `initdb` and `pg_ctl` (for example, from
PostgreSQL 17), discovered on PATH or through `PG_BIN`. They create disposable
databases and skip if binaries are unavailable. Browser auth tests mock provider
responses; they do not send email or replace live verification.

## Current limits

- **Free hosting:** the API sleeps after 15 idle minutes and may take about a
  minute to wake. Provider quotas can suspend service. See [Render Free](https://render.com/docs/free)
  and [Supabase pricing](https://supabase.com/pricing).
- **Email:** the configured auth email limit is 30 per hour. Test confirmation
  and recovery messages arrived in Spam; reliable inbox placement is not established.
- **Guests:** up to 50 saved problems, including archived ones. Clearing browser
  data or signing into another account can lose guest access.
- **Input limits:** hosted requests are capped at 1 MiB; field and CSV validation
  also applies. Permanent accounts have no saved-problem-count cap.
- **Deferred controls:** CAPTCHA, extra operation limits, review-history caps,
  and automatic guest cleanup are not implemented. Existing authentication rate
  limits remain active. Anonymous users can still accumulate; deleting an auth
  user alone does not remove tracker rows.
