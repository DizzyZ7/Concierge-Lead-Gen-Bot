# Project Handoff

## Updated
- UTC: 2026-07-12 10:45 UTC
- Branch: `main`
- Current commit before this handoff refresh: `11631a59ce7eb2d20e00cccbe526881aa4a0dcf4`

## Current state
Thailand Lead Radar remains prepared for reviewer-first startup with PostgreSQL schema gating, managed database support, no-polling preflight, source validation, role separation, mandatory reviewer claims, audit history and CI quality gates. Claim enforcement is fail-closed and uses an atomic action lease to protect near-expiry actions. The project now also has an isolated PostgreSQL business-workflow self-test for `post -> draft -> reviewer claim -> claim guard -> lead -> audit`. Live Telegram polling, real reviewer delivery, parser monitoring and Claude operation are still not verified in the current environment.

## Completed
- Kept mandatory reviewer claim ownership for protected actions on `sent_to_reviewer` cards.
- Kept fail-closed claim verification and atomic action lease behavior.
- Extracted post-to-lead conversion from the Telegram handler into a reusable service layer.
- Added an isolated PostgreSQL workflow self-test that creates a temporary schema and drops it in `finally`.
- The workflow self-test checks claim ownership, second-reviewer blocking, one-lead idempotency, public contact warnings, audit creation and claim cleanup.
- Removed the database query layer dependency on full Telegram/runtime settings for business-date calculation.
- Added a separate GitHub Actions workflow for the isolated PostgreSQL test without Telegram credentials.
- Added unit coverage for lead notes, business timezone behavior and the workflow CI contract.
- Updated README and launch runbook to require claim before protected reviewer actions and include the new self-test.

## Changed files
- `services/reviewer_claims.py` - mandatory claim decisions and atomic action lease from the previous hardening series.
- `bot/middlewares/reviewer_claim_guard.py` - fail-closed ownership checks from the previous hardening series.
- `tests/test_reviewer_claims.py` - claim access unit coverage.
- `tests/test_reviewer_claims_db.py` - PostgreSQL claim concurrency and action-lease coverage.
- `services/lead_conversion.py` - reusable idempotent post-to-lead conversion and safe initial notes.
- `bot/handlers/results.py` - uses the lead conversion service instead of handler-local business logic.
- `scripts/workflow_selftest.py` - isolated temporary-schema PostgreSQL workflow verification.
- `db/queries.py` - business date reads only `TIMEZONE`, not the complete runtime settings object.
- `tests/test_lead_conversion.py` - lead note and unverified-contact coverage.
- `tests/test_business_time.py` - explicit, environment and invalid timezone coverage.
- `.github/workflows/workflow-selftest.yml` - migration plus isolated reviewer workflow gate.
- `tests/test_ci_workflow.py` - verifies the new workflow has no Telegram credential dependency.
- `docs/REVIEWER_CLAIMS.md` - mandatory claim and action lease documentation.
- `docs/LAUNCH_RUNBOOK.md` - adds workflow self-test and claim-aware Telegram acceptance steps.
- `README.md` - documents claim workflow, database self-test and CI gate.
- `docs/PROJECT_HANDOFF.md` - refreshed continuation state.

## Database and migrations
- Required Alembic revision: `0010_reviewer_claims`.
- Current migration head: `0010_reviewer_claims`.
- Migration applied in environment: previously yes against the provided external PostgreSQL database; no migration was added or applied in this session.
- Commands for applying migrations:
  - Bundled DB: `docker compose run --rm bot alembic upgrade head`
  - Managed DB: `docker compose -f compose.external-db.yaml run --rm bot alembic upgrade head`

## Tests and verification
- New unit, PostgreSQL integration and workflow self-test code was committed but was not executed from this session.
- A local clean clone attempt failed because the container could not resolve `github.com`.
- GitHub combined status and workflow lookup returned no status checks or runs for the latest direct-push commits; do not treat CI as passed yet.
- The new workflow self-test is isolated in a temporary schema and does not require Telegram credentials.
- Previous verified baseline remains: migration `0010_reviewer_claims`, compileall, 63 tests, smoke-check, Compose validation and non-strict preflight passed before the latest claim and workflow changes.

## Runtime and deployment
- Deployed: unknown.
- Docker/server status: not checked in this session. Previous Docker image pulls were blocked by Docker Hub `short read` / `unexpected EOF` failures.
- Parser state: not checked; live Telegram user session remains unverified.
- Reviewer state: claim and workflow code paths are hardened; real two-reviewer Telegram interaction is not verified.
- Claude state: not checked; fallback and cooldown remain required.
- Required environment variables without secret values: `BOT_TOKEN`, `ADMIN_IDS`, `REVIEWER_CHAT_IDS`, `REVIEWER_USER_IDS` for group/supergroup delivery, `DATABASE_URL`, `TIMEZONE`, `OUTBOUND_ENABLED=false`, `PARSER_ENABLED`, `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`, `TG_SESSION_NAME`, optional `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL`.

## Known risks and unresolved issues
- The new tests and isolated workflow self-test still need a successful GitHub Actions or local PostgreSQL run.
- The isolated workflow self-test requires permission to create and drop a temporary schema. Managed PostgreSQL roles without `CREATE` privilege need a dedicated test database or maintenance role.
- Live reviewer claims should be verified with two real reviewer users in a private test group.
- Real Telegram bot token, reviewer IDs, Telethon credentials/session and optional Claude key are still required in the private runtime environment.
- Seeded Telegram sources still require live validation.
- Keep `OUTBOUND_ENABLED=false` as the launch baseline.

## Next recommended task
Run the GitHub Actions gates and `python -m scripts.workflow_selftest`, then perform a private two-reviewer staging check: claim a card, attempt a conflicting action from the second reviewer, verify action-lease behavior, create a lead and inspect `/post_history`. After that, run `python -m services.session_login`, `python -m scripts.validate_channels` and `python -m scripts.preflight_check --strict` in the private runtime.

## Do not break
- No automatic public comments, DMs, chat joins, source posts or external contact actions.
- Reviewer-first, human-in-the-loop workflow remains mandatory.
- One source post must not create duplicate leads.
- Reviewer group delivery requires explicit positive `REVIEWER_USER_IDS`.
- A live reviewer card requires an owned active claim before protected edits or outcomes.
- Claim verification failures must cancel the action, not bypass ownership.
- Reviewer claims must support timeout, owner renew/release, admin override and cleanup after final outcome.
- Key reviewer and claim actions must be written to `post_actions`.
- Telegram HTML must be escaped and message length must remain within Telegram limits.
- AI provider failure must not stop parsing; fallback and cooldown must remain available.
- Daily limits and statistics must respect `TIMEZONE` without requiring unrelated Telegram settings.
- Migration gate must prevent startup on stale schema.
- Public usernames and `t.me` links remain unverified contact candidates only.
