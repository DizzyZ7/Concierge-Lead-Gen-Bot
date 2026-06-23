from __future__ import annotations

from aiogram import Router

from bot.handlers import channels, dashboard, failed, launch_check, leads, posts, reports, results, review_extras, reviewer_backlog_menu, saved, settings as settings_handlers, source_control, source_view, templates


def build_router() -> Router:
    router = Router(name="all_handlers")
    router.include_router(dashboard.router)
    router.include_router(launch_check.router)
    router.include_router(channels.router)
    router.include_router(source_control.router)
    router.include_router(posts.router)
    router.include_router(review_extras.router)
    router.include_router(reviewer_backlog_menu.router)
    router.include_router(source_view.router)
    router.include_router(saved.router)
    router.include_router(failed.router)
    router.include_router(results.router)
    router.include_router(reports.router)
    router.include_router(leads.router)
    router.include_router(templates.router)
    router.include_router(settings_handlers.router)
    return router
