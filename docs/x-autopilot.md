# X Autopilot Phase 2

Single-account, Luna-only research and drafting with human-approved X publishing. Development agents are separate from runtime calls: production uses only `gpt-5.6-luna`; Sol and Astra are disabled.

## Setup

Python 3.14 is recommended. Local SQLite data remains supported; PostgreSQL is required in cloud mode.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Copy only if no local config exists; preserve existing personal settings.
cp config/x-autopilot.example.toml config/x-autopilot.toml
python3 -m x_autopilot init-db
python3 -m x_autopilot review
```

On Windows the venv interpreter is `.venv\Scripts\python.exe`. `.env.example` documents variable names only; the application does not automatically load `.env` files. Supply secrets through the environment or service secrets.

`review` starts the UI only; `serve` runs the UI and persistent scheduler, with publication polling independent of research/model work; `worker` runs the scheduler alone; `scheduler-tick` executes one tick and exits. `research`, `generate`, and `run` are manual commands. Manual generation bypasses the scheduler's daily slot and can incur additional model cost.

## Runtime and content guards

The pipeline uses one generation batch and one evidence-review batch for up to four candidates. It preserves ModelGateway/ModelProvider boundaries, bounds source excerpts and output tokens, and defaults to no automatic model retries. Limits count all candidates, including rejected ones.

Versioned prompts request natural everyday Turkish, short observations, mild humor, and SaaS/app/AI/developer ideas. No emoji, corporate voice, artificial clickbait, required hooks/questions/lessons, account impersonation, or copying examples. Personal experiences may only use explicitly human-verified facts in `app.verified_user_context` (empty by default).

Untrusted source/model text is never authority. Claim coverage, source-specific evidence ownership, missing/fabricated evidence IDs, numeric assertions and personal-experience signals are checked. Unsupported drafts cannot be approved; they require editing and re-verification. Natural-language guards are not a complete truth guarantee; every post still needs human editorial approval.

## Review and delivery

`pending → approved → scheduled → publishing → published`

An approved draft can also be published immediately. Editing/re-verifying invalidates approval and scheduling; every mutation advances its revision, rejecting stale forms. The UI shows evidence, sources, model metadata, cost records, publication IDs and errors.

`X_PUBLISH_ENABLED=false` is the default. Setting it to `true` enables delivery only; it never approves content. The scheduled publisher selects only approved-origin drafts whose scheduled time has arrived. Pending/rejected drafts cannot be delivered.

X does not document a server idempotency key for `POST /2/tweets`, so exactly-once delivery cannot be guaranteed after an uncertain response. A durable atomic claim prevents another send attempt for the same draft. Timeouts, malformed success responses or process crashes after claiming are never automatically retried. `publish_unknown` or lingering `publishing` states require checking the X account before taking further action. `publish_failed` indicates a definite failure. This version does not automatically requeue failures.

No automated replies, DMs, follows, likes, reposts, media generation or multiple accounts.

## X connection

Official OAuth 1.0a user context is used for one account. Configure write permission in the X Developer App and create that account's access token/secret; regenerate user tokens after changing app permissions when necessary.

Environment variables: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`. Secrets are not stored in the database or repository. Redirects and automatic POST retries are disabled. Successful publishing persists the X post ID and UTC timestamp. A real test post requires explicit account-owner approval of the text and action; mock tests never contact X.

## Scheduler

Defaults: `Europe/Istanbul`, research every six hours, one batch of at most four candidates daily after 09:00, publication checks every 60 seconds. Configure timezone, generation time/day interval, research interval, publication interval and tick interval in `[scheduler]`. `SCHEDULER_ENABLED=false` pauses periodic work.

Slots are durably claimed in storage. Restarts or a second process cannot replay the same daily generation slot. Failed/crashed generation slots are not retried; the next schedule is used. Missed previous days are not generated as a backlog. Approval/schedule state survives restarts. Cloud workers use PostgreSQL; Railway defaults to one replica.

## Railway

The Dockerfile, `railway.json`, and `config/x-autopilot.cloud.toml` provide the deployment configuration. The image includes only runtime code and cloud config, excluding local databases, personal config and secrets. Add a PostgreSQL service and set the app's `DATABASE_URL` to `${{Postgres.DATABASE_URL}}`. Cloud mode rejects SQLite fallback. Startup applies migrations, with bounded retries for brief DB startup delays.

Start command:

```sh
python -m x_autopilot --config config/x-autopilot.cloud.toml serve
```

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL service reference |
| `OPENAI_API_KEY` | Luna Responses API secret |
| `PUBLIC_URL` | Railway HTTPS origin without a path |
| `REVIEW_USERNAME` | Single reviewer username |
| `REVIEW_PASSWORD` | Unique secret, at least 20 characters |
| `X_PUBLISH_ENABLED` | Initially `false` |
| `SCHEDULER_ENABLED` | Normally `true` |
| `PORT` | Provided by Railway |

X credentials are required only when delivery is enabled. Remote review uses HTTP Basic authentication over external HTTPS and fails closed without credentials/HTTPS origin. Local loopback may remain unauthenticated for development. `/health` and `/ready` expose no secrets; `/ready` checks database and combined-service scheduler health. Railway healthchecks run at deployment, not as continuous monitoring.

Authenticate Railway CLI or supply an appropriate project token, use `railway link` to verify the target project, select app/Postgres services, configure secrets in Railway Variables, then upload with `railway up`. These files are deployment preparation, not proof of successful deployment. Verify authentication, readiness, worker records and DB persistence at the deployed URL.

## Moving SQLite data to PostgreSQL

With `DATABASE_URL` pointing to an empty PostgreSQL destination, run `python -m x_autopilot import-sqlite /absolute/path/source.sqlite3`. The command reads a consistent, read-only snapshot, preserves IDs/relationships, and repairs PostgreSQL sequences. It refuses a destination containing application data and rolls back the copy on failure. The SQLite source is unchanged. Verify record counts and states in cloud review before enabling delivery.

## Tests and accounting

```sh
python scripts/validate.py
python -m unittest discover -s tests -v
```

Run PostgreSQL integration tests only against an isolated test database using `XAP_TEST_DATABASE_URL`. Tests require no real X/OpenAI credentials. Model call records contain input/output/cache token counts and an estimated USD amount with pricing provenance; output reasoning tokens are not counted twice.

The September 11, 2026 Luna experiment generated 15 raw candidates in one call for approximately **0.00199205 USD**, or **0.00013280333 USD per raw candidate**. This historical experiment excludes Phase 2 batch review and is not a measured cost per approved/published post. X API, hosting/Postgres and Codex development costs are excluded.

## Official references

- [X post integration](https://docs.x.com/x-api/posts/manage-tweets/integrate)
- [OAuth 1.0a user tokens](https://docs.x.com/fundamentals/authentication/oauth-1-0a/obtaining-user-access-tokens)
- [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles)
- [Railway healthchecks](https://docs.railway.com/deployments/healthchecks)
- [Railway PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Luna model/pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
