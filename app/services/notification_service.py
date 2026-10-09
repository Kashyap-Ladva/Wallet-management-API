from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification


def list_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    return list(
        db.scalars(
            statement.order_by(Notification.date_created.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def mark_notification_read(
    db: Session,
    user_id: int,
    notification_id: int,
) -> Notification | None:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if notification is None:
        return None
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(notification)
    return notification
