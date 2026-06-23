# Thailand Lead Radar — Operations

## Daily checks

```text
/health
/daily_report
/channel_stats
/queue_stats
/failed_queue
```

`/health` must show live parser and reviewer heartbeats. A stale heartbeat or a recent error requires review before adding more sources.

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

After reset, the next parser run will take a fresh bounded slice. Existing posts remain protected by message and text duplicate checks.

## Escalation order

1. Run `/health`.
2. Check `/failed_queue` and recent parser/reviewer error text.
3. Inspect `docker compose logs --tail=200 bot`.
4. Take a database backup before a code or migration rollback.
5. Keep `OUTBOUND_ENABLED=false` until reviewer-first quality is stable.
