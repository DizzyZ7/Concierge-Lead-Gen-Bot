# Reviewer card claims

Reviewer claims prevent two people from closing the same live card at once.

## How it works

1. A reviewer receives a card in the reviewer queue.
2. Before editing or recording any outcome, he presses **«Взять в работу»**.
3. A live `sent_to_reviewer` card cannot be saved, skipped, edited, marked done, converted to a lead, marked as commented, marked as an idea, or marked irrelevant without an active claim owned by that reviewer.
4. The card stores the reviewer identity and becomes locked for 45 minutes.
5. The card text shows who owns it and the UTC expiration time.
6. Other reviewers can still read the source and draft, but cannot change the card while the claim is active.
7. The owner may press **«Освободить»** to return it to the queue. An administrator can also release or close any active claim.
8. Pressing **«Взять в работу»** again by the current owner renews the 45-minute window.
9. After expiry, the previous owner must claim the card again before acting, and any authorized reviewer may take it.

The claim check is fail-closed: if ownership cannot be verified because of a database or runtime error, the requested change is cancelled instead of bypassing the lock.

A claim is automatically cleared when a protected action closes the card with a status other than `sent_to_reviewer`.

## Audit

Claims, renewals, releases, and final reviewer actions are written to `post_actions`.

Admins can inspect a card history:

```text
/post_history <post_id>
```

## Scope

Claims apply only to cards that have already reached `sent_to_reviewer`. They do not block parser ingestion, pending review, source validation, CRM administration, or source monitoring. Administrators retain an explicit operational override for live cards.

The feature requires Alembic revision `0010_reviewer_claims`.
