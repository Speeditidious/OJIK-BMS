"""sqladmin admin panel factory."""
from pathlib import Path

from sqladmin import Admin

from app.admin.auth import DiscordAdminAuth
from app.admin.views import (
    AdminActionLogAdmin,
    AdminActionLogLineAdmin,
    AnnouncementAdmin,
    AnnouncementTagAdmin,
    AnnouncementTemplateAdmin,
    ClientUpdateAnnouncementAdmin,
    CourseAdmin,
    CustomCourseAdmin,
    CustomDifficultyTableAdmin,
    DifficultyTableAdmin,
    FumenAdmin,
    FumenPlayPopularityAdmin,
    FumenPopularityDirtyAdmin,
    FumenPopularityWindowAdmin,
    FumenTableEntryAdmin,
    IssueAdmin,
    IssueCommentAdmin,
    IssueTagAdmin,
    NotificationAdmin,
    NotificationReadAdmin,
    NotificationUserStateAdmin,
    OAuthAccountAdmin,
    ScheduleAdmin,
    TableImportLogAdmin,
    TableSourceAliasAdmin,
    UserAdmin,
    UserDayNoteAdmin,
    UserFavoriteDifficultyTableAdmin,
    UserFumenTagAdmin,
    UserPlayerStatsAdmin,
    UserRankingAdmin,
    UserRatingUpdateDailyAdmin,
    UserScoreAdmin,
    UserTableRatingCheckpointAdmin,
    UserTableRatingUpdateDailyAdmin,
    WeeklyAdmin,
    WeeklyFumenAdmin,
)

# Templates directory relative to this package's api/ root.
# In Docker (./api:/app), this resolves to /app/templates.
_TEMPLATES_DIR = str(Path(__file__).parent.parent.parent / "templates")


def create_admin(app, engine) -> Admin:
    """Create and mount the sqladmin Admin instance on *app*.

    Args:
        app: The FastAPI application instance.
        engine: SQLAlchemy (async) engine.

    Returns:
        The configured :class:`sqladmin.Admin` instance.
    """
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, RedirectResponse

    from app.core.config import settings

    async def add_table_by_url(request: Request):
        if not request.session.get("admin_user_id"):
            return RedirectResponse(url="/auth/discord/login?state=admin_panel", status_code=302)
        if request.method == "GET":
            return HTMLResponse(
                """
                <!doctype html>
                <html>
                  <head><title>Add Difficulty Table by URL</title></head>
                  <body style="font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto;">
                    <h1>Add Difficulty Table by URL</h1>
                    <form method="post">
                      <input
                        name="url"
                        type="url"
                        required
                        placeholder="https://example.com/table.html"
                        style="box-sizing: border-box; width: 100%; padding: 10px; font-size: 16px;"
                      >
                      <button type="submit" style="margin-top: 12px; padding: 8px 14px;">
                        Queue Sync
                      </button>
                    </form>
                  </body>
                </html>
                """
            )

        form = await request.form()
        url = str(form.get("url") or "").strip()
        if not url:
            return HTMLResponse("URL is required.", status_code=400)

        import uuid

        from app.services.admin_action_log import create_log, mark_task_id
        from app.services.table_sync import canonicalize_table_url
        from app.tasks.table_updater import update_difficulty_table_by_url

        try:
            triggered_by = uuid.UUID(str(request.session.get("admin_user_id")))
        except (TypeError, ValueError):
            triggered_by = None

        canonical_url = canonicalize_table_url(url)
        log_id = await create_log(
            action_name="add_table_by_url",
            target_kind="difficulty_table_url",
            target_id=canonical_url,
            target_label=canonical_url,
            triggered_by=triggered_by,
            payload={"url": canonical_url},
        )
        task_result = update_difficulty_table_by_url.delay(canonical_url, log_id=str(log_id))
        if getattr(task_result, "id", None):
            await mark_task_id(log_id, task_result.id)
        return RedirectResponse(
            request.url_for("admin:details", identity=AdminActionLogAdmin.identity, pk=str(log_id)),
            status_code=302,
        )

    app.add_route("/admin/difficulty-tables/add-by-url", add_table_by_url, methods=["GET", "POST"])

    auth_backend = DiscordAdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app=app,
        engine=engine,
        title="OJIK BMS Admin",
        authentication_backend=auth_backend,
        base_url="/admin",
        templates_dir=_TEMPLATES_DIR,
    )

    all_admin_views = [
        UserAdmin,
        OAuthAccountAdmin,
        AdminActionLogAdmin,
        AdminActionLogLineAdmin,
        AnnouncementTagAdmin,
        AnnouncementTemplateAdmin,
        AnnouncementAdmin,
        IssueTagAdmin,
        IssueAdmin,
        IssueCommentAdmin,
        NotificationAdmin,
        NotificationReadAdmin,
        NotificationUserStateAdmin,
        DifficultyTableAdmin,
        FumenAdmin,
        FumenPlayPopularityAdmin,
        FumenPopularityDirtyAdmin,
        FumenPopularityWindowAdmin,
        FumenTableEntryAdmin,
        UserScoreAdmin,
        UserPlayerStatsAdmin,
        ClientUpdateAnnouncementAdmin,
        CourseAdmin,
        UserFavoriteDifficultyTableAdmin,
        TableImportLogAdmin,
        TableSourceAliasAdmin,
        UserFumenTagAdmin,
        CustomDifficultyTableAdmin,
        CustomCourseAdmin,
        ScheduleAdmin,
        UserRankingAdmin,
        UserTableRatingCheckpointAdmin,
        UserTableRatingUpdateDailyAdmin,
        UserRatingUpdateDailyAdmin,
        UserDayNoteAdmin,
        WeeklyAdmin,
        WeeklyFumenAdmin,
    ]

    for view in all_admin_views:
        admin.add_view(view)

    return admin
