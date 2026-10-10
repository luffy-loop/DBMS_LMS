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


def _notification_href(item, user):
    if item.entity_type == "assignment" and item.entity_id:
        if item.notification_type == "submission_received" and user.get("role") in {"teacher", "admin"}:
            return "/marks?assignment_id=" + str(item.entity_id)
        if item.notification_type == "marks_published":
            return "/marks"
        return "/assignments?assignment_id=" + str(item.entity_id)
    if item.entity_type in {"resource", "course"}:
        return "/courses"
    return None

def _ensure_deadline_notifications(user_id, db):
    if not user_id:
        return
    from datetime import timedelta
    from models import Assignment, Enrollment, Submission
    now = datetime.now()
    horizon = now + timedelta(hours=24)
    try:
        rows = db.query(Assignment).join(Enrollment, Enrollment.course_id == Assignment.course_id).filter(Enrollment.student_id == user_id).all()
    except Exception:
        db.rollback()
        return
    existing = {row.entity_id for row in db.query(Notification).filter(Notification.user_id == user_id, Notification.notification_type == "deadline_approaching", Notification.entity_type == "assignment").all()}
    created = False
    for assignment in rows:
        deadline = assignment.end_time
        if assignment.start_time and assignment.duration_minutes:
            derived = assignment.start_time + timedelta(minutes=assignment.duration_minutes)
            deadline = min([x for x in [deadline, derived] if x is not None], default=None)
        if not deadline or not (now < deadline <= horizon):
            continue
        if db.query(Submission.id).filter(Submission.assignment_id == assignment.id, Submission.student_id == user_id).first():
            continue
        if str(assignment.id) not in existing:
            db.add(Notification(user_id=user_id, notification_type="deadline_approaching", title="Deadline approaching", message=f"{assignment.title} is due within 24 hours.", created_at=datetime.utcnow(), entity_type="assignment", entity_id=str(assignment.id)))
            created = True
    if created:
        db.commit()



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
    _ensure_deadline_notifications(user["id"], db)
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
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "href": _notification_href(item, user),
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



@router.patch("/read-all")
def mark_all_notifications_read(
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user["id"], Notification.read_at.is_(None))
        .update({Notification.read_at: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    return {"message": "Notifications marked as read", "count": count}


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
