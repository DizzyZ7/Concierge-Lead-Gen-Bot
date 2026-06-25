from __future__ import annotations

import asyncio
import argparse
import sys
from asyncio import Lock

from bot.handlers.launch_check import render_launch_check
from bot.main import create_bot, create_dispatcher
from core.config import Settings, get_settings
from core.reviewer_access import parse_reviewer_user_ids, reviewer_user_ids
from core.scheduler import create_scheduler
from db.migration_guard import ensure_schema_current
from db.session import create_engine, create_session_factory
from services.ai import AIService
from services.limit_queue_promoter import LimitQueuePromoter
from services.runtime_ops import RuntimeOps

LAUNCH_READY_PREFIX = "✅ Можно запускать"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a no-polling launch preflight check.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when launch-check reports unresolved launch blockers.",
    )
    return parser.parse_args(argv)


def launch_check_ready(text: str) -> bool:
    return bool(text.splitlines()) and text.splitlines()[0].strip() == LAUNCH_READY_PREFIX


def config_blockers(settings: Settings) -> list[str]:
    blockers: list[str] = []
    if settings.outbound_enabled:
        blockers.append("OUTBOUND_ENABLED must stay false for reviewer-first launch.")
    if settings.auto_approve:
        blockers.append("AUTO_APPROVE must stay false for manual reviewer launch.")
    if not settings.reviewer_mode:
        blockers.append("REVIEWER_MODE must stay true for reviewer-first launch.")
    try:
        configured_reviewers = reviewer_user_ids(settings)
    except ValueError as error:
        blockers.append(str(error))
        configured_reviewers = set()
    if any(chat_id < 0 for chat_id in settings.reviewer_chat_ids) and not configured_reviewers:
        blockers.append("Group reviewer delivery requires explicit positive REVIEWER_USER_IDS.")
    if settings.parser_enabled and not settings.parser_ready:
        blockers.append("PARSER_ENABLED=true requires TG_API_ID and TG_API_HASH.")
    return blockers


def has_explicit_reviewer_users(value: str | None) -> bool:
    return bool(parse_reviewer_user_ids(value))


async def run_preflight(strict: bool = False) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    bot = None
    try:
        revision = await ensure_schema_current(session_factory)
        bot = create_bot(settings)
        ai_service = AIService(settings)
        runtime_ops = RuntimeOps(bot=bot, session_factory=session_factory, settings=settings)
        workflow_lock = Lock()
        dispatcher = create_dispatcher(
            settings=settings,
            session_factory=session_factory,
            ai_service=ai_service,
            runtime_ops=runtime_ops,
            source_workflow_lock=workflow_lock,
        )
        limit_queue_promoter = LimitQueuePromoter(
            session_factory=session_factory,
            ai_service=ai_service,
            settings=settings,
            runtime_ops=runtime_ops,
        )
        scheduler = create_scheduler(settings)
        scheduler.add_job(
            lambda: None,
            "interval",
            minutes=5,
            id="preflight_noop",
            max_instances=1,
            coalesce=True,
        )
        blockers = config_blockers(settings)
        launch_check = await render_launch_check(session_factory, settings)
        print(f"Schema revision: {revision}")
        print(f"Dispatcher routers: {len(dispatcher.sub_routers)}")
        print(f"Scheduler jobs: {len(scheduler.get_jobs())}")
        print(f"Limit queue promoter: {limit_queue_promoter.__class__.__name__}")
        print(f"Config blockers: {len(blockers)}")
        print("")
        if blockers:
            print("Config blockers:")
            for blocker in blockers:
                print(f"- {blocker}")
            print("")
        print(launch_check)
        if strict and (blockers or not launch_check_ready(launch_check)):
            print("")
            print("Strict preflight failed: unresolved launch blockers remain.")
            return 1
        return 0
    finally:
        if bot is not None:
            await bot.session.close()
        await engine.dispose()


async def main() -> None:
    args = parse_args()
    raise SystemExit(await run_preflight(strict=args.strict))


if __name__ == "__main__":
    asyncio.run(main())
