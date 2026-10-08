from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_user
from database import get_db
from models import Notification, User
from notification_service import notify_users

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SystemNotificationCreate(BaseModel):
    title: str
    message: str
    user_ids: list[int] | None = None


@router.get("")
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == user["id"])
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user["id"], Notification.read_at.is_(None))
        .scalar()
        or 0
    )
    return {
        "notifications": [
            {
                "id": item.id,
                "type": item.notification_type,
                "title": item.title,
                "message": item.message,
                "read": item.read_at is not None,
                "created_at": item.created_at.isoformat(),
            }
            for item in rows
        ],
        "unread_count": unread_count,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user["id"])
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    if item.read_at is None:
        item.read_at = datetime.now()
        db.commit()
    return {"message": "Notification marked as read", "id": item.id}


@router.post("/system")
def create_system_notification(
    data: SystemNotificationCreate,
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    title = data.title.strip()
    message = data.message.strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="Notification title and message are required")
    if data.user_ids is None:
        recipient_ids = [row[0] for row in db.query(User.id).all()]
    else:
        recipient_ids = list(dict.fromkeys(data.user_ids))
        if recipient_ids:
            existing = {row[0] for row in db.query(User.id).filter(User.id.in_(recipient_ids)).all()}
            if existing != set(recipient_ids):
                raise HTTPException(status_code=400, detail="One or more notification recipients do not exist")
    count = notify_users(db, recipient_ids, "system", title, message)
    return {"message": "System notification created", "recipients": count}
