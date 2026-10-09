import logging
from datetime import datetime
from models import Notification

logger = logging.getLogger("lms.notifications")


def notify_users(db, user_ids, notification_type, title, message, entity_type=None, entity_id=None):
    ids = list(dict.fromkeys(int(user_id) for user_id in user_ids if user_id is not None))
    if not ids:
        return 0
    try:
        existing = set()
        if entity_type is not None and entity_id is not None:
            existing = {
                row.user_id
                for row in db.query(Notification)
                .filter(
                    Notification.user_id.in_(ids),
                    Notification.notification_type == notification_type,
                    Notification.entity_type == entity_type,
                    Notification.entity_id == str(entity_id),
                )
                .all()
            }
        rows = [
            Notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title[:200],
                message=message[:1000],
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                created_at=datetime.utcnow(),
            )
            for user_id in ids
            if user_id not in existing
        ]
        if rows:
            db.add_all(rows)
            db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        logger.exception("Notification delivery failed")
        return 0
