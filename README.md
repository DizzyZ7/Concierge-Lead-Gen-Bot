# Concierge Lead Gen Bot

Reviewer-first Telegram admin bot for a concierge workflow.

The current GitHub version is a safe MVP: it does not publish anything automatically. The owner adds or approves an item, the bot prepares a draft, then sends that draft to a human reviewer in private messages. The reviewer manually checks the text, sends it where needed, and marks it as done in the bot.

## Stack

- Python 3.12
- aiogram 3.x
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
```

Run:

```bash
docker compose up -d --build
```

The container starts with:

```bash
alembic upgrade head && python main.py
```

## MVP workflow

1. Open the admin bot and press `/start`.
2. Add a source bucket:

```text
/add_channel @manual thailand relocation
```

3. Add an item manually:

```text
/add_item 1 https://t.me/example/123 Текст поста или запроса клиента
```

Use `-` instead of URL if there is no link:

```text
/add_item 1 - Текст без ссылки
```

4. Open pending list:

```text
/pending
```

5. Press `Approve`.
6. The bot creates a draft and sends it to `REVIEWER_CHAT_IDS`.
7. Reviewer checks the text, sends it manually, then presses `Done`.

## Commands

### Main

```text
/start
/stats
/settings
/pause
/resume
```

### Channels

```text
/channels
/add_channel @manual thailand relocation
/set_channel_limit 1 5
```

### Items and review

```text
/add_item <channel_id> <url_or_dash> <text>
/pending
/edit_draft <post_id> <new text>
/review_queue
```

### Leads and deals

```text
/leads
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

## Important notes

- The GitHub MVP is reviewer-first and does not send public messages automatically.
- Every reviewer must open the bot and press `/start`, otherwise Telegram will not allow the bot to write first.
- `.env` and Telegram session files must never be committed.
- The full experimental version with user session parsing is not required for the MVP launch.

## Project structure

```text
bot/
core/
db/
services/
main.py
Dockerfile
compose.yaml
alembic.ini
requirements.txt
```
