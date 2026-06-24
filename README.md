# Thailand Lead Radar

Reviewer-first Telegram lead radar for Thailand concierge workflows.

The bot reads only configured Telegram sources through a separate Telethon user session, scores posts, prepares reviewer cards and drafts, and keeps a small lead CRM. It **does not publish comments or contact people automatically**. Any external action remains a human decision.

## What the bot does

```text
Telegram source post
  -> relevance and intent scoring
  -> per-channel filters and daily caps
  -> reviewer card with a draft and public contact hints
  -> human decision
  -> lead / comment / idea / saved / skipped
  -> audit history and CRM follow-up
```

Key capabilities:

- read-only Telegram monitoring;
- Claude scoring with local fallback;
- per-source score thresholds, intents, stop words, delays and daily draft caps;
- manual reviewer workflow with no external auto-send;
- source validation, parser health checks and launch readiness checks;
- reviewer backlog and limit queue;
- leads, notes, follow-ups, deals and actual commission tracking;
- source quality analytics;
- immutable audit history for key reviewer actions;
- separate delivery chats and reviewer user permissions.

## Stack

- Python 3.12
- aiogram 3
- Telethon read-only user session
- Anthropic SDK / Claude
- PostgreSQL 16
- SQLAlchemy async + Alembic
- APScheduler
- Docker Compose

## Safety model

`OUTBOUND_ENABLED=false` is the expected launch mode.

The bot may automatically read configured sources, score text, create a private reviewer card, validate channel access and send operational alerts. It does not automatically post a public comment, send a direct message, join a chat, or change source content.

## Configuration

Create the local config:

```bash
cp .env.example .env
```

Minimum example for a personal reviewer chat:

```env
BOT_TOKEN=123456:token
ADMIN_IDS=123456789
REVIEWER_CHAT_IDS=123456789
DATABASE_URL=postgresql+asyncpg://concierge:concierge@db:5432/concierge
TIMEZONE=Asia/Bangkok
PARSER_ENABLED=false
OUTBOUND_ENABLED=false
```

For a reviewer group or supergroup, delivery and permissions are separate:

```env
REVIEWER_CHAT_IDS=-1001234567890
REVIEWER_USER_IDS=123456789,987654321
```

- `REVIEWER_CHAT_IDS` — where the cards are sent; a personal chat or a negative group/supergroup ID.
- `REVIEWER_USER_IDS` — personal Telegram IDs allowed to press reviewer buttons and use reviewer commands.
- For a personal reviewer chat, existing behavior remains compatible: when `REVIEWER_USER_IDS` is omitted, a positive delivery chat ID is treated as that reviewer user ID.

Never commit `.env` or files in `sessions/`.

## Deploy and migration gate

The application requires Alembic revision `0009_post_action_audit`. The bot checks this before polling; a stale database schema prevents startup instead of causing hidden runtime errors.

Recommended first deployment:

```bash
docker compose up -d db
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot python -m scripts.smoke_check
docker compose up -d --build bot
docker compose logs -f bot
```

The Docker image also runs `alembic upgrade head` before `python main.py`, but the explicit migration command above makes a first deployment and troubleshooting clearer.

## Telegram source monitoring setup

Add Telegram API and Claude configuration to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
RELEVANCE_THRESHOLD=0.70
TG_API_ID=123456
TG_API_HASH=your_api_hash
TG_PHONE=+79999999999
TG_SESSION_NAME=concierge_session
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
```

Create the Telegram user session once:

```bash
docker compose run --rm bot python -m services.session_login
```

Seed initial Thailand sources or add them manually:

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```

```text
/add_channel @some_channel thailand relocation
/add_channel @some_realty_channel thailand realty
```

## First staging pass

After the bot starts, use this order in Telegram:

```text
/validate_channels
/launch_check
/set_business_context <фактическое описание услуг и аудитории>
/scan_now
/pending
/approved_queue
/review_queue
/reviewer_backlog
```

