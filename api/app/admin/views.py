"""sqladmin ModelView definitions for all OJIK BMS models.

Data integrity rules applied here mirror the constraints in the API:
- Append-only tables (ScoreHistory, CourseScoreHistory): read-only.
- Best-score tables (UserScore, UserCourseScore): no create, no delete.
- User: no delete (prevents accidental cascade wipeout).
- ChatbotDocument: embedding column excluded (pgvector breaks the form renderer).
"""
from sqladmin import ModelView

from app.models.chatbot import (
    ChatbotConversation,
    ChatbotDocument,
    ChatbotUsageLimit,
)
from app.models.course import Course, CourseScoreHistory, UserCourseScore
from app.models.score import ScoreHistory, UserPlayerStats, UserScore
from app.models.song import Song
from app.models.table import CustomCourse, CustomTable, DifficultyTable, Schedule
from app.models.user import OAuthAccount, User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.username, User.is_active, User.is_public, User.is_admin, User.created_at]
    column_searchable_list = [User.username]
    column_sortable_list = [User.username, User.created_at, User.is_active, User.is_admin]
    can_delete = False  # Deleting a user triggers cascades across all score tables


class OAuthAccountAdmin(ModelView, model=OAuthAccount):
    name = "OAuth Account"
    name_plural = "OAuth Accounts"
    icon = "fa-brands fa-discord"
    column_list = [
        OAuthAccount.id,
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
        DifficultyTable.last_synced_at,
    ]
    column_searchable_list = [DifficultyTable.name, DifficultyTable.slug]
    column_sortable_list = [DifficultyTable.id, DifficultyTable.name, DifficultyTable.last_synced_at]
    # table_data (large JSONB) is intentionally omitted from column_list above


class SongAdmin(ModelView, model=Song):
    name = "Song"
    name_plural = "Songs"
    icon = "fa-solid fa-music"
    column_list = [Song.id, Song.title, Song.artist, Song.md5, Song.sha256, Song.bpm]
    column_searchable_list = [Song.title, Song.artist, Song.md5, Song.sha256]
    column_sortable_list = [Song.title, Song.artist, Song.bpm, Song.created_at]


class UserScoreAdmin(ModelView, model=UserScore):
    name = "User Score"
    name_plural = "User Scores"
    icon = "fa-solid fa-star"
    column_list = [
        UserScore.id,
        UserScore.user_id,
        UserScore.song_sha256,
        UserScore.song_md5,
        UserScore.client_type,
        UserScore.clear_type,
        UserScore.score_rate,
        UserScore.play_count,
        UserScore.played_at,
    ]
    column_searchable_list = [UserScore.song_sha256, UserScore.song_md5]
    column_sortable_list = [UserScore.played_at, UserScore.synced_at, UserScore.score_rate]
    can_create = False  # Scores must enter through the sync pipeline
    can_delete = False  # Blind deletion would break score history continuity


class ScoreHistoryAdmin(ModelView, model=ScoreHistory):
    name = "Score History"
    name_plural = "Score History"
    icon = "fa-solid fa-clock-rotate-left"
    column_list = [
        ScoreHistory.id,
        ScoreHistory.user_id,
        ScoreHistory.song_sha256,
        ScoreHistory.client_type,
        ScoreHistory.clear_type,
        ScoreHistory.score_rate,
        ScoreHistory.recorded_at,
    ]
    column_searchable_list = [ScoreHistory.song_sha256, ScoreHistory.song_md5]
    column_sortable_list = [ScoreHistory.recorded_at]
    # Append-only: no mutations allowed
    can_create = False
    can_edit = False
    can_delete = False


class UserPlayerStatsAdmin(ModelView, model=UserPlayerStats):
    name = "Player Stats"
    name_plural = "Player Stats"
    icon = "fa-solid fa-chart-bar"
    column_list = [
        UserPlayerStats.user_id,
        UserPlayerStats.client_type,
        UserPlayerStats.total_notes_hit,
        UserPlayerStats.total_play_count,
        UserPlayerStats.synced_at,
    ]
    column_sortable_list = [UserPlayerStats.synced_at, UserPlayerStats.total_notes_hit]


