# Project Handoff

## Updated
- UTC: 2026-07-12 10:40:28 UTC
- Branch: `main`
- Current commit before this handoff refresh: `34dbda46afc1ee370883ccfcdaa6693d9e6e4de2`

## Current state
Thailand Lead Radar remains prepared for reviewer-first startup with PostgreSQL schema gating, managed database support, no-polling preflight, source validation, role separation, reviewer claims, audit history and CI quality gates. Reviewer claim enforcement is now stricter: a live reviewer card requires an owned active claim before any protected change, claim verification fails closed, and an atomic action lease closes the timeout-boundary race. Live Telegram polling, real reviewer delivery and Claude operation are still not verified in the current environment.

## Completed
- Made reviewer claim ownership mandatory for protected actions on `sent_to_reviewer` cards.
- Changed claim middleware from fail-open to fail-closed when ownership cannot be verified.
- Added an atomic five-minute action lease before protected actions so a near-expiry claim cannot be taken between verification and the status change.
- Added pure unit coverage for required claims, owner access, other-reviewer blocking and admin override.
- Added PostgreSQL integration coverage for concurrent claims and action-lease renewal.
- Updated reviewer claim documentation.

## Changed files
- `services/reviewer_claims.py` - added mandatory claim decisions and atomic action lease.
- `bot/middlewares/reviewer_claim_guard.py` - requires and atomically secures ownership before protected actions; errors cancel the action.
- `tests/test_reviewer_claims.py` - covers claim access rules.
- `tests/test_reviewer_claims_db.py` - covers PostgreSQL claim concurrency and near-expiry action lease.
- `docs/REVIEWER_CLAIMS.md` - documents mandatory claims, fail-closed checks and action lease behavior.
- `docs/PROJECT_HANDOFF.md` - refreshed continuation state.

## Database and migrations
- Required Alembic revision: `0010_reviewer_claims`.
- Current migration head: `0010_reviewer_claims`.
- Migration applied in environment: previously yes against the provided external PostgreSQL database; no migration was added or applied in this session.
- Commands for applying migrations:
  - Bundled DB: `docker compose run --rm bot alembic upgrade head`
  - Managed DB: `docker compose -f compose.external-db.yaml run --rm bot alembic upgrade head`

## Tests and verification
- New unit and PostgreSQL integration tests were committed but were not executed from this session because no local repository runtime or test database was available.
- The PostgreSQL integration test uses `TEST_DATABASE_URL` explicitly outside CI and only falls back to `DATABASE_URL` when `CI=true`, avoiding accidental execution against a normal runtime database.
- GitHub combined status returned no status checks for the latest direct-push commit.
- Commit workflow lookup also returned no runs for the latest direct-push commit.
- Previous verified baseline remains: migration `0010_reviewer_claims`, compileall, 63 tests, smoke-check, Compose validation and non-strict preflight passed in the prior prepared workspace.

## Runtime and deployment
- Deployed: unknown.
- Docker/server status: not checked in this session.
- Parser state: not checked; live Telegram user session remains unverified.
- Reviewer state: code paths hardened; real two-reviewer Telegram interaction not verified.
- Claude state: not checked; fallback behavior remains required.
- Required environment variables without secret values: `BOT_TOKEN`, `ADMIN_IDS`, `REVIEWER_CHAT_IDS`, `REVIEWER_USER_IDS` for group/supergroup delivery, `DATABASE_URL`, `TIMEZONE`, `OUTBOUND_ENABLED=false`, `PARSER_ENABLED`, `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`, `TG_SESSION_NAME`, optional `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL`.

## Known risks and unresolved issues
- The new tests still need execution on GitHub Actions or a local PostgreSQL test environment.
- Live reviewer claims should be verified with two real reviewer users in a private test group.
- Real Telegram bot token, reviewer IDs, Telethon credentials/session and optional Claude key are still required in the private runtime environment.
- Seeded Telegram sources still require live validation.
- Keep `OUTBOUND_ENABLED=false` as the launch baseline.

## Next recommended task
Run the full test suite against PostgreSQL and then perform a private two-reviewer staging check: claim a card, attempt a conflicting action from the second reviewer, test near-expiry renewal, release the claim and verify `/post_history`. This is the highest-value next step because the claim rules are now production-hardened in code but not yet verified through real Telegram delivery.

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
- Daily limits and statistics must respect `TIMEZONE`.
- Migration gate must prevent startup on stale schema.
- Public usernames and `t.me` links remain unverified contact candidates only.
