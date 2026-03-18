"""sqladmin admin panel factory."""
from pathlib import Path

from sqladmin import Admin

from app.admin.auth import DiscordAdminAuth
from app.admin.views import (
    ChatbotConversationAdmin,
    ChatbotDocumentAdmin,
    ChatbotUsageLimitAdmin,
    CourseAdmin,
    CourseScoreHistoryAdmin,
    CustomCourseAdmin,
    CustomTableAdmin,
    DifficultyTableAdmin,
    OAuthAccountAdmin,
    ScheduleAdmin,
    SongAdmin,
    ScoreHistoryAdmin,
    UserAdmin,
    UserCourseScoreAdmin,
    UserPlayerStatsAdmin,
    UserScoreAdmin,
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
    from app.core.config import settings

    auth_backend = DiscordAdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app=app,
        engine=engine,
        title="OJIK BMS Admin",
        authentication_backend=auth_backend,
        base_url="/admin",
        templates_dir=_TEMPLATES_DIR,
    )

    admin.add_view(UserAdmin)
    admin.add_view(OAuthAccountAdmin)
    admin.add_view(DifficultyTableAdmin)
    admin.add_view(SongAdmin)
    admin.add_view(UserScoreAdmin)
    admin.add_view(ScoreHistoryAdmin)
    admin.add_view(UserPlayerStatsAdmin)
    admin.add_view(CourseAdmin)
    admin.add_view(UserCourseScoreAdmin)
    admin.add_view(CourseScoreHistoryAdmin)
    admin.add_view(CustomTableAdmin)
    admin.add_view(CustomCourseAdmin)
    admin.add_view(ScheduleAdmin)
    admin.add_view(ChatbotDocumentAdmin)
    admin.add_view(ChatbotConversationAdmin)
    admin.add_view(ChatbotUsageLimitAdmin)

    return admin
