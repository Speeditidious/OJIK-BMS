"""sqladmin admin panel factory."""
from pathlib import Path

from sqladmin import Admin

from app.admin.auth import DiscordAdminAuth
from app.admin.views import (
    ClientUpdateAnnouncementAdmin,
    CourseAdmin,
    CustomCourseAdmin,
    CustomDifficultyTableAdmin,
    DifficultyTableAdmin,
    FumenAdmin,
    OAuthAccountAdmin,
    ScheduleAdmin,
    UserAdmin,
    UserFavoriteDifficultyTableAdmin,
    UserFumenTagAdmin,
    UserPlayerStatsAdmin,
    UserRankingAdmin,
    UserRatingUpdateDailyAdmin,
    UserScoreAdmin,
    UserTableRatingCheckpointAdmin,
    UserTableRatingUpdateDailyAdmin,
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

    all_admin_views = [
        UserAdmin,
        OAuthAccountAdmin,
        DifficultyTableAdmin,
        FumenAdmin,
        UserScoreAdmin,
        UserPlayerStatsAdmin,
        ClientUpdateAnnouncementAdmin,
        CourseAdmin,
        UserFavoriteDifficultyTableAdmin,
        UserFumenTagAdmin,
        CustomDifficultyTableAdmin,
        CustomCourseAdmin,
        ScheduleAdmin,
        UserRankingAdmin,
        UserTableRatingCheckpointAdmin,
        UserTableRatingUpdateDailyAdmin,
        UserRatingUpdateDailyAdmin,
    ]

    for view in all_admin_views:
        admin.add_view(view)

    return admin
