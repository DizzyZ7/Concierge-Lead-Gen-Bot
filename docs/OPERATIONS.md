# Thailand Lead Radar — Operations

## Daily checks

```text
/health
/daily_report
/channel_stats
/queue_stats
/failed_queue
/followups
```

`/health` must show live parser, reviewer, and daily-limit-queue heartbeats. A stale heartbeat or a recent error requires review before adding more sources.

## First staging pass

After the stack starts, use this order:

```text
/launch_check
/business_context
/set_business_context <фактическое описание услуг>
/channels
/scan_now
/pending
/approved_queue
/review_queue
```

`/scan_now` runs the parser immediately. It is useful after adding a channel or resetting its cursor, and it uses the same lock as the scheduler to avoid duplicate processing.

`/promote_limit_queue` immediately checks whether posts held by daily caps can be moved to reviewer flow. It never bypasses the per-channel daily limit.

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

Operational alerts are sent to `ADMIN_IDS` and rate-limited per component. The bot stores the last success time, details, and error in `app_settings`, so `/health` remains useful after a restart.

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
2. Check `/failed_queue` and recent parser, reviewer, or limit-queue error text.
3. Inspect `docker compose logs --tail=200 bot`.
4. Take a database backup before a code or migration rollback.
5. Keep `OUTBOUND_ENABLED=false` until reviewer-first quality is stable.
