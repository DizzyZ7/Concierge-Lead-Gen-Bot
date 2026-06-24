from __future__ import annotations

from aiogram import Router

from bot.handlers import channels, dashboard, failed, launch_check, leads, posts, reports, results, review_extras, reviewer_backlog_menu, saved, settings as settings_handlers, source_control, source_view, templates
from bot.middlewares.admin_only import AdminOnlyMiddleware
from core.config import Settings


def protect_admin_router(router: Router, middleware: AdminOnlyMiddleware) -> None:
    router.message.middleware(middleware)
    router.callback_query.middleware(middleware)


def build_router(settings: Settings) -> Router:
    admin_middleware = AdminOnlyMiddleware(settings)
    for admin_router in (
        launch_check.router,
        channels.router,
        source_control.router,
        failed.router,
        leads.router,
        templates.router,
        settings_handlers.router,
    ):
        protect_admin_router(admin_router, admin_middleware)

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
