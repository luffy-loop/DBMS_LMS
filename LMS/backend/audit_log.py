import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from auth import get_user
from database import get_db
from models import AuditLog, User

router = APIRouter(prefix="/admin/audit-logs", tags=["audit"])

def record_audit(db: Session, user_id, action, entity_type=None, entity_id=None, details=None):
    try:
        payload = json.dumps(details, separators=(",", ":")) if isinstance(details, (dict, list)) else (str(details)[:2000] if details is not None else None)
        db.add(AuditLog(user_id=int(user_id) if user_id is not None else None, action=action[:80], entity_type=entity_type[:40] if entity_type else None, entity_id=str(entity_id)[:100] if entity_id is not None else None, details=payload, created_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()

@router.get("")
def list_audit_logs(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), action: str | None = None, user_id: int | None = None, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    query = db.query(AuditLog, User.name).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"logs": [{"id": log.id, "user_id": log.user_id, "user_name": name, "action": log.action, "entity_type": log.entity_type, "entity_id": log.entity_id, "details": log.details, "created_at": log.created_at.isoformat()} for log, name in rows], "page": page, "page_size": page_size}
