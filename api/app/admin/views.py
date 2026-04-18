"""sqladmin ModelView definitions for all OJIK BMS models.

Data integrity rules applied here mirror the constraints in the API:
- Best-score tables (UserScore): no create, no delete.
- User: no delete (prevents accidental cascade wipeout).
"""
import uuid

from sqladmin import ModelView, action
from sqlalchemy import delete, null, update
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.models.course import Course
from app.models.difficulty_table import (
    CustomCourse,
    CustomDifficultyTable,
    DifficultyTable,
    UserFavoriteDifficultyTable,
)
from app.models.fumen import Fumen, UserFumenTag
from app.models.ranking import UserRanking
from app.models.schedule import Schedule
from app.models.score import UserPlayerStats, UserScore
from app.models.user import OAuthAccount, User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.username, User.is_active, User.is_admin, User.created_at]
    column_searchable_list = [User.username]
    column_sortable_list = [User.username, User.created_at, User.is_active, User.is_admin]
    can_delete = False  # Deleting a user triggers cascades across all score tables

    @action(
        name="reset_play_data",
        label="플레이 데이터 초기화",
        confirmation_message=(
            "선택한 유저의 모든 플레이 데이터(user_scores, user_player_stats, first_synced_at)가 삭제됩니다. "
            "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def reset_play_data(self, request: Request) -> RedirectResponse:
        """Delete all play data for selected users (dev/admin use only)."""
        from app.core.database import AsyncSessionLocal

        pks = request.query_params.get("pks", "")
        user_ids = [uid.strip() for uid in pks.split(",") if uid.strip()]

        if user_ids:
            async with AsyncSessionLocal() as db:
                for uid_str in user_ids:
                    try:
                        uid = uuid.UUID(uid_str)
                    except ValueError:
                        continue
                    await db.execute(delete(UserScore).where(UserScore.user_id == uid))
                    await db.execute(delete(UserPlayerStats).where(UserPlayerStats.user_id == uid))
                    await db.execute(update(User).where(User.id == uid).values(first_synced_at=null()))
                await db.commit()

        return RedirectResponse(request.url_for("admin:list", identity="user"), status_code=302)

    @action(
        name="delete_user_and_data",
        label="계정 및 모든 데이터 삭제",
        confirmation_message=(
            "선택한 유저의 계정과 모든 관련 데이터가 영구 삭제됩니다. "
            "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def delete_user_and_data(self, request: Request) -> RedirectResponse:
        """Permanently delete user account and all associated data (admin only)."""
        from app.core.database import AsyncSessionLocal
        from app.routers.users import _delete_all_user_data

        pks = request.query_params.get("pks", "")
        user_ids = [uid.strip() for uid in pks.split(",") if uid.strip()]

        if user_ids:
            async with AsyncSessionLocal() as db:
                for uid_str in user_ids:
                    try:
                        uid = uuid.UUID(uid_str)
                    except ValueError:
                        continue
                    await _delete_all_user_data(db, uid)

        return RedirectResponse(request.url_for("admin:list", identity="user"), status_code=302)


class OAuthAccountAdmin(ModelView, model=OAuthAccount):
    name = "OAuth Account"
    name_plural = "OAuth Accounts"
    icon = "fa-brands fa-discord"
    column_list = [
        OAuthAccount.user_id,
        OAuthAccount.provider,
        OAuthAccount.provider_account_id,
        OAuthAccount.provider_username,
    ]
    column_searchable_list = [OAuthAccount.provider_username, OAuthAccount.provider_account_id]
    column_sortable_list = [OAuthAccount.provider, OAuthAccount.provider_username]


class DifficultyTableAdmin(ModelView, model=DifficultyTable):
    name = "Difficulty Table"
    name_plural = "Difficulty Tables"
    icon = "fa-solid fa-table"
    column_list = [
        DifficultyTable.id,
        DifficultyTable.name,
        DifficultyTable.symbol,
        DifficultyTable.slug,
        DifficultyTable.is_default,
        DifficultyTable.updated_at,
    ]
    column_searchable_list = [DifficultyTable.name, DifficultyTable.slug]
    column_sortable_list = [DifficultyTable.id, DifficultyTable.name, DifficultyTable.updated_at]

    @action(
        name="sync_selected_tables",
        label="선택된 테이블 최신화",
        confirmation_message="선택된 난이도표들을 최신화합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def sync_selected_tables(self, request: Request) -> RedirectResponse:
        """Queue Celery sync tasks for each selected difficulty table."""
        from app.tasks.table_updater import update_difficulty_table

        pks = request.query_params.get("pks", "")
        for pk in [p.strip() for p in pks.split(",") if p.strip()]:
            update_difficulty_table.delay(pk)

        return RedirectResponse(
            request.url_for("admin:list", identity="difficultytable"), status_code=302
        )

    @action(
        name="sync_all_tables",
        label="전체 테이블 일괄 최신화",
        confirmation_message="모든 난이도표를 최신화합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def sync_all_tables(self, request: Request) -> RedirectResponse:
        """Queue a Celery task to sync all difficulty tables."""
        from app.tasks.table_updater import update_all_difficulty_tables

        update_all_difficulty_tables.delay()

        return RedirectResponse(
            request.url_for("admin:list", identity="difficultytable"), status_code=302
        )

    @action(
        name="recalculate_rankings",
        label="랭킹 재계산",
        confirmation_message="선택된 난이도표의 전체 유저 랭킹을 재계산합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def recalculate_rankings(self, request: Request) -> RedirectResponse:
        """Queue ranking recalculation for selected difficulty tables."""
        from app.services.ranking_config import get_ranking_config
        from app.tasks.ranking_calculator import recalculate_all_rankings

        pks = request.query_params.get("pks", "")
        ids = [p.strip() for p in pks.split(",") if p.strip()]

        try:
            config = get_ranking_config()
        except RuntimeError:
            config = None

        if config is None:
            recalculate_all_rankings.delay()
        else:
            id_to_slug = {str(t.table_id): t.slug for t in config.tables}
            for pk in ids:
                slug = id_to_slug.get(pk)
                if slug:
                    recalculate_all_rankings.delay(slug)

        return RedirectResponse(
            request.url_for("admin:list", identity="difficultytable"), status_code=302
        )


class FumenAdmin(ModelView, model=Fumen):
    name = "Fumen"
    name_plural = "Fumens"
    icon = "fa-solid fa-music"
    column_list = [Fumen.title, Fumen.artist, Fumen.md5, Fumen.sha256, Fumen.bpm_max]
    column_searchable_list = [Fumen.title, Fumen.artist, Fumen.md5, Fumen.sha256]
    column_sortable_list = [Fumen.title, Fumen.artist, Fumen.bpm_max, Fumen.created_at]


class UserScoreAdmin(ModelView, model=UserScore):
    name = "User Score"
    name_plural = "User Scores"
    icon = "fa-solid fa-star"
    column_list = [
        UserScore.id,
        UserScore.user_id,
        UserScore.scorehash,
        UserScore.fumen_sha256,
        UserScore.fumen_md5,
        UserScore.fumen_hash_others,
        UserScore.client_type,
        UserScore.clear_type,
        UserScore.rate,
        UserScore.play_count,
        UserScore.recorded_at,
        UserScore.synced_at,
    ]
    column_searchable_list = [UserScore.fumen_sha256, UserScore.fumen_md5, UserScore.scorehash]
    column_sortable_list = [UserScore.recorded_at, UserScore.synced_at, UserScore.rate]
    can_create = False  # Scores must enter through the sync pipeline
    can_delete = False  # Blind deletion would break score continuity


class UserPlayerStatsAdmin(ModelView, model=UserPlayerStats):
    name = "Player Stats"
    name_plural = "Player Stats"
    icon = "fa-solid fa-chart-bar"
    column_list = [
        UserPlayerStats.id,
        UserPlayerStats.user_id,
        UserPlayerStats.client_type,
        UserPlayerStats.playcount,
        UserPlayerStats.clearcount,
        UserPlayerStats.playtime,
        UserPlayerStats.synced_at,
    ]
    column_sortable_list = [UserPlayerStats.synced_at, UserPlayerStats.playcount]
    # judgments (JSONB) intentionally omitted from column_list


class CourseAdmin(ModelView, model=Course):
    name = "Course"
    name_plural = "Courses"
    icon = "fa-solid fa-list-ol"
    column_list = [Course.id, Course.name, Course.source_table_id, Course.is_active, Course.dan_title, Course.synced_at]
    column_searchable_list = [Course.name, Course.dan_title]
    column_sortable_list = [Course.synced_at, Course.is_active, Course.name]



class UserFavoriteDifficultyTableAdmin(ModelView, model=UserFavoriteDifficultyTable):
    name = "Favorite Table"
    name_plural = "Favorite Tables"
    icon = "fa-solid fa-star"
    column_list = [
        UserFavoriteDifficultyTable.user_id,
        UserFavoriteDifficultyTable.table_id,
        UserFavoriteDifficultyTable.display_order,
    ]
    column_sortable_list = [UserFavoriteDifficultyTable.display_order]


class UserFumenTagAdmin(ModelView, model=UserFumenTag):
    name = "Fumen Tag"
    name_plural = "Fumen Tags"
    icon = "fa-solid fa-tag"
    column_list = [
        UserFumenTag.id,
        UserFumenTag.user_id,
        UserFumenTag.fumen_sha256,
        UserFumenTag.fumen_md5,
        UserFumenTag.tag,
    ]
    column_searchable_list = [UserFumenTag.tag, UserFumenTag.fumen_sha256, UserFumenTag.fumen_md5]
    column_sortable_list = [UserFumenTag.tag]


class CustomDifficultyTableAdmin(ModelView, model=CustomDifficultyTable):
    name = "Custom Table"
    name_plural = "Custom Tables"
    icon = "fa-solid fa-table-columns"
    column_list = [
        CustomDifficultyTable.id,
        CustomDifficultyTable.owner_id,
        CustomDifficultyTable.name,
        CustomDifficultyTable.is_public,
        CustomDifficultyTable.created_at,
    ]
    column_searchable_list = [CustomDifficultyTable.name]
    column_sortable_list = [CustomDifficultyTable.name, CustomDifficultyTable.created_at, CustomDifficultyTable.is_public]


class CustomCourseAdmin(ModelView, model=CustomCourse):
    name = "Custom Course"
    name_plural = "Custom Courses"
    icon = "fa-solid fa-route"
    column_list = [
        CustomCourse.id,
        CustomCourse.owner_id,
        CustomCourse.name,
        CustomCourse.created_at,
    ]
    column_searchable_list = [CustomCourse.name]
    column_sortable_list = [CustomCourse.name, CustomCourse.created_at]


class ScheduleAdmin(ModelView, model=Schedule):
    name = "Schedule"
    name_plural = "Schedules"
    icon = "fa-solid fa-calendar"
    column_list = [
        Schedule.id,
        Schedule.user_id,
        Schedule.title,
        Schedule.scheduled_date,
        Schedule.is_completed,
    ]
    column_searchable_list = [Schedule.title]
    column_sortable_list = [Schedule.scheduled_date, Schedule.is_completed]


class UserRankingAdmin(ModelView, model=UserRanking):
    name = "User Ranking"
    name_plural = "User Rankings"
    icon = "fa-solid fa-ranking-star"
    column_list = [
        UserRanking.user_id,
        UserRanking.table_id,
        UserRanking.exp,
        UserRanking.exp_level,
        UserRanking.rating,
        UserRanking.rating_norm,
        UserRanking.dan_title,
        UserRanking.calculated_at,
    ]
    column_sortable_list = [
        UserRanking.exp,
        UserRanking.rating,
        UserRanking.rating_norm,
        UserRanking.calculated_at,
    ]
    column_searchable_list = [UserRanking.dan_title]
    can_create = False  # 계산 파이프라인으로만 생성
    can_edit = False    # 수동 수정은 데이터 정합성 파괴 위험