`/validate_channels` checks each active source using the current Telegram user session. A successful validation is fresh for seven days. `/launch_check` requires fresh validation for every active channel.

Use `/scan_now` after adding a source or resetting its cursor. The command shares the same lock with the scheduler, so it does not duplicate parser work.

## Roles

### Reviewer

Reviewer actions are limited to the working queue:

```text
/start
/help
/stats
/daily_report
/pending
/approved_queue
/review_queue
/reviewer_backlog [hours]
/saved_queue
/content_ideas
/source <post_id>
/draft <post_id>
/edit_draft <post_id> <new text>
```

A reviewer may approve, save, skip, mark as processed, mark a public comment as written, create a lead or mark an item as an idea. Reviewer menus do not expose channel management, system health, CRM management, deals, revenue or operational configuration.

### Administrator

Admins additionally manage sources, parser and source validation, system health, templates, lead CRM, follow-ups, actual commission and audit history.

Important commands:

```text
/health
/launch_check
/channels
/validate_channels
/scan_now
/promote_limit_queue
/channel_stats
/source_quality 7
/leads
/followups
/deal <lead_id> <actual_commission_amount>
/post_history <post_id>
```

## Per-channel tuning

```text
/set_channel_limit <channel_id> <limit>
/set_channel_delay <channel_id> <min> <max>
/set_channel_min_score <channel_id> <0.00-1.00|->
/set_channel_intents <channel_id> <intent1,intent2|->
/set_channel_blocklist <channel_id> <word1,word2|->
/reset_channel_cursor <channel_id>
```

Useful intents include `relocation`, `realty`, `visa`, `tourism`, `investment`, `business`, `finance` and `expat_life`.

## Reviewer workflow

1. A source post receives a relevance score and intent.
2. If it passes the source filters, the bot creates a reviewer draft.
3. The reviewer checks the source, edits the draft if necessary and acts manually outside the bot.
4. In the card, the reviewer records the outcome: comment, lead, idea, saved, skipped, irrelevant or done.
5. Public Telegram handles found inside the source text are shown as **unverified candidates** only. The reviewer must verify ownership before any contact.
6. “Стал лидом” creates a CRM lead with the source, geo, intent and a note containing any public contact candidates.

## Queues and operations

```text
/pending
/approved_queue
/limit_queue
/review_queue
/reviewer_backlog [hours]
/saved_queue
/content_ideas
/failed_queue
```

- `limit_queue` holds relevant posts that could not be drafted because of a source daily cap.
- `reviewer_backlog` shows cards already delivered to a reviewer but unresolved for more than the chosen number of hours; it does not send automatic reminders or change statuses.
- `failed_queue` keeps individual processing failures for manual retry instead of losing the source post.

## Analytics and CRM

```text
/daily_report
/channel_stats
/source_quality 7
/leads [new|contacted|converted|dead|all]
/lead <lead_id>
/lead_status <lead_id> <new|contacted|converted|dead>
/lead_note <lead_id> <text>
/followups [hours]
/deal <lead_id> <actual_commission_amount>
```

`/deal` records the **actual earned commission** passed to the command. The bot does not apply a hidden percentage or infer turnover.

## Audit history

Key human actions are recorded in the append-only `post_actions` table:

- lead created;
- comment marked as written;
- content idea;
- irrelevant;
- saved;
- skipped;
- reviewer marked as done.

Inspect the history as an admin:

```text
/post_history <post_id>
```

See `docs/POST_AUDIT.md` and `docs/OPERATIONS.md` for operational details.

## Health and CI

`/health` reports database connectivity, parser, reviewer dispatcher, limit queue and source-validation health. It is admin-only.

GitHub Actions runs:

```text
compileall
alembic upgrade head on clean PostgreSQL
unittest discovery
smoke check
```

## Project structure

```text
bot/        Telegram handlers, filters and middleware
a core/      Configuration and logging
db/         Models, migrations and queries
services/   Parser, AI, reviewer flow and operations
scripts/    Seeds and smoke checks
docs/       Operations and audit runbooks
```
