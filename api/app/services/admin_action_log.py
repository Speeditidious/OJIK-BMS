"""Helpers for writing sqladmin action progress logs."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.admin_action_log import AdminActionLog, AdminActionLogLine

FINISHED_STATUSES = frozenset({"success", "failed", "partial"})


async def create_log(
    *,
    action_name: str,
    target_kind: str,
    target_id: str | None = None,
    target_label: str | None = None,
    parent_log_id: uuid.UUID | None = None,
    triggered_by: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Create an admin action log row and return its id."""
    async with AsyncSessionLocal() as db:
        row = AdminActionLog(
            parent_log_id=parent_log_id,
            action_name=action_name,
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
            triggered_by=triggered_by,
            payload=payload,
            status="pending",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id


async def append_line(log_id: uuid.UUID, message: str, level: str = "info") -> None:
    """Append a line and update the parent log's last_message."""
    async with AsyncSessionLocal() as db:
        db.add(AdminActionLogLine(log_id=log_id, level=level, message=message))
        await db.execute(
            update(AdminActionLog)
            .where(AdminActionLog.id == log_id)
            .values(last_message=message)
        )
        await db.commit()


async def set_status(
    log_id: uuid.UUID,
    status: str,
    *,
    error_message: str | None = None,
    celery_task_id: str | None = None,
) -> None:
    """Set the status for one action log."""
    values: dict[str, Any] = {"status": status}
    if error_message is not None:
        values["error_message"] = error_message
    if celery_task_id is not None:
        values["celery_task_id"] = celery_task_id
    if status in FINISHED_STATUSES:
        values["completed_at"] = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        await db.execute(update(AdminActionLog).where(AdminActionLog.id == log_id).values(**values))
        await db.commit()


async def mark_task_id(log_id: uuid.UUID, celery_task_id: str) -> None:
    """Record Celery's task id for an already-created log row."""
    await set_status(log_id, "pending", celery_task_id=celery_task_id)


async def summarize_child_status(parent_log_id: uuid.UUID) -> dict[str, int]:
    """Return child status counts for a parent log."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminActionLog.status).where(AdminActionLog.parent_log_id == parent_log_id)
        )
        counts: dict[str, int] = {}
        for status in result.scalars().all():
            counts[status] = counts.get(status, 0) + 1
        return counts


async def refresh_parent_status(parent_log_id: uuid.UUID) -> None:
    """Update a batch parent log from child statuses."""
    counts = await summarize_child_status(parent_log_id)
    total = sum(counts.values())
    if total == 0:
        return
    finished = sum(counts.get(status, 0) for status in FINISHED_STATUSES)
    if finished < total:
        status = "running"
    elif counts.get("failed", 0):
        status = "partial" if counts.get("success", 0) else "failed"
    else:
        status = "success"
    message = "Child status: " + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    await append_line(parent_log_id, message)
    await set_status(parent_log_id, status)
