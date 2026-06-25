# Project Handoff

## Updated
- UTC: 2026-06-25 22:54:11 UTC
- Branch: unknown; this workspace has no `.git` metadata.
- Current commit: unknown; this workspace has no `.git` metadata.

## Current state
Thailand Lead Radar is prepared for reviewer-first startup with managed PostgreSQL support, schema gating, no-polling preflight, source-validation CLI, safer reviewer access checks, and CI launch gates. The provided external PostgreSQL database is migrated to `0010_reviewer_claims` and seeded with starter Thailand channels/templates. Local Python checks pass. Live Telegram session, real bot polling, reviewer delivery, Claude credentials, remote CI, and Docker image build are not fully verified from this workspace.

## Completed
- Aligned required migration revision with actual Alembic head `0010_reviewer_claims`.
- Applied migrations to the provided external PostgreSQL database and seeded starter channels/templates.
- Added plain `postgresql://` normalization to asyncpg URLs for runtime and Alembic.
- Added managed PostgreSQL Compose path via `compose.external-db.yaml`.
- Added no-polling startup preflight with strict unsafe-config checks.
- Added no-polling Telegram source-validation CLI with schema gate before Telegram connect.
- Added reviewer group safety check requiring explicit positive `REVIEWER_USER_IDS`.
- Fixed Russian Pattaya inflection matching in fallback geo scoring.
- Added unit/smoke coverage for URL normalization, preflight blockers, source-validation helpers, and CI gates.
- Updated README, operations docs, launch runbook, and CI workflow for managed DB and preflight flow.

## Changed files
- `README.md` - updated required revision and managed PostgreSQL launch flow.
- `.github/workflows/ci.yml` - added valid test bot token, compose config checks, and no-polling preflight.
- `.env.example` - added reviewer user IDs and local PostgreSQL variables.
- `compose.yaml` - made `.env` optional and forwards bot/database env vars explicitly.
- `compose.external-db.yaml` - added bot-only Compose config for managed PostgreSQL.
- `db/session.py` - added database URL normalization.
- `db/migrations/env.py` - applies URL normalization for Alembic.
- `scripts/preflight_check.py` - added launch preflight and strict config blocker checks.
- `scripts/validate_channels.py` - added source validation CLI.
- `scripts/smoke_check.py` - added smoke assertions for DB URL normalization and preflight blockers.
- `services/ai.py` - added Pattaya stem alias.
- `tests/test_database_url.py` - added DB URL normalization tests.
- `tests/test_preflight_check.py` - added preflight blocker tests.
- `tests/test_validate_channels_script.py` - added validation helper tests.
- `tests/test_ci_workflow.py` - added CI quality gate tests.
- `docs/OPERATIONS.md` - documented managed DB, preflight, and strict prerequisites.
- `docs/LAUNCH_RUNBOOK.md` - documented command order for managed DB launch.
- `docs/PROJECT_HANDOFF.md` - refreshed project state and verification status without secrets.

## Database and migrations
- Required Alembic revision: `0010_reviewer_claims`.
- Current migration head: `0010_reviewer_claims`.
- Migration applied in environment: yes, against the provided external PostgreSQL database.
- Command for applying migrations:
  - Bundled DB: `docker compose run --rm bot alembic upgrade head`
  - Managed DB: `docker compose -f compose.external-db.yaml run --rm bot alembic upgrade head`

## Tests and verification
- Ran `.venv\Scripts\python.exe -m alembic upgrade head` against the provided external PostgreSQL database: passed.
- Ran `.venv\Scripts\python.exe -m alembic current`: `0010_reviewer_claims (head)`.
- Ran runtime schema guard against the provided external PostgreSQL database: `0010_reviewer_claims`.
- Ran starter seed scripts against the provided external PostgreSQL database: 8 channels and 4 templates present/added.
- Ran `.venv\Scripts\python.exe -m compileall -q .`: passed.
- Ran `.venv\Scripts\python.exe -m unittest discover -s tests -v`: passed, 60 tests.
- Ran `.venv\Scripts\python.exe -m scripts.smoke_check`: passed.
- Ran `docker compose config` and `docker compose -f compose.external-db.yaml config`: passed with CI-style env.
- Ran `.venv\Scripts\python.exe -m scripts.preflight_check` against external DB with safe test env: passed, `Config blockers: 0`.
- Ran strict preflight with safe test env: correctly failed because live launch blockers remain.
- Ran secret scan for provided DB URL fragments outside `.venv`/cache: no matches.
- CI status: GitHub Actions passed for PR #1 commit `c360fa3`: `CI` run 224 and `Python check` run 310.

## Runtime and deployment
- Deployed: unknown.
- Docker/server status: Docker daemon is reachable (`29.3.1`); image build is blocked by Docker Hub/base image pull failures (`short read` / `unexpected EOF` for `python:3.12-slim`, also seen for `postgres:16-alpine`).
- Parser state: not running; safe checks used `PARSER_ENABLED=false`.
- Reviewer state: preflight wiring verified with test reviewer values; real Telegram delivery not verified.
- Claude state: not verified; launch check reports fallback mode without configured key.
- Required environment variables without secret values: `BOT_TOKEN`, `ADMIN_IDS`, `REVIEWER_CHAT_IDS`, `REVIEWER_USER_IDS` for group/supergroup reviewer delivery, `DATABASE_URL`, `TIMEZONE`, `OUTBOUND_ENABLED=false`, `PARSER_ENABLED`, `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`, `TG_SESSION_NAME`, optional `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL`.

## Known risks and unresolved issues
- No `.git` metadata is present in the original workspace, so local branch/current commit cannot be verified there; changes were pushed from a temporary clean clone to PR #1.
- Docker build cannot complete until Docker Hub image downloads are stable or base images are available locally.
- Real Telegram bot token, admin/reviewer IDs, Telethon API credentials, phone/session, and optional Claude key are still needed in private runtime environment.
- Seeded Telegram sources still need live validation through `python -m services.session_login` and `python -m scripts.validate_channels`.
- Strict preflight will remain red until parser credentials/session, source validation, runtime heartbeats, and optional Claude readiness are handled.
- Keep `OUTBOUND_ENABLED=false` as the baseline launch mode.

## Next recommended task
Create a private runtime environment with real Telegram bot/reviewer/parser credentials, then run `python -m services.session_login`, `python -m scripts.validate_channels`, and `python -m scripts.preflight_check --strict`. This is the highest-value next step because schema, seeded data, local tests, source-validation CLI, and no-polling startup wiring are verified, but live Telegram readiness is not.

## Do not break
- No automatic public comments, DMs, chat joins, source posts, or external contact actions.
- Reviewer-first, human-in-the-loop workflow remains mandatory.
- One source post must not create duplicate leads.
- Reviewer group delivery must require explicit positive `REVIEWER_USER_IDS`.
- Active claims must prevent another reviewer from closing/editing the card.
- Reviewer claims must support timeout, owner renew/release, admin release, and cleanup after final outcome.
- Key reviewer actions must be written to `post_actions`.
- Telegram HTML must be escaped and message length must stay within Telegram limits.
- AI provider failure must not stop parsing; local fallback and cooldown behavior must keep source processing available.
- Daily limits and statistics must respect `TIMEZONE`.
- Migration gate must prevent startup on stale schema.
- Public usernames and `t.me` links are unverified contact candidates only.
