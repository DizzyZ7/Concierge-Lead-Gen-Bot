# Reviewer card claims

Reviewer claims prevent two people from closing the same live card at once.

## How it works

1. A reviewer receives a card in the reviewer queue.
2. He presses **«Взять в работу»**.
3. The card stores the reviewer identity and becomes locked for 45 minutes.
4. The card text shows who owns it and the UTC expiration time.
5. Other reviewers can still read the source and draft, but cannot save, skip, mark done, create a lead, mark a comment, mark an idea, mark irrelevant, or edit the draft while the claim is active.
6. The owner may press **«Освободить»** to return it to the queue. An administrator can also release any active claim.
7. Pressing **«Взять в работу»** again by the current owner renews the 45-minute window.
8. After expiry, any authorized reviewer can take the card again.

A claim is automatically cleared when a protected action closes the card with a status other than `sent_to_reviewer`.

## Audit

Claims, renewals, releases, and final reviewer actions are written to `post_actions`.

Admins can inspect a card history:

```text
/post_history <post_id>
```

## Scope

Claims apply only to cards that have already reached `sent_to_reviewer`. They do not block parser ingestion, pending review, source validation, CRM administration, or source monitoring.

The feature requires Alembic revision `0010_reviewer_claims`.
