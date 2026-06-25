# Thailand Lead Radar — Operations

## Deployment gate

The application starts only when the database schema is on the current Alembic revision. Before every deploy with new code, run:

```bash
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot python -m scripts.smoke_check
docker compose run --rm bot python -m scripts.preflight_check
docker compose up -d --build
```

For a managed PostgreSQL database, put its connection string into `DATABASE_URL` and use the external-db compose file so the bot does not try to start the bundled local database:

```bash
docker compose -f compose.external-db.yaml run --rm bot alembic upgrade head
docker compose -f compose.external-db.yaml run --rm bot python -m scripts.smoke_check
docker compose -f compose.external-db.yaml run --rm bot python -m scripts.seed_thailand_channels
docker compose -f compose.external-db.yaml run --rm bot python -m services.session_login
docker compose -f compose.external-db.yaml run --rm bot python -m scripts.validate_channels
docker compose -f compose.external-db.yaml run --rm bot python -m scripts.preflight_check
docker compose -f compose.external-db.yaml run --rm bot python -m scripts.preflight_check --strict
docker compose -f compose.external-db.yaml up -d --build
```

Both `postgresql://...` and `postgresql+asyncpg://...` database URLs are accepted by the application.

Strict preflight requires seeded channels, an authorized Telegram user session, and fresh source validation. For ordinary code-only deploys after launch, rerun `scripts.validate_channels` when sources or Telegram credentials changed.

When migrations are behind, the bot exits before Telegram polling and logs the exact revision mismatch. This prevents a partially running process against an outdated schema.

## Reviewer delivery and access

`REVIEWER_CHAT_IDS` controls where reviewer cards are delivered. It may contain a personal chat ID or a negative group/supergroup ID.

`REVIEWER_USER_IDS` controls who may press reviewer buttons and use reviewer commands. It must contain only positive personal Telegram user IDs.

For a personal reviewer chat, existing configuration remains compatible: a positive chat ID is treated as that user's ID when `REVIEWER_USER_IDS` is omitted.

For a group delivery chat, add explicit users before launch:

```text
REVIEWER_CHAT_IDS=-1001234567890
REVIEWER_USER_IDS=123456789,987654321
```

The bot never treats a negative group ID as a human user ID. `/launch_check` warns when a reviewer group is configured without authorized reviewer users.

## Daily checks

```text
/health
/daily_report
/channel_stats
/queue_stats
/reviewer_backlog
/failed_queue
/followups
```

`/health` must show live parser, reviewer, daily-limit-queue, and source-validation heartbeats. A stale heartbeat or a recent error requires review before adding more sources.

`/reviewer_backlog` shows cards that were already delivered to a reviewer but remain unresolved for more than 24 hours. It does not send reminders or change statuses automatically. Use `/reviewer_backlog 48` or another threshold when reviewing an older queue.

## First staging pass

After the stack starts, use this order:

```text
/launch_check
/business_context
/set_business_context <фактическое описание услуг>
/channels
/validate_channels
/scan_now
/pending
/approved_queue
/review_queue
```

`/validate_channels` checks each configured source through the current Telegram user session. It stores the time of the check and an error message when a channel cannot be reached. A source validation is treated as fresh for seven days; `/launch_check` requires every active channel to be fresh.

`/scan_now` runs the parser immediately. It is useful after adding a channel or resetting its cursor, and it uses the same lock as the scheduler to avoid duplicate processing.

`/promote_limit_queue` immediately checks whether posts held by daily caps can be moved to reviewer flow. It never bypasses the per-channel daily limit.

## Weekly source review

After at least several days of real reviewer decisions, run:

```text
/source_quality 7
```

The report separates actual lead/comment outcomes from noise and open backlog. It only recommends a manual action; it does not disable channels or change limits itself.

Use the recommendation as a starting point:

- noisy source — raise `min_score` or add `blocked_keywords`;
- high open backlog — check reviewer workload and the channel daily limit;
- strong source — keep it active and consider expanding its daily limit;
- too little data — keep monitoring before changing filters.

## Business context

Set a compact factual profile through:

```text
/set_business_context <описание услуг>
```

Include what can genuinely be offered, relevant Thailand locations, intended audience, and claims that must not be made. The context guides AI relevance scoring and draft wording, but does not enable external auto-posting.

Read or clear it with:

```text
/business_context
/set_business_context -
```

## Error alerts

Operational alerts are sent to `ADMIN_IDS` and rate-limited per component. When a failed component recovers, the bot sends one recovery notification. Runtime state is stored in `app_settings`, so `/health` remains useful after a restart.

## Failed items

When a single source post cannot be processed, it is moved to `processing_failed` instead of disappearing from logs.

```text
/failed_queue
```

Use `Повторить обработку` after checking the source or after fixing the configuration issue.

## Channel cursors

Each channel stores `last_seen_message_id`. This lets the parser process new messages in chronological batches instead of repeatedly sampling the latest messages.

Inspect the cursor:

```text
/channels
```

Reset only when needed:

```text
/reset_channel_cursor <channel_id>
```

After reset, run `/scan_now` to take a fresh bounded slice immediately. Existing posts remain protected by message and text duplicate checks.

## Escalation order

1. Run `/health` and `/launch_check`.
2. Run `/validate_channels` if source validation is missing, stale, or failed.
3. Check `/reviewer_backlog`, `/failed_queue`, and recent parser, reviewer, limit-queue, or source-validation error text.
4. Inspect `docker compose logs --tail=200 bot`.
5. Take a database backup before a code or migration rollback.
6. Keep `OUTBOUND_ENABLED=false` until reviewer-first quality is stable.
