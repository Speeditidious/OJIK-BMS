"""sqladmin ModelView definitions for all OJIK BMS models.

Data integrity rules applied here mirror the constraints in the API:
- Best-score tables (UserScore): no create, no delete.
- User: no delete (prevents accidental cascade wipeout).
"""
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqladmin import ModelView, action
from sqladmin.forms import Select2TagsField
from sqlalchemy import delete, func, null, select, text, tuple_, update
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.models.admin_action_log import AdminActionLog, AdminActionLogLine
from app.models.announcement import Announcement, AnnouncementTag, AnnouncementTemplate
from app.models.client_update import ClientUpdateAnnouncement
from app.models.course import Course
from app.models.day_note import UserDayNote
from app.models.difficulty_table import (
    CustomCourse,
    CustomDifficultyTable,
    DifficultyTable,
    UserFavoriteDifficultyTable,
)
from app.models.fumen import (
    Fumen,
    FumenPlayPopularity,
    FumenPopularityDirty,
    FumenPopularityWindow,
    FumenTableEntry,
    UserFumenTag,
)
from app.models.issue import Issue, IssueComment, IssueTag
from app.models.notification import (
    Notification,
    NotificationRead,
    NotificationUserState,
)
from app.models.ranking import (
    UserRanking,
    UserRatingUpdateDaily,
    UserTableRatingCheckpoint,
    UserTableRatingUpdateDaily,
)
from app.models.schedule import Schedule
from app.models.score import UserPlayerStats, UserScore
from app.models.table_import import TableImportLog, TableSourceAlias
from app.models.user import OAuthAccount, User

RESETTABLE_CLIENT_TYPES = frozenset({"lr2", "beatoraja"})
CLIENT_UPDATE_DEFAULT_PUBLISH_DELAY = timedelta(minutes=10)


def _admin_user_id(request: Request) -> uuid.UUID | None:
    raw = request.session.get("admin_user_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def _admin_details_redirect(request: Request, identity: str, pk: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(
        request.url_for("admin:details", identity=identity, pk=str(pk)),
        status_code=302,
    )


def _parse_admin_user_ids(raw_pks: str) -> list[uuid.UUID]:
    """Parse sqladmin comma-separated primary keys into UUIDs."""
    user_ids: list[uuid.UUID] = []
    for uid_str in [uid.strip() for uid in raw_pks.split(",") if uid.strip()]:
        try:
            user_ids.append(uuid.UUID(uid_str))
        except ValueError:
            continue
    return user_ids


def _clean_level_subset(value: object, level_order: object) -> list[str] | None:
    """Keep unique configured levels that exist in the table level_order."""
    allowed = {str(level).strip() for level in (level_order or []) if str(level).strip()}
    cleaned: list[str] = []
    seen: set[str] = set()
    raw_values = value if isinstance(value, list) else []
    for raw in raw_values:
        level = str(raw).strip()
        if not level or level in seen or level not in allowed:
            continue
        cleaned.append(level)
        seen.add(level)
    return cleaned or None


async def _reset_user_play_data(db, uid: uuid.UUID, client_type: str | None = None) -> None:
    """Delete selected play data for one user.

    When ``client_type`` is provided, only that client's score/stat rows and
    first-sync marker are removed. Other client data is preserved.
    """
    if client_type is not None and client_type not in RESETTABLE_CLIENT_TYPES:
        raise ValueError(f"Unsupported client_type for reset: {client_type}")

    score_filter = [UserScore.user_id == uid]
    stats_filter = [UserPlayerStats.user_id == uid]
    if client_type is not None:
        score_filter.append(UserScore.client_type == client_type)
        stats_filter.append(UserPlayerStats.client_type == client_type)

    await db.execute(delete(UserScore).where(*score_filter))
    await db.execute(delete(UserPlayerStats).where(*stats_filter))

    if client_type is None:
        await db.execute(update(User).where(User.id == uid).values(first_synced_at=null()))
        return

    await db.execute(
        text("""
            UPDATE users
               SET first_synced_at = (
                   CASE
                       WHEN first_synced_at IS NOT NULL
                        AND jsonb_typeof(first_synced_at) = 'object'
                       THEN first_synced_at - CAST(:client_type AS text)
                       ELSE first_synced_at
                   END
               )
             WHERE id = :uid
        """),
        {"uid": str(uid), "client_type": client_type},
    )


