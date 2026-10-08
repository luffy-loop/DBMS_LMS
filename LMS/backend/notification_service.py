import logging
from datetime import datetime
from models import Notification

logger = logging.getLogger("lms.notifications")


def notify_users(db, user_ids, notification_type, title, message):
    ids = list(dict.fromkeys(int(user_id) for user_id in user_ids if user_id is not None))
    if not ids:
        return 0
    try:
        db.add_all([
            Notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title[:200],
                message=message[:1000],
                created_at=datetime.now(),
            )
            for user_id in ids
        ])
        db.commit()
        return len(ids)
    except Exception:
        db.rollback()
        logger.exception("Notification delivery failed")
        return 0
