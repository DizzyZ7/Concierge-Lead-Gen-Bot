from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TargetChannel(Base):
    __tablename__ = "target_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    channel_title: Mapped[str | None] = mapped_column(Text)
    geo: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    daily_draft_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    review_delay_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    review_delay_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    min_score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    allowed_intents: Mapped[str | None] = mapped_column(Text)
    blocked_keywords: Mapped[str | None] = mapped_column(Text)
    last_seen_message_id: Mapped[int | None] = mapped_column(BigInteger)
    last_validation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    posts: Mapped[list["ParsedPost"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class ParsedPost(Base):
    __tablename__ = "parsed_posts"
    __table_args__ = (UniqueConstraint("channel_id", "tg_message_id", name="uq_parsed_post_channel_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("target_channels.id", ondelete="CASCADE"), nullable=False)
    tg_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    post_text: Mapped[str | None] = mapped_column(Text)
    post_url: Mapped[str | None] = mapped_column(Text)
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    relevance_score: Mapped[float | None] = mapped_column()
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    content_summary: Mapped[str | None] = mapped_column(Text)
    suggested_angle: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    channel: Mapped[TargetChannel] = relationship(back_populates="posts")
    draft: Mapped[Optional["ReviewDraft"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    leads: Mapped[list["Lead"]] = relationship(back_populates="source_post")
    actions: Mapped[list["PostAction"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class ReviewDraft(Base):
    __tablename__ = "review_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("parsed_posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    draft_source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_to_reviewer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewer_message_id: Mapped[int | None] = mapped_column(BigInteger)
    marked_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    claimed_by_username: Mapped[str | None] = mapped_column(String(128))
    claimed_by_name: Mapped[str | None] = mapped_column(String(256))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    post: Mapped[ParsedPost] = relationship(back_populates="draft")


class PostAction(Base):
    __tablename__ = "post_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("parsed_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(Text)
    new_status: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    actor_username: Mapped[str | None] = mapped_column(String(128))
    actor_name: Mapped[str | None] = mapped_column(String(256))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    post: Mapped[ParsedPost] = relationship(back_populates="actions")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("source_post_id", name="uq_leads_source_post_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger)
    tg_username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    source_post_id: Mapped[int | None] = mapped_column(ForeignKey("parsed_posts.id", ondelete="SET NULL"))
    geo: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="new")
    deal_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    source_post: Mapped[Optional[ParsedPost]] = relationship(back_populates="leads")


class DraftTemplate(Base):
    __tablename__ = "draft_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    geo: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_stats_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    posts_parsed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    drafts_sent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviewer_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deals_closed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    revenue: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    ai_drafts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    template_drafts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ai_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
