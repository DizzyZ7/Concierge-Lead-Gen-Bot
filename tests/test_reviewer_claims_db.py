from __future__ import annotations

import asyncio
import os
import unittest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.models import ParsedPost, ReviewDraft, TargetChannel
from db.session import create_engine, create_session_factory
from services.post_audit import ActionActor
from services.reviewer_claims import claim_reviewer_card, get_claim_access


def test_database_url() -> str | None:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    if os.getenv("CI", "").lower() == "true":
        return os.getenv("DATABASE_URL")
    return None


class ReviewerClaimDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url = test_database_url()
        if not database_url:
            self.skipTest("TEST_DATABASE_URL is not configured outside CI")

        self.engine = create_engine(database_url)
        self.session_factory = create_session_factory(self.engine)
        self.channel_id: int | None = None
        self.post_id: int | None = None

        try:
            async with self.session_factory() as session:
                suffix = uuid4().hex
                channel = TargetChannel(
                    channel_username=f"@claim_test_{suffix}",
                    geo="thailand",
                    category="test",
                )
                session.add(channel)
                await session.flush()

                post = ParsedPost(
                    channel_id=channel.id,
                    tg_message_id=int(suffix[:12], 16),
                    post_text="claim concurrency test",
                    relevance_score=0.9,
                    intent="realty",
                    status="sent_to_reviewer",
                )
                session.add(post)
                await session.flush()

                session.add(
                    ReviewDraft(
                        post_id=post.id,
                        draft_text="test draft",
                        draft_source="test",
                    )
                )
                await session.commit()
                self.channel_id = channel.id
                self.post_id = post.id
        except SQLAlchemyError as error:
            await self.engine.dispose()
            self.skipTest(f"Test PostgreSQL is unavailable: {error.__class__.__name__}")

    async def asyncTearDown(self) -> None:
        if not hasattr(self, "engine"):
            return
        if self.channel_id is not None:
            async with self.session_factory() as session:
                channel = await session.get(TargetChannel, self.channel_id)
                if channel is not None:
                    await session.delete(channel)
                    await session.commit()
        await self.engine.dispose()

    async def claim_as(self, user_id: int):
        async with self.session_factory() as session:
            return await claim_reviewer_card(
                session,
                post_id=self.post_id,
                actor=ActionActor(user_id=user_id, username=f"reviewer_{user_id}", name=f"Reviewer {user_id}"),
            )

    async def test_live_card_requires_claim_before_action(self) -> None:
        async with self.session_factory() as session:
            access = await get_claim_access(
                session,
                post_id=self.post_id,
                actor_user_id=101,
                is_admin=False,
            )
        self.assertEqual(access.code, "claim_required")

    async def test_only_one_concurrent_reviewer_wins_claim(self) -> None:
        first, second = await asyncio.gather(self.claim_as(101), self.claim_as(202))
        self.assertEqual(sorted([first.code, second.code]), ["claimed", "taken"])

        winner = 101 if first.code == "claimed" else 202
        loser = 202 if winner == 101 else 101
        async with self.session_factory() as session:
            draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == self.post_id))
            self.assertIsNotNone(draft)
            self.assertEqual(draft.claimed_by_user_id, winner)

            winner_access = await get_claim_access(
                session,
                post_id=self.post_id,
                actor_user_id=winner,
                is_admin=False,
            )
            loser_access = await get_claim_access(
                session,
                post_id=self.post_id,
                actor_user_id=loser,
                is_admin=False,
            )

        self.assertEqual(winner_access.code, "allowed")
        self.assertEqual(loser_access.code, "taken")


if __name__ == "__main__":
    unittest.main()
