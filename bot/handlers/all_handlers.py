from __future__ import annotations

from aiogram import Router

from bot.handlers import (
    channels,
    dashboard,
    failed,
    launch_check,
    leads,
    post_action_callbacks,
    post_history,
    posts,
    report_access,
    reports,
    results,
    review_extras,
    reviewer_backlog_menu,
    reviewer_claims,
    reviewer_draft_edit,
    reviewer_queue,
    saved,
    settings as settings_handlers,
    source_control,
    source_view,
    templates,
)
from bot.middlewares.admin_only import AdminOnlyMiddleware
from bot.middlewares.reviewer_claim_guard import ReviewerClaimGuardMiddleware
from core.config import Settings


def protect_admin_router(router: Router, middleware: AdminOnlyMiddleware) -> None:
    router.message.middleware(middleware)
    router.callback_query.middleware(middleware)


def protect_claim_router(router: Router, middleware: ReviewerClaimGuardMiddleware) -> None:
    router.message.middleware(middleware)
    router.callback_query.middleware(middleware)


def build_router(settings: Settings | None = None) -> Router:
    # Production always passes the validated Settings object from create_dispatcher.
    # The fallback keeps import-only smoke checks independent of real environment variables.
    app_settings = settings or Settings.model_construct(
        admin_ids_raw="",
        reviewer_chat_ids_raw=None,
    )
    admin_middleware = AdminOnlyMiddleware(app_settings)
    for admin_router in (
        launch_check.router,
        channels.router,
        source_control.router,
        failed.router,
        leads.router,
        post_history.router,
        templates.router,
        settings_handlers.router,
    ):
        protect_admin_router(admin_router, admin_middleware)

    claim_guard = ReviewerClaimGuardMiddleware()
    for claim_guarded_router in (
        reviewer_draft_edit.router,
        posts.router,
        post_action_callbacks.router,
        review_extras.router,
        saved.router,
        results.router,
    ):
        protect_claim_router(claim_guarded_router, claim_guard)

    router = Router(name="all_handlers")
    router.include_router(dashboard.router)
    router.include_router(launch_check.router)
    router.include_router(channels.router)
    router.include_router(source_control.router)
    router.include_router(reviewer_claims.router)
    router.include_router(post_action_callbacks.router)
    router.include_router(reviewer_queue.router)
    router.include_router(reviewer_draft_edit.router)
    router.include_router(posts.router)
    router.include_router(review_extras.router)
    router.include_router(reviewer_backlog_menu.router)
    router.include_router(source_view.router)
    router.include_router(saved.router)
    router.include_router(failed.router)
    router.include_router(results.router)
    router.include_router(report_access.router)
    router.include_router(reports.router)
    router.include_router(leads.router)
    router.include_router(post_history.router)
    router.include_router(templates.router)
    router.include_router(settings_handlers.router)
    return router