class CourseAdmin(ModelView, model=Course):
    name = "Course"
    name_plural = "Courses"
    icon = "fa-solid fa-list-ol"
    column_list = [Course.course_hash, Course.source, Course.song_count, Course.created_at]
    column_searchable_list = [Course.course_hash]
    column_sortable_list = [Course.created_at, Course.song_count, Course.source]


class UserCourseScoreAdmin(ModelView, model=UserCourseScore):
    name = "User Course Score"
    name_plural = "User Course Scores"
    icon = "fa-solid fa-trophy"
    column_list = [
        UserCourseScore.id,
        UserCourseScore.user_id,
        UserCourseScore.course_hash,
        UserCourseScore.client_type,
        UserCourseScore.clear_type,
        UserCourseScore.score_rate,
        UserCourseScore.play_count,
        UserCourseScore.played_at,
    ]
    column_searchable_list = [UserCourseScore.course_hash]
    column_sortable_list = [UserCourseScore.played_at, UserCourseScore.score_rate]
    can_create = False
    can_delete = False


class CourseScoreHistoryAdmin(ModelView, model=CourseScoreHistory):
    name = "Course Score History"
    name_plural = "Course Score History"
    icon = "fa-solid fa-flag-checkered"
    column_list = [
        CourseScoreHistory.id,
        CourseScoreHistory.user_id,
        CourseScoreHistory.course_hash,
        CourseScoreHistory.client_type,
        CourseScoreHistory.clear_type,
        CourseScoreHistory.score_rate,
        CourseScoreHistory.recorded_at,
    ]
    column_searchable_list = [CourseScoreHistory.course_hash]
    column_sortable_list = [CourseScoreHistory.recorded_at]
    # Append-only: no mutations allowed
    can_create = False
    can_edit = False
    can_delete = False


class CustomTableAdmin(ModelView, model=CustomTable):
    name = "Custom Table"
    name_plural = "Custom Tables"
    icon = "fa-solid fa-table-columns"
    column_list = [
        CustomTable.id,
        CustomTable.owner_id,
        CustomTable.name,
        CustomTable.is_public,
        CustomTable.created_at,
    ]
    column_searchable_list = [CustomTable.name]
    column_sortable_list = [CustomTable.name, CustomTable.created_at, CustomTable.is_public]


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


class ChatbotDocumentAdmin(ModelView, model=ChatbotDocument):
    name = "Chatbot Document"
    name_plural = "Chatbot Documents"
    icon = "fa-solid fa-file-lines"
    column_list = [
        ChatbotDocument.id,
        ChatbotDocument.category,
        ChatbotDocument.title,
        ChatbotDocument.chunk_index,
        ChatbotDocument.updated_at,
    ]
    column_searchable_list = [ChatbotDocument.title, ChatbotDocument.category]
    column_sortable_list = [ChatbotDocument.category, ChatbotDocument.updated_at]
    # pgvector column crashes the form renderer — always exclude it from forms
    # (embedding is also omitted from column_list above)
    form_excluded_columns = [ChatbotDocument.embedding]


class ChatbotConversationAdmin(ModelView, model=ChatbotConversation):
    name = "Chatbot Conversation"
    name_plural = "Chatbot Conversations"
    icon = "fa-solid fa-comments"
    column_list = [
        ChatbotConversation.id,
        ChatbotConversation.user_id,
        ChatbotConversation.created_at,
        ChatbotConversation.summary,
    ]
    column_sortable_list = [ChatbotConversation.created_at]


class ChatbotUsageLimitAdmin(ModelView, model=ChatbotUsageLimit):
    name = "Chatbot Usage Limit"
    name_plural = "Chatbot Usage Limits"
    icon = "fa-solid fa-gauge"
    column_list = [
        ChatbotUsageLimit.user_id,
        ChatbotUsageLimit.date,
        ChatbotUsageLimit.request_count,
        ChatbotUsageLimit.token_count,
    ]
    column_sortable_list = [ChatbotUsageLimit.date, ChatbotUsageLimit.request_count]
