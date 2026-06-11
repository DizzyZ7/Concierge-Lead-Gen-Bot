# Automation Roadmap

The project is built as reviewer-first today, but the architecture keeps a clean path for future automation.

## Current mode: assisted reviewer flow

```text
source item -> relevance scoring -> draft generation -> reviewer card -> human decision
```

The system reads configured sources, prepares a draft, and sends it to a human reviewer. It does not publish anything automatically.

## Automation levels

### Level 0: manual intake

- Owner adds an item with `/add_item`.
- Bot prepares a draft after approval.
- Reviewer manually sends or discards the message.

### Level 1: assisted discovery

- Parser reads configured sources.
- Claude scores relevance.
- Relevant items are routed to reviewer.
- Reviewer edits, cancels, approves, or marks done.

### Level 2: supervised automation

Future extension.

- Bot can route selected low-risk drafts automatically to a supervised queue.
- Owner can pause everything instantly.
- All actions are logged.
- Limits, time windows, duplicate checks and audit records are mandatory.

### Level 3: authorized destination automation

Future extension for owned or explicitly authorized destinations only.

- Direct publishing is behind feature flags.
- Each destination must be explicitly allowlisted.
- Per-destination and global daily limits are required.
- Human override and rollback controls stay available.

## Required gates before enabling automation

Before any automated outbound action exists, implement these gates:

1. `AUTOMATION_LEVEL` environment flag.
2. `OUTBOUND_ENABLED=false` by default.
3. Destination allowlist in DB.
4. Global pause switch.
5. Daily and hourly limits.
6. Duplicate text prevention.
7. Audit log table.
8. Reviewer override queue.
9. Error budget and alerting.
10. Canary mode for one destination first.

## Suggested DB additions later

```text
automation_rules
outbound_destinations
audit_log
rate_limit_counters
message_variants
```

## Suggested services later

```text
services/outbound_router.py
services/publishers/base.py
services/publishers/telegram_owned.py
services/rate_limiter.py
services/audit.py
```

## Safe default

The default production setting must remain:

```env
PARSER_ENABLED=true
REVIEWER_MODE=true
OUTBOUND_ENABLED=false
AUTOMATION_LEVEL=assisted
```

This gives the owner lead discovery and draft preparation without uncontrolled outbound posting.
