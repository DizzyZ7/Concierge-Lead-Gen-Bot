# Post action audit

`post_actions` is an append-only history of human decisions made on Lead Radar cards.

The audit records:

- lead created;
- comment marked as published;
- content idea saved;
- post marked irrelevant;
- post saved for later;
- post skipped;
- reviewer marked the card as processed;
- reviewer claim created or renewed;
- reviewer claim released manually.

Each record contains the source post ID, previous and new status, the acting Telegram user, optional details, and an UTC timestamp.

Only administrators can inspect the history:

```text
/post_history <post_id>
```

The audit does not send messages, does not change lead qualification, and does not grant a reviewer access to CRM or financial data. It is used for team coordination and operational review.

Core action history requires Alembic revision `0009_post_action_audit`. Reviewer claim events additionally require `0010_reviewer_claims`.
