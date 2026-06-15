# Concierge Lead Gen Bot

Reviewer-first Telegram admin bot for a concierge workflow.

The bot does not publish anything automatically. It can read configured sources, find relevant posts with Claude, prepare a draft, and send it to a human reviewer in private messages. The reviewer can edit, cancel, approve, or mark the item as done.

## Stack

- Python 3.12
- aiogram 3.x
- Telethon read-only user session
- Claude via Anthropic SDK
- PostgreSQL
- SQLAlchemy 2.0 async
- Alembic
- APScheduler
- Docker

## Quick start

```bash
cp .env.example .env
```

Fill `.env`:

```env
BOT_TOKEN=123456:token
ADMIN_IDS=123456789
REVIEWER_CHAT_IDS=123456789
DATABASE_URL=postgresql+asyncpg://concierge:concierge@db:5432/concierge
TIMEZONE=Asia/Bangkok
ANTHROPIC_API_KEY=sk-ant-...
```

Run:

```bash
docker compose up -d --build
```

The container starts with:

```bash
alembic upgrade head && python main.py
```

Optional starter data:

```bash
docker compose run --rm bot python -m scripts.seed_templates
docker compose run --rm bot python -m scripts.seed_thailand_channels
```

## Claude and source monitoring setup

1. Add Telegram API data and Claude key to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
RELEVANCE_THRESHOLD=0.70
TG_API_ID=123456
TG_API_HASH=your_api_hash
TG_PHONE=+79999999999
TG_SESSION_NAME=concierge_session
```

2. Create the Telegram user session once:

```bash
docker compose run --rm bot python -m services.session_login
```

3. Seed Thailand monitoring sources or add them manually:

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```

```text
/add_channel @some_channel thailand relocation
/add_channel @some_realty_channel thailand realty
```

4. Enable monitoring:

```env
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
```

5. Restart:

```bash
docker compose restart bot
```

Flow after that:

```text
Source post
  -> Claude relevance score
  -> relevant item gets a draft
  -> reviewer receives a private card
  -> reviewer edits / cancels / approves / marks done
```

## Manual MVP workflow

1. Open the admin bot and press `/start`.
2. Add a source bucket:

```text
/add_channel @manual thailand relocation
```

3. For instant reviewer delivery during testing, set delay to zero:

```text
/set_channel_delay 1 0 0
```

4. Add an item manually:

```text
/add_item 1 https://t.me/example/123 Текст поста или запроса клиента
```

Use `-` instead of URL if there is no link:

```text
/add_item 1 - Текст без ссылки
```

5. Open pending list:

```text
/pending
```

6. Press `Approve now` for immediate routing, or `Approve` for normal delay.
7. The bot creates a draft and sends it to `REVIEWER_CHAT_IDS`.
8. Reviewer checks the text, sends it manually, then presses `Done`.

Useful inspection commands:

```text
/approved_queue
/draft <post_id>
/source <post_id>
/saved_queue
/content_ideas
/daily_report
/channel_stats
```

If an approved draft is waiting because of delay, force it into the reviewer queue:

```text
/dispatch_now <post_id>
```

## Commands

### Main

```text
/start
/help
/health
/stats
/queue_stats
/daily_report
/channel_stats
/settings
/pause
/resume
```

### Channels

```text
/channels
/add_channel @manual thailand relocation
/set_channel_limit 1 5
/set_channel_delay 1 0 0
```

### Items and review

```text
/add_item <channel_id> <url_or_dash> <text>
/pending
/approved_queue
/review_queue
/saved_queue
/content_ideas
/source <post_id>
/draft <post_id>
/dispatch_now <post_id>
/edit_draft <post_id> <new text>
```

### Leads and deals

```text
/leads
/add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>
/lead_status <lead_id> <new|contacted|converted|dead>
/deal <lead_id> <amount>
```

A deal adds 40 percent of the amount to the revenue counter.

### Templates

```text
/templates
/add_template thailand relocation Текст шаблона
/disable_template <template_id>
```

Templates are used before hardcoded fallback drafts.

## Health and operations

```text
/health
/queue_stats
/daily_report
/channel_stats
```

`/health` checks the database connection and pause flag. `/queue_stats` shows how many items are in every workflow status. `/daily_report` shows source quality summary. `/channel_stats` shows per-channel quality.

## Important notes

- The GitHub MVP is reviewer-first and does not send public messages automatically.
- Every reviewer must open the bot and press `/start`, otherwise Telegram will not allow the bot to write first.
- `.env` and Telegram session files must never be committed.
- The user session is used only for reading configured sources.

## Project structure

```text
bot/
core/
db/
services/
scripts/
main.py
Dockerfile
compose.yaml
alembic.ini
requirements.txt
```
