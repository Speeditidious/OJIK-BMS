"""Issue domain services: reference extraction and persistence helpers."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ISSUE_REF_RE = re.compile(r"(?<![\w])#([1-9][0-9]{0,9})(?![\w])")
USER_MENTION_RE = re.compile(r"(?<![.\w@])@([\w]+(?:[._-][\w]+)*)")


@dataclass(frozen=True)
class UserMentionToken:
    """A user mention token as written, plus its normalized lookup key."""

    username: str
    source_text: str


def extract_issue_reference_numbers(text: str) -> list[int]:
    """Return unique issue numbers referenced by #123 tokens, preserving first-appearance order."""
    seen: set[int] = set()
    refs: list[int] = []
    for match in ISSUE_REF_RE.finditer(text):
        number = int(match.group(1))
        if number not in seen:
            seen.add(number)
            refs.append(number)
    return refs


def extract_user_mention_tokens(text: str) -> list[UserMentionToken]:
    """Return unique user mention tokens with lower-cased usernames for lookup."""
    seen: set[str] = set()
    mentions: list[UserMentionToken] = []
    for match in USER_MENTION_RE.finditer(text):
        username = match.group(1).lower()
        if username not in seen:
            seen.add(username)
            mentions.append(UserMentionToken(username=username, source_text=match.group(0)))
    return mentions


def extract_mentioned_usernames(text: str) -> list[str]:
    """Return unique lower-cased usernames referenced by @username tokens."""
    return [mention.username for mention in extract_user_mention_tokens(text)]



async def persist_issue_references(
    db: AsyncSession,
    *,
    issue_id: int,
    issue_title: str,
    comment_id: uuid.UUID | None,
    body: str,
    actor_user_id: uuid.UUID,
    actor_username: str,
    send_notifications: bool = True,
) -> None:
    """Resolve and store user/issue references from a body, then optionally notify mentioned users."""
    from app.models.issue import IssueIssueReference, IssueUserMention
    from app.models.user import User
    from app.services.notifications import create_issue_mention_notification

    mention_tokens = extract_user_mention_tokens(body)
    usernames = [mention.username for mention in mention_tokens]
    source_text_by_username = {mention.username: mention.source_text for mention in mention_tokens}
    issue_numbers = extract_issue_reference_numbers(body)

    # Resolve users in one query
    if usernames:
        result = await db.execute(
            select(User).where(func.lower(User.username).in_(usernames))
        )
        resolved_users = result.scalars().all()
    else:
        resolved_users = []

    # Resolve issue IDs in one query
    from app.models.issue import Issue as IssueModel
    if issue_numbers:
        result = await db.execute(
            select(IssueModel.id).where(IssueModel.id.in_(issue_numbers))
        )
        resolved_issue_ids = [row[0] for row in result.all()]
    else:
        resolved_issue_ids = []

    # Store user mention rows (ignore duplicates via try/except or merge pattern)
    for user in resolved_users:
        mention = IssueUserMention(
            issue_id=issue_id,
            comment_id=comment_id,
            mentioned_user_id=user.id,
            source_text=source_text_by_username.get(user.username.lower(), f"@{user.username}"),
        )
        db.add(mention)

    # Store issue reference rows
    for target_id in resolved_issue_ids:
        if target_id != issue_id or comment_id is not None:
            ref = IssueIssueReference(
                source_issue_id=issue_id,
                source_comment_id=comment_id,
                target_issue_id=target_id,
                source_text=f"#{target_id}",
            )
            db.add(ref)

    # Flush to persist references before sending notifications
    await db.flush()

    if send_notifications:
        # Create mention notifications for other users
        for user in resolved_users:
            if user.id != actor_user_id:
                await create_issue_mention_notification(
                    db,
                    issue_id=issue_id,
                    issue_title=issue_title,
                    mentioned_user_id=user.id,
                    actor_username=actor_username,
                    comment_id=comment_id,
                )


async def replace_issue_references(
    db: AsyncSession,
    *,
    issue_id: int,
    issue_title: str,
    comment_id: uuid.UUID | None,
    body: str,
    actor_user_id: uuid.UUID,
    actor_username: str,
) -> None:
    """Delete existing mentions/refs for a body, then re-persist without notifications. Use for edits."""
    from app.models.issue import IssueIssueReference, IssueUserMention
    from sqlalchemy import delete

    if comment_id is None:
        await db.execute(
            delete(IssueUserMention).where(
                IssueUserMention.issue_id == issue_id,
                IssueUserMention.comment_id.is_(None),
            )
        )
        await db.execute(
            delete(IssueIssueReference).where(
                IssueIssueReference.source_issue_id == issue_id,
                IssueIssueReference.source_comment_id.is_(None),
            )
        )
    else:
        await db.execute(
            delete(IssueUserMention).where(
                IssueUserMention.issue_id == issue_id,
                IssueUserMention.comment_id == comment_id,
            )
        )
        await db.execute(
            delete(IssueIssueReference).where(
                IssueIssueReference.source_issue_id == issue_id,
                IssueIssueReference.source_comment_id == comment_id,
            )
        )

    await persist_issue_references(
        db,
        issue_id=issue_id,
        issue_title=issue_title,
        comment_id=comment_id,
        body=body,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        send_notifications=False,
    )
