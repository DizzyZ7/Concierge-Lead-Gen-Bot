# Thailand Lead Radar — Launch Runbook

Checklist for the first production launch.

## 1. Preflight

- Create a private `.env` from `.env.example`.
- On BotHost, set `DATABASE_URL` to the external managed PostgreSQL connection string. Do not use `localhost` or `db:5432` there.
- Replace the example `POSTGRES_PASSWORD` only when using the bundled local PostgreSQL service.
- Keep `OUTBOUND_ENABLED=false` and `AUTOMATION_LEVEL=assisted`.
- Confirm `ADMIN_IDS` contains the operator Telegram user ID.
- Confirm `REVIEWER_CHAT_IDS` contains the private reviewer chat ID or the group/supergroup ID used for reviewer cards.
- If `REVIEWER_CHAT_IDS` is a group/supergroup, add the bot to the chat manually and grant send permission before deploy.
- Add `ANTHROPIC_API_KEY`, `TG_API_ID`, `TG_API_HASH`, and `TG_PHONE`.
- Make sure every reviewer has opened the bot and pressed `/start` at least once.

Recommended initial monitoring settings:

```env
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
RELEVANCE_THRESHOLD=0.70
```

The parser has a built-in safety guard and ignores source posts older than 24 hours on the first monitoring pass.

## 2. Database and session

### BotHost production

BotHost starts the bot with one direct command:

```bash
python main.py
```

`main.py` is the single production entrypoint. It loads `.env`, checks the external PostgreSQL connection with retry, applies `alembic upgrade head` when needed, deletes any stale Telegram webhook, checks reviewer-chat reachability, and then starts aiogram polling.

Expected startup log events:

```text
database_connection_ok
telegram_webhook_deleted
startup_self_check
```

If a reviewer group is unreachable, the log event is `reviewer_chat_unreachable`; add the bot to the chat and redeploy/restart.

Manual BotHost shell checks, if needed:

```bash
python -m alembic current
python -m alembic upgrade head
python -m scripts.smoke_check
python -m scripts.preflight_check
```

### Docker/local

Use the default `compose.yaml` for the bundled local PostgreSQL service. If production uses a managed PostgreSQL database, set `DATABASE_URL` to that external connection string and replace `docker compose` with `docker compose -f compose.external-db.yaml` in the commands below.

The application accepts both `postgresql://...` and `postgresql+asyncpg://...` formats for `DATABASE_URL`.

Check and apply migrations:

```bash
docker compose run --rm bot alembic current
docker compose run --rm bot alembic upgrade head
```

Seed the initial Thailand source list and its filters:

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```

Create the Telegram user session once:

```bash
docker compose run --rm bot python -m services.session_login
```

Validate the configured Telegram sources before strict preflight:

```bash
docker compose run --rm bot python -m scripts.validate_channels
```

## 3. Smoke check and start

Run the code smoke check before the first start:

```bash
docker compose run --rm bot python -m scripts.smoke_check
docker compose run --rm bot python -m scripts.preflight_check
docker compose run --rm bot python -m scripts.preflight_check --strict
```

Build and start the stack:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

The bot container and direct BotHost entrypoint both apply `alembic upgrade head` before polling.

## 4. Acceptance test in Telegram

1. Open the bot and run `/health`.
2. Confirm database is connected and reviewer count is correct.
3. Run `/channels` and confirm all intended sources are active.
4. Create one safe manual test item:

```text
/add_item <channel_id> - Тестовый запрос по аренде жилья на Пхукете
```

5. Open `/pending`, press `Одобрить сейчас`, and confirm the reviewer receives a card.
6. Press `Стал лидом` and confirm the new item appears in `/leads`.
7. Check `/daily_report`, `/channel_stats`, and `/queue_stats`.
8. Test `/failed_queue` only if a controlled failure is available; do not intentionally break production credentials.

## 5. First three days

Keep reviewer-first mode. Do not enable any public outbound automation.

Review twice per day:

```text
/health
/daily_report
/channel_stats
/queue_stats
/failed_queue
```

Tune channel filters based on real noise:

```text
/set_channel_min_score <channel_id> <0.00-1.00>
/set_channel_intents <channel_id> <intent1,intent2>
/set_channel_blocklist <channel_id> <word1,word2>
```

## 6. Backup and rollback

Before a deployment, create a database backup:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U concierge concierge > backups/concierge_$(date +%Y%m%d_%H%M%S).sql
```

For a code rollback, return the repository to the last known-good commit, then rebuild:

```bash
git log --oneline -10
git checkout <known-good-commit>
docker compose up -d --build
```

Do not roll back database migrations without a tested restore plan. Restore a database backup only during a controlled maintenance window.

## 7. Launch exit criteria

The launch is ready only when all of these are true:

- `/health` reports a live reviewer heartbeat.
- Parser heartbeat appears after its first interval when monitoring is enabled.
- At least one manual item reaches a reviewer card.
- A lead created from a post appears in `/leads` with source context.
- `/failed_queue` is empty.
- No recurring error alert is arriving to admins.
- Mikhail confirms that the cards, drafts, and source filters are useful on real channels.