def _queue_user_ranking_recalculation(user_ids: list[uuid.UUID]) -> None:
    """Queue ranking recalculation after admin play-data reset."""
    if not user_ids:
        return
    try:
        from app.tasks.ranking_calculator import recalculate_user_rankings
    except Exception:
        return
    for uid in user_ids:
        try:
            recalculate_user_rankings.delay(str(uid))
        except Exception:
            pass


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

        user_ids = _parse_admin_user_ids(request.query_params.get("pks", ""))

        if user_ids:
            async with AsyncSessionLocal() as db:
                for uid in user_ids:
                    await _reset_user_play_data(db, uid)
                await db.commit()
            _queue_user_ranking_recalculation(user_ids)

        return RedirectResponse(request.url_for("admin:list", identity="user"), status_code=302)

    @action(
        name="reset_lr2_play_data",
        label="LR2 플레이 데이터 초기화",
        confirmation_message=(
            "선택한 유저의 LR2 플레이 데이터만 삭제됩니다. "
            "Beatoraja 데이터는 유지되며, first_synced_at의 lr2 키만 제거됩니다. "
            "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def reset_lr2_play_data(self, request: Request) -> RedirectResponse:
        """Delete only LR2 play data for selected users."""
        from app.core.database import AsyncSessionLocal

        user_ids = _parse_admin_user_ids(request.query_params.get("pks", ""))

        if user_ids:
            async with AsyncSessionLocal() as db:
                for uid in user_ids:
                    await _reset_user_play_data(db, uid, "lr2")
                await db.commit()
            _queue_user_ranking_recalculation(user_ids)

        return RedirectResponse(request.url_for("admin:list", identity="user"), status_code=302)

    @action(
        name="reset_beatoraja_play_data",
        label="Beatoraja 플레이 데이터 초기화",
        confirmation_message=(
            "선택한 유저의 Beatoraja 플레이 데이터만 삭제됩니다. "
            "LR2 데이터는 유지되며, first_synced_at의 beatoraja 키만 제거됩니다. "
            "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def reset_beatoraja_play_data(self, request: Request) -> RedirectResponse:
        """Delete only Beatoraja play data for selected users."""
        from app.core.database import AsyncSessionLocal

        user_ids = _parse_admin_user_ids(request.query_params.get("pks", ""))

        if user_ids:
            async with AsyncSessionLocal() as db:
                for uid in user_ids:
                    await _reset_user_play_data(db, uid, "beatoraja")
                await db.commit()
            _queue_user_ranking_recalculation(user_ids)

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
        OAuthAccount.discord_avatar_hash,
    ]
    column_searchable_list = [OAuthAccount.provider_username, OAuthAccount.provider_account_id]
    column_sortable_list = [OAuthAccount.provider, OAuthAccount.provider_username]


class AdminActionLogAdmin(ModelView, model=AdminActionLog):
    name = "Action Log"
    name_plural = "Action Logs"
    icon = "fa-solid fa-clipboard-list"
    column_list = [
        AdminActionLog.id,
        AdminActionLog.parent_log_id,
        AdminActionLog.action_name,
        AdminActionLog.target_kind,
        AdminActionLog.target_label,
        AdminActionLog.status,
        AdminActionLog.last_message,
        AdminActionLog.started_at,
        AdminActionLog.completed_at,
    ]
    column_details_list = [
        AdminActionLog.id,
        AdminActionLog.parent_log_id,
        AdminActionLog.action_name,
        AdminActionLog.target_kind,
        AdminActionLog.target_id,
        AdminActionLog.target_label,
        AdminActionLog.status,
        AdminActionLog.celery_task_id,
        AdminActionLog.payload,
        AdminActionLog.last_message,
        AdminActionLog.error_message,
        AdminActionLog.started_at,
        AdminActionLog.completed_at,
        AdminActionLog.lines,
    ]
    column_searchable_list = [
        AdminActionLog.action_name,
        AdminActionLog.target_id,
        AdminActionLog.target_label,
        AdminActionLog.status,
    ]
    column_sortable_list = [AdminActionLog.started_at, AdminActionLog.completed_at, AdminActionLog.status]
    column_default_sort = [(AdminActionLog.started_at, True)]
    can_create = False
    can_edit = False
    can_delete = True


class AdminActionLogLineAdmin(ModelView, model=AdminActionLogLine):
    name = "Action Log Line"
    name_plural = "Action Log Lines"
    icon = "fa-solid fa-list-check"
    column_list = [
        AdminActionLogLine.log_id,
        AdminActionLogLine.level,
        AdminActionLogLine.message,
        AdminActionLogLine.created_at,
    ]
    column_searchable_list = [AdminActionLogLine.level, AdminActionLogLine.message]
    column_sortable_list = [AdminActionLogLine.created_at, AdminActionLogLine.level]
    column_default_sort = [(AdminActionLogLine.created_at, True)]
    can_create = False
    can_edit = False
    can_delete = True


class AnnouncementTagAdmin(ModelView, model=AnnouncementTag):
    name = "Announcement Tag"
    name_plural = "Announcement Tags"
    icon = "fa-solid fa-tags"
    column_list = [
        AnnouncementTag.id,
        AnnouncementTag.name,
        AnnouncementTag.name_en,
        AnnouncementTag.name_ja,
        AnnouncementTag.color,
        AnnouncementTag.send_notification,
        AnnouncementTag.display_order,
    ]
    column_searchable_list = [AnnouncementTag.name]
    column_sortable_list = [AnnouncementTag.display_order, AnnouncementTag.name]
    form_excluded_columns = [AnnouncementTag.created_at, AnnouncementTag.updated_at]


class AnnouncementTemplateAdmin(ModelView, model=AnnouncementTemplate):
    name = "Announcement Template"
    name_plural = "Announcement Templates"
    icon = "fa-solid fa-file-lines"
    column_list = [
        AnnouncementTemplate.id,
        AnnouncementTemplate.tag,
        AnnouncementTemplate.title_template,
        AnnouncementTemplate.updated_at,
    ]
    form_excluded_columns = [AnnouncementTemplate.created_at, AnnouncementTemplate.updated_at]


class AnnouncementAdmin(ModelView, model=Announcement):
    name = "Announcement"
    name_plural = "Announcements"
    icon = "fa-solid fa-bullhorn"
    column_default_sort = [(Announcement.published_at, True)]
    column_list = [
        Announcement.id,
        Announcement.tag,
        Announcement.title,
        Announcement.is_published,
        Announcement.published_at,
        Announcement.updated_at,
    ]
    column_searchable_list = [Announcement.title, Announcement.title_en, Announcement.title_ja, Announcement.body, Announcement.body_en, Announcement.body_ja]
    column_sortable_list = [Announcement.published_at, Announcement.updated_at, Announcement.is_published]
    form_columns = [
        Announcement.tag,
        Announcement.title,
        Announcement.title_en,
        Announcement.title_ja,
        Announcement.body,
        Announcement.body_en,
        Announcement.body_ja,
        Announcement.is_published,
        Announcement.published_at,
    ]

    async def on_model_change(self, data, model, is_created, request) -> None:
        """Stamp published_at when an announcement is published."""
        is_published = data.get("is_published") if "is_published" in data else model.is_published
        published_at = data.get("published_at") if "published_at" in data else model.published_at
        if is_published and published_at is None:
            now = datetime.now(UTC)
            data["published_at"] = now
            model.published_at = now

    async def after_model_change(self, data, model, is_created, request) -> None:
        """Create a deduplicated notification after publish."""
        if not model.is_published:
            return
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.services.notifications import create_announcement_notification

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Announcement)
                .options(selectinload(Announcement.tag))
                .where(Announcement.id == model.id)
            )
            announcement = result.scalar_one_or_none()
            if announcement is not None:
                await create_announcement_notification(db, announcement)
                await db.commit()

    @action(
        name="publish_announcements",
        label="공지 공개하기",
        confirmation_message="선택한 공지를 공개하고 공개 시간을 현재 시각으로 채웁니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def publish_announcements(self, request: Request) -> RedirectResponse:
        """Publish selected announcements and stamp published_at if needed."""
        from app.core.database import AsyncSessionLocal
        from app.services.announcements import (
            publish_announcements as _publish_announcements,
        )

        pks = _parse_uuid_pks(request.query_params.get("pks", ""))
        if pks:
            async with AsyncSessionLocal() as db:
                await _publish_announcements(db, pks)
                await db.commit()

        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)


class NotificationAdmin(ModelView, model=Notification):
    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"
    column_list = [
        Notification.id,
        Notification.type,
        Notification.target_user_id,
        Notification.title,
        Notification.is_published,
        Notification.created_at,
    ]
    column_searchable_list = [Notification.type, Notification.title, Notification.body, Notification.dedupe_key]
    column_sortable_list = [Notification.type, Notification.created_at, Notification.is_published]
    can_create = False
    can_edit = False


class NotificationReadAdmin(ModelView, model=NotificationRead):
    name = "Notification Read"
    name_plural = "Notification Reads"
    icon = "fa-solid fa-envelope-open"
    column_list = [
        NotificationRead.user_id,
        NotificationRead.notification_id,
        NotificationRead.read_at,
        NotificationRead.deleted_at,
    ]
    column_sortable_list = [NotificationRead.read_at, NotificationRead.deleted_at]
    can_create = False
    can_edit = False


class NotificationUserStateAdmin(ModelView, model=NotificationUserState):
    name = "Notification User State"
    name_plural = "Notification User States"
    icon = "fa-solid fa-clock"
    column_list = [
        NotificationUserState.user_id,
        NotificationUserState.read_cutoff_at,
        NotificationUserState.updated_at,
    ]
    column_sortable_list = [NotificationUserState.read_cutoff_at, NotificationUserState.updated_at]
    can_create = False
    can_edit = False


class DifficultyTableAdmin(ModelView, model=DifficultyTable):
    name = "Difficulty Table"
    name_plural = "Difficulty Tables"
    icon = "fa-solid fa-table"
    create_template = "sqladmin/difficulty_table_create.html"
    edit_template = "sqladmin/difficulty_table_edit.html"
    column_list = [
        DifficultyTable.id,
        DifficultyTable.name,
        DifficultyTable.symbol,
        DifficultyTable.slug,
        DifficultyTable.is_default,
        DifficultyTable.display_level_order,
        DifficultyTable.non_regular_level_order,
        DifficultyTable.updated_at,
    ]
    column_searchable_list = [DifficultyTable.name, DifficultyTable.slug]
    column_sortable_list = [DifficultyTable.id, DifficultyTable.name, DifficultyTable.updated_at]
    form_columns = [
        DifficultyTable.name,
        DifficultyTable.symbol,
        DifficultyTable.slug,
        DifficultyTable.source_url,
        DifficultyTable.is_default,
        DifficultyTable.default_order,
        DifficultyTable.level_order,
        DifficultyTable.display_level_order,
        DifficultyTable.non_regular_level_order,
    ]
    form_overrides = {
        "display_level_order": Select2TagsField,
        "non_regular_level_order": Select2TagsField,
    }
    form_args = {
        "display_level_order": {
            "label": "Display Level Order",
            "description": "Optional level display order. Leave empty to use level_order.",
            "choices": [],
        },
        "non_regular_level_order": {
            "label": "Non-Regular Level Order",
            "description": "Levels shown after the main level group. Values missing from level_order are ignored.",
            "choices": [],
        },
    }

    async def on_model_change(
        self,
        data: dict,
        model: DifficultyTable,
        is_created: bool,
        request: Request,
    ) -> None:
        """Normalize admin-managed level order lists before saving."""
        level_order = data.get("level_order") or model.level_order
        data["display_level_order"] = _clean_level_subset(
            data.get("display_level_order"),
            level_order,
        )
        data["non_regular_level_order"] = _clean_level_subset(
            data.get("non_regular_level_order"),
            level_order,
        )

    @action(
        name="add_by_url",
        label="URL로 추가/최신화",
        add_in_list=True,
    )
    async def add_by_url(self, request: Request) -> RedirectResponse:
        """Open the URL-only table sync form."""
        return RedirectResponse("/admin/difficulty-tables/add-by-url", status_code=302)

    @action(
        name="sync_selected_tables",
        label="선택된 테이블 최신화",
        confirmation_message="선택된 난이도표들을 최신화합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def sync_selected_tables(self, request: Request) -> RedirectResponse:
        """Queue Celery sync tasks for each selected difficulty table."""
        from app.services.admin_action_log import create_log, mark_task_id
        from app.tasks.table_updater import update_difficulty_table

        pks = request.query_params.get("pks", "")
        selected = [p.strip() for p in pks.split(",") if p.strip()]
        if not selected:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity), status_code=302
            )

        parent_log_id = None
        if len(selected) > 1:
            parent_log_id = await create_log(
                action_name="sync_selected_tables",
                target_kind="difficulty_table_batch",
                target_label=f"{len(selected)} tables",
                triggered_by=_admin_user_id(request),
                payload={"table_ids": selected},
            )

        log_ids: list[uuid.UUID] = []
        for pk in selected:
            log_id = await create_log(
                action_name="sync_selected_tables",
                target_kind="difficulty_table",
                target_id=pk,
                parent_log_id=parent_log_id,
                triggered_by=_admin_user_id(request),
            )
            task_result = update_difficulty_table.delay(pk, log_id=str(log_id))
            if getattr(task_result, "id", None):
                await mark_task_id(log_id, task_result.id)
            log_ids.append(log_id)

        return _admin_details_redirect(
            request,
            AdminActionLogAdmin.identity,
            parent_log_id or log_ids[0],
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
        from app.services.admin_action_log import create_log, mark_task_id
        from app.tasks.table_updater import update_all_difficulty_tables

        log_id = await create_log(
            action_name="sync_all_tables",
            target_kind="difficulty_table_batch",
            target_label="All DB tables",
            triggered_by=_admin_user_id(request),
            payload={"default_only": False, "force": True},
        )
        task_result = update_all_difficulty_tables.delay(log_id=str(log_id))
        if getattr(task_result, "id", None):
            await mark_task_id(log_id, task_result.id)

        return _admin_details_redirect(request, AdminActionLogAdmin.identity, log_id)

    @action(
        name="sync_default_tables",
        label="기본 테이블만 최신화",
        confirmation_message="config.toml의 기본 난이도표만 강제로 최신화합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def sync_default_tables(self, request: Request) -> RedirectResponse:
        """Queue a Celery task to force-sync default difficulty tables only."""
        from app.services.admin_action_log import create_log, mark_task_id
        from app.tasks.table_updater import update_all_difficulty_tables

        log_id = await create_log(
            action_name="sync_default_tables",
            target_kind="difficulty_table_batch",
            target_label="Default tables",
            triggered_by=_admin_user_id(request),
            payload={"default_only": True, "force": True},
        )
        task_result = update_all_difficulty_tables.delay(
            log_id=str(log_id),
            default_only=True,
            force=True,
        )
        if getattr(task_result, "id", None):
            await mark_task_id(log_id, task_result.id)

        return _admin_details_redirect(request, AdminActionLogAdmin.identity, log_id)

    @action(
        name="recalculate_rankings",
        label="랭킹 재계산",
        confirmation_message="선택된 난이도표의 전체 유저 랭킹을 재계산합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def recalculate_rankings(self, request: Request) -> RedirectResponse:
        """Queue ranking recalculation for selected difficulty tables."""
        from app.services.admin_action_log import create_log, mark_task_id
        from app.services.ranking_config import get_ranking_config
        from app.tasks.ranking_calculator import recalculate_all_rankings

        pks = request.query_params.get("pks", "")
        ids = [p.strip() for p in pks.split(",") if p.strip()]

        try:
            config = get_ranking_config()
        except RuntimeError:
            config = None

        if config is None:
            log_id = await create_log(
                action_name="recalculate_rankings",
                target_kind="ranking_batch",
                target_label="All ranking tables",
                triggered_by=_admin_user_id(request),
            )
            task_result = recalculate_all_rankings.delay(log_id=str(log_id))
            if getattr(task_result, "id", None):
                await mark_task_id(log_id, task_result.id)
            return _admin_details_redirect(request, AdminActionLogAdmin.identity, log_id)

        id_to_slug = {str(t.table_id): t.slug for t in config.tables}
        slugs = [id_to_slug[pk] for pk in ids if pk in id_to_slug]
        if not slugs:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity), status_code=302
            )

        parent_log_id = None
        if len(slugs) > 1:
            parent_log_id = await create_log(
                action_name="recalculate_rankings",
                target_kind="ranking_batch",
                target_label=f"{len(slugs)} ranking tables",
                triggered_by=_admin_user_id(request),
                payload={"slugs": slugs},
            )

        log_ids: list[uuid.UUID] = []
        for slug in slugs:
            log_id = await create_log(
                action_name="recalculate_rankings",
                target_kind="ranking_table",
                target_id=slug,
                target_label=slug,
                parent_log_id=parent_log_id,
                triggered_by=_admin_user_id(request),
            )
            task_result = recalculate_all_rankings.delay(slug, log_id=str(log_id))
            if getattr(task_result, "id", None):
                await mark_task_id(log_id, task_result.id)
            log_ids.append(log_id)

        return _admin_details_redirect(
            request,
            AdminActionLogAdmin.identity,
            parent_log_id or log_ids[0],
        )


class FumenAdmin(ModelView, model=Fumen):
    name = "Fumen"
    name_plural = "Fumens"
    icon = "fa-solid fa-music"
    column_list = [Fumen.fumen_id, Fumen.title, Fumen.artist, Fumen.md5, Fumen.sha256, Fumen.bpm_max, Fumen.keymode]
    column_searchable_list = [Fumen.title, Fumen.artist, Fumen.md5, Fumen.sha256]
    column_sortable_list = [Fumen.title, Fumen.artist, Fumen.bpm_max, Fumen.keymode, Fumen.created_at]


class FumenTableEntryAdmin(ModelView, model=FumenTableEntry):
    name = "Fumen Table Entry"
    name_plural = "Fumen Table Entries"
    icon = "fa-solid fa-list"
    column_list = [
        FumenTableEntry.fumen_id,
        FumenTableEntry.table_id,
        FumenTableEntry.level,
        FumenTableEntry.updated_at,
    ]
    column_searchable_list = [FumenTableEntry.level]
    column_sortable_list = [FumenTableEntry.table_id, FumenTableEntry.level, FumenTableEntry.updated_at]
    can_create = False
    can_edit = False
    can_delete = False


class FumenPlayPopularityAdmin(ModelView, model=FumenPlayPopularity):
    name = "Fumen Play Popularity"
    name_plural = "Fumen Play Popularity"
    icon = "fa-solid fa-chart-simple"
    column_list = [
        FumenPlayPopularity.fumen_id,
        FumenPlayPopularity.played_user_count,
        FumenPlayPopularity.total_play_count,
        FumenPlayPopularity.updated_at,
    ]
    column_sortable_list = [
        FumenPlayPopularity.played_user_count,
        FumenPlayPopularity.total_play_count,
        FumenPlayPopularity.updated_at,
    ]
    can_create = False
    can_edit = False
    can_delete = False


class FumenPopularityDirtyAdmin(ModelView, model=FumenPopularityDirty):
    name = "Fumen Popularity Dirty"
    name_plural = "Fumen Popularity Dirty Queue"
    icon = "fa-solid fa-list-check"
    column_list = [FumenPopularityDirty.fumen_id, FumenPopularityDirty.queued_at]
    column_sortable_list = [FumenPopularityDirty.queued_at]
    can_create = False
    can_edit = False
    can_delete = True


class FumenPopularityWindowAdmin(ModelView, model=FumenPopularityWindow):
    name = "Fumen Popularity Window"
    name_plural = "Fumen Popularity Windows"
    icon = "fa-solid fa-ranking-star"
    column_list = [
        FumenPopularityWindow.window,
        FumenPopularityWindow.rank,
        FumenPopularityWindow.fumen_id,
        FumenPopularityWindow.played_user_count,
        FumenPopularityWindow.play_count,
        FumenPopularityWindow.computed_at,
    ]
    column_sortable_list = [
        FumenPopularityWindow.window,
        FumenPopularityWindow.rank,
        FumenPopularityWindow.played_user_count,
        FumenPopularityWindow.play_count,
        FumenPopularityWindow.computed_at,
    ]
    can_create = False
    can_edit = False
    can_delete = False


class UserScoreAdmin(ModelView, model=UserScore):
    name = "User Score"
    name_plural = "User Scores"
    icon = "fa-solid fa-star"
    column_list = [
        UserScore.id,
        UserScore.user_id,
        UserScore.scorehash,
        UserScore.fumen_id,
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
    column_searchable_list = [
        UserScore.id,
        UserScore.user_id,
        UserScore.client_type,
        UserScore.scorehash,
        UserScore.fumen_id,
        UserScore.fumen_sha256,
        UserScore.fumen_md5,
        UserScore.fumen_hash_others,
        UserScore.clear_type,
        UserScore.exscore,
        UserScore.rate,
        UserScore.rank,
        UserScore.max_combo,
        UserScore.min_bp,
        UserScore.play_count,
        UserScore.clear_count,
        UserScore.judgments,
        UserScore.options,
        UserScore.recorded_at,
        UserScore.synced_at,
    ]
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
    column_searchable_list = [
        UserPlayerStats.id,
        UserPlayerStats.user_id,
        UserPlayerStats.client_type,
        UserPlayerStats.synced_at,
        UserPlayerStats.playcount,
        UserPlayerStats.clearcount,
        UserPlayerStats.playtime,
        UserPlayerStats.judgments,
    ]
    column_sortable_list = [
        UserPlayerStats.id,
        UserPlayerStats.user_id,
        UserPlayerStats.client_type,
        UserPlayerStats.synced_at,
        UserPlayerStats.playcount,
        UserPlayerStats.clearcount,
        UserPlayerStats.playtime,
    ]
    column_default_sort = [(UserPlayerStats.synced_at, True)]
    # judgments (JSONB) intentionally omitted from column_list


class CourseAdmin(ModelView, model=Course):
    name = "Course"
    name_plural = "Courses"
    icon = "fa-solid fa-list-ol"
    column_list = [
        Course.id,
        Course.name,
        Course.source_table_id,
        Course.constraint,
        Course.is_active,
        Course.dan_title,
        Course.synced_at,
    ]
    column_searchable_list = [Course.name, Course.dan_title]
    column_sortable_list = [Course.synced_at, Course.is_active, Course.name]


class ClientUpdateAnnouncementAdmin(ModelView, model=ClientUpdateAnnouncement):
    name = "Client Update"
    name_plural = "Client Updates"
    icon = "fa-solid fa-bullhorn"
    column_default_sort = [(ClientUpdateAnnouncement.updated_at, True)]
    column_list = [
        ClientUpdateAnnouncement.version,
        ClientUpdateAnnouncement.channel,
        ClientUpdateAnnouncement.target_os,
        ClientUpdateAnnouncement.arch,
        ClientUpdateAnnouncement.mandatory,
        ClientUpdateAnnouncement.is_published,
        ClientUpdateAnnouncement.publish_after,
        ClientUpdateAnnouncement.published_at,
        ClientUpdateAnnouncement.updated_at,
    ]
    column_searchable_list = [
        ClientUpdateAnnouncement.version,
        ClientUpdateAnnouncement.title,
        ClientUpdateAnnouncement.body_markdown,
        ClientUpdateAnnouncement.body_markdown_en,
        ClientUpdateAnnouncement.body_markdown_ja,
    ]
    column_sortable_list = [
        ClientUpdateAnnouncement.version,
        ClientUpdateAnnouncement.is_published,
        ClientUpdateAnnouncement.publish_after,
        ClientUpdateAnnouncement.published_at,
        ClientUpdateAnnouncement.updated_at,
    ]
    form_columns = [
        ClientUpdateAnnouncement.version,
        ClientUpdateAnnouncement.channel,
        ClientUpdateAnnouncement.target_os,
        ClientUpdateAnnouncement.arch,
        ClientUpdateAnnouncement.installer_kind,
        ClientUpdateAnnouncement.title,
        ClientUpdateAnnouncement.body_markdown,
        ClientUpdateAnnouncement.body_markdown_en,
        ClientUpdateAnnouncement.body_markdown_ja,
        ClientUpdateAnnouncement.release_page_url,
        ClientUpdateAnnouncement.update_url,
        ClientUpdateAnnouncement.tauri_signature,
        ClientUpdateAnnouncement.asset_size_bytes,
        ClientUpdateAnnouncement.asset_sha256,
        ClientUpdateAnnouncement.mandatory,
        ClientUpdateAnnouncement.min_supported_version,
        ClientUpdateAnnouncement.is_published,
        ClientUpdateAnnouncement.publish_after,
    ]

    async def on_model_change(self, data, model, is_created, request) -> None:
        """Stamp published_at when an admin publishes a client update, and validate signed rows."""
        from sqladmin.exceptions import SQLAdminException

        update_url = (data.get("update_url") or model.update_url or "").strip()
        if not update_url.startswith("https://"):
            raise SQLAdminException("update_url은 https:// 로 시작해야 합니다.")

        github_page_pattern = "github.com/"
        if "/releases/tag/" in update_url and github_page_pattern in update_url:
            raise SQLAdminException(
                "update_url은 GitHub 릴리즈 페이지가 아닌 직접 다운로드 URL이어야 합니다."
            )

        tauri_signature = data.get("tauri_signature") if "tauri_signature" in data else model.tauri_signature
        asset_sha256 = data.get("asset_sha256") if "asset_sha256" in data else model.asset_sha256
        asset_size_bytes = data.get("asset_size_bytes") if "asset_size_bytes" in data else model.asset_size_bytes
        if tauri_signature:
            if not asset_sha256 or not asset_size_bytes:
                raise SQLAdminException(
                    "tauri_signature가 있으면 asset_sha256과 asset_size_bytes도 필수입니다."
                )

        is_published = data.get("is_published") if "is_published" in data else model.is_published
        if is_published and model.published_at is None:
            model.published_at = datetime.now(UTC)
        if is_published and model.publish_after is None:
            model.publish_after = _client_update_default_publish_after()
        if is_published:
            await _trigger_revalidate()

    async def after_model_change(self, data, model, is_created, request) -> None:
        """Create a deduplicated notification after publish."""
        if not model.is_published:
            return
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.services.notifications import create_client_update_notification

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ClientUpdateAnnouncement).where(ClientUpdateAnnouncement.id == model.id)
            )
            update_row = result.scalar_one_or_none()
            if update_row is not None:
                await create_client_update_notification(db, update_row)
                await db.commit()

    @action(
        name="publish_updates",
        label="업데이트 알림 예약하기",
        confirmation_message=(
            "선택한 업데이트를 공개 예약합니다. 기본적으로 약 10분 뒤 설치된 클라이언트에 표시됩니다. "
            "계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def publish_updates(self, request: Request) -> RedirectResponse:
        """Publish selected announcements and stamp published_at if needed."""
        from app.core.database import AsyncSessionLocal

        pks = _parse_uuid_pks(request.query_params.get("pks", ""))
        if pks:
            now = datetime.now(UTC)
            visible_at = _client_update_default_publish_after(now)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(ClientUpdateAnnouncement)
                    .where(ClientUpdateAnnouncement.id.in_(pks))
                    .values(
                        is_published=True,
                        published_at=func.coalesce(ClientUpdateAnnouncement.published_at, now),
                        publish_after=func.coalesce(ClientUpdateAnnouncement.publish_after, visible_at),
                        updated_at=now,
                    )
                )
                result = await db.execute(select(ClientUpdateAnnouncement).where(ClientUpdateAnnouncement.id.in_(pks)))
                from app.services.notifications import create_client_update_notification

                for update_row in result.scalars().all():
                    await create_client_update_notification(db, update_row)
                await db.commit()

        if pks:
            await _trigger_revalidate()

        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    @action(
        name="publish_same_version_updates",
        label="같은 버전 전체 업데이트 알림 예약하기",
        confirmation_message=(
            "선택한 업데이트와 같은 version/channel의 모든 target_os/arch/installer_kind row를 공개 예약합니다. "
            "기본적으로 약 10분 뒤 설치된 클라이언트에 표시됩니다. 계속하시겠습니까?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def publish_same_version_updates(self, request: Request) -> RedirectResponse:
        """Publish every target row sharing the selected rows' version/channel."""
        from app.core.database import AsyncSessionLocal
        from app.services.notifications import create_client_update_notification

        pks = _parse_uuid_pks(request.query_params.get("pks", ""))
        if pks:
            now = datetime.now(UTC)
            visible_at = _client_update_default_publish_after(now)
            async with AsyncSessionLocal() as db:
                selected_result = await db.execute(
                    select(ClientUpdateAnnouncement).where(ClientUpdateAnnouncement.id.in_(pks))
                )
                selected_pairs = {
                    (row.version, row.channel) for row in selected_result.scalars().all()
                }

                if selected_pairs:
                    target_rows_result = await db.execute(
                        select(ClientUpdateAnnouncement).where(
                            tuple_(
                                ClientUpdateAnnouncement.version,
                                ClientUpdateAnnouncement.channel,
                            ).in_(selected_pairs)
                        )
                    )
                    target_rows = target_rows_result.scalars().all()
                    target_ids = [row.id for row in target_rows]
                    if not target_ids:
                        await db.commit()
                        return RedirectResponse(
                            request.url_for("admin:list", identity=self.identity),
                            status_code=302,
                        )

                    await db.execute(
                        update(ClientUpdateAnnouncement)
                        .where(ClientUpdateAnnouncement.id.in_(target_ids))
                        .values(
                            is_published=True,
                            published_at=func.coalesce(ClientUpdateAnnouncement.published_at, now),
                            publish_after=func.coalesce(
                                ClientUpdateAnnouncement.publish_after, visible_at
                            ),
                            updated_at=now,
                        )
                    )

                    for update_row in target_rows:
                        update_row.is_published = True
                        update_row.published_at = update_row.published_at or now
                        update_row.publish_after = update_row.publish_after or visible_at
                        await create_client_update_notification(db, update_row)
                    await db.commit()

        if pks:
            await _trigger_revalidate()

        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)

    @action(
        name="unpublish_updates",
        label="업데이트 알림 내리기",
        confirmation_message="선택한 업데이트를 비공개로 전환합니다. 계속하시겠습니까?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def unpublish_updates(self, request: Request) -> RedirectResponse:
        """Hide selected announcements from client update endpoints."""
        from app.core.database import AsyncSessionLocal

        pks = _parse_uuid_pks(request.query_params.get("pks", ""))
        if pks:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(ClientUpdateAnnouncement)
                    .where(ClientUpdateAnnouncement.id.in_(pks))
                    .values(is_published=False, updated_at=datetime.now(UTC))
                )
                await db.commit()

        return RedirectResponse(request.url_for("admin:list", identity=self.identity), status_code=302)


def _client_update_default_publish_after(now: datetime | None = None) -> datetime:
    """Return the default visibility time for newly published client updates."""
    return (now or datetime.now(UTC)) + CLIENT_UPDATE_DEFAULT_PUBLISH_DELAY


async def _trigger_revalidate() -> None:
    """Fire-and-forget call to Next.js /api/revalidate to bust the client-release cache."""
    from app.core.config import settings

    secret = settings.REVALIDATE_SECRET
    frontend_url = settings.FRONTEND_URL
    if not secret or not frontend_url:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{frontend_url}/api/revalidate",
                headers={"x-revalidate-secret": secret},
            )
    except Exception:
        logging.getLogger(__name__).warning("Failed to trigger Next.js revalidate", exc_info=True)


def _parse_uuid_pks(raw: str) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for pk in [part.strip() for part in raw.split(",") if part.strip()]:
        try:
            ids.append(uuid.UUID(pk))
        except ValueError:
            continue
    return ids


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


class TableImportLogAdmin(ModelView, model=TableImportLog):
    name = "Table Import Log"
    name_plural = "Table Import Logs"
    icon = "fa-solid fa-file-import"
    column_list = [
        TableImportLog.id,
        TableImportLog.user_id,
        TableImportLog.source_url,
        TableImportLog.outcome,
        TableImportLog.created_at,
    ]
    column_searchable_list = [TableImportLog.source_url, TableImportLog.outcome]
    column_sortable_list = [TableImportLog.created_at, TableImportLog.outcome]
    can_create = False
    can_edit = False


class TableSourceAliasAdmin(ModelView, model=TableSourceAlias):
    name = "Table Source Alias"
    name_plural = "Table Source Aliases"
    icon = "fa-solid fa-link"
    column_list = [
        TableSourceAlias.id,
        TableSourceAlias.alias_url,
        TableSourceAlias.table_id,
        TableSourceAlias.created_at,
    ]
    column_searchable_list = [TableSourceAlias.alias_url]
    column_sortable_list = [TableSourceAlias.created_at]

    async def on_model_change(self, data, model, is_created, request) -> None:
        """Store aliases in the same canonical URL form used by imports."""
        from app.services.table_sync import canonicalize_table_url

        alias_url = data.get("alias_url") if "alias_url" in data else model.alias_url
        if alias_url:
            model.alias_url = canonicalize_table_url(alias_url)


class UserFumenTagAdmin(ModelView, model=UserFumenTag):
    name = "Fumen Tag"
    name_plural = "Fumen Tags"
    icon = "fa-solid fa-tag"
    column_list = [
        UserFumenTag.id,
        UserFumenTag.user_id,
        UserFumenTag.fumen_id,
        UserFumenTag.tag,
    ]
    column_searchable_list = [UserFumenTag.tag]
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


class UserTableRatingCheckpointAdmin(ModelView, model=UserTableRatingCheckpoint):
    name = "Rating Checkpoint"
    name_plural = "Rating Checkpoints"
    icon = "fa-solid fa-wave-square"
    column_list = [
        UserTableRatingCheckpoint.user_id,
        UserTableRatingCheckpoint.table_id,
        UserTableRatingCheckpoint.effective_date,
        UserTableRatingCheckpoint.exp,
        UserTableRatingCheckpoint.rating,
    ]
    column_searchable_list = [
        UserTableRatingCheckpoint.user_id,
        UserTableRatingCheckpoint.table_id,
        UserTableRatingCheckpoint.effective_date,
    ]
    column_sortable_list = [
        UserTableRatingCheckpoint.user_id,
        UserTableRatingCheckpoint.table_id,
        UserTableRatingCheckpoint.effective_date,
        UserTableRatingCheckpoint.exp,
        UserTableRatingCheckpoint.rating,
    ]
    column_default_sort = [(UserTableRatingCheckpoint.effective_date, True)]
    can_create = False
    can_edit = False
    can_delete = False


class UserTableRatingUpdateDailyAdmin(ModelView, model=UserTableRatingUpdateDaily):
    name = "Rating Updates By Table"
    name_plural = "Rating Updates By Table"
    icon = "fa-solid fa-table-list"
    column_list = [
        UserTableRatingUpdateDaily.user_id,
        UserTableRatingUpdateDaily.table_id,
        UserTableRatingUpdateDaily.effective_date,
        UserTableRatingUpdateDaily.update_count,
    ]
    column_searchable_list = [
        UserTableRatingUpdateDaily.user_id,
        UserTableRatingUpdateDaily.table_id,
        UserTableRatingUpdateDaily.effective_date,
    ]
    column_sortable_list = [
        UserTableRatingUpdateDaily.user_id,
        UserTableRatingUpdateDaily.table_id,
        UserTableRatingUpdateDaily.effective_date,
        UserTableRatingUpdateDaily.update_count,
    ]
    column_default_sort = [(UserTableRatingUpdateDaily.effective_date, True)]
    can_create = False
    can_edit = False
    can_delete = False


class UserRatingUpdateDailyAdmin(ModelView, model=UserRatingUpdateDaily):
    name = "Rating Updates Aggregated"
    name_plural = "Rating Updates Aggregated"
    icon = "fa-solid fa-layer-group"
    column_list = [
        UserRatingUpdateDaily.user_id,
        UserRatingUpdateDaily.effective_date,
        UserRatingUpdateDaily.update_count,
    ]
    column_searchable_list = [
        UserRatingUpdateDaily.user_id,
        UserRatingUpdateDaily.effective_date,
    ]
    column_sortable_list = [
        UserRatingUpdateDaily.user_id,
        UserRatingUpdateDaily.effective_date,
        UserRatingUpdateDaily.update_count,
    ]
    column_default_sort = [(UserRatingUpdateDaily.effective_date, True)]
    can_create = False
    can_edit = False
    can_delete = False


# ── Issue domain ───────────────────────────────────────────────────────────────

class IssueTagAdmin(ModelView, model=IssueTag):
    name = "Issue Tag"
    name_plural = "Issue Tags"
    icon = "fa-solid fa-tags"
    column_list = [IssueTag.slug, IssueTag.name, IssueTag.is_active, IssueTag.display_order, IssueTag.updated_at]
    column_searchable_list = [IssueTag.slug, IssueTag.name, IssueTag.content_hint]
    column_sortable_list = [IssueTag.display_order, IssueTag.name, IssueTag.is_active]
    form_excluded_columns = [IssueTag.created_at, IssueTag.updated_at]
    can_delete = False


class IssueAdmin(ModelView, model=Issue):
    name = "Issue"
    name_plural = "Issues"
    icon = "fa-solid fa-circle-exclamation"
    column_list = [Issue.id, Issue.title, Issue.tag, Issue.status, Issue.is_pinned, Issue.author, Issue.comment_count, Issue.last_activity_at]
    column_searchable_list = [Issue.title, Issue.body]
    column_sortable_list = [Issue.id, Issue.status, Issue.is_pinned, Issue.pinned_at, Issue.comment_count, Issue.last_activity_at, Issue.created_at]
    form_excluded_columns = [Issue.created_at, Issue.updated_at, Issue.comment_count, Issue.last_activity_at, Issue.pinned_at]
    can_create = False
    can_delete = False


class IssueCommentAdmin(ModelView, model=IssueComment):
    name = "Issue Comment"
    name_plural = "Issue Comments"
    icon = "fa-solid fa-comments"
    column_list = [IssueComment.id, IssueComment.issue_id, IssueComment.author, IssueComment.created_at]
    column_searchable_list = [IssueComment.body]
    column_sortable_list = [IssueComment.created_at]
    can_create = False
    can_delete = False


class UserDayNoteAdmin(ModelView, model=UserDayNote):
    name = "Day Note"
    name_plural = "Day Notes"
    icon = "fa-solid fa-note-sticky"
    column_list = [UserDayNote.id, UserDayNote.user_id, UserDayNote.note_date, UserDayNote.title, UserDayNote.content, UserDayNote.updated_at]
    column_searchable_list = [UserDayNote.title, UserDayNote.content]
    column_sortable_list = [UserDayNote.note_date, UserDayNote.updated_at]
    can_create = False
    can_edit = False
