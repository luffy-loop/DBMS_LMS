import json
import logging
import os
import time
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

environment = os.getenv("ENVIRONMENT", "development").lower()
key = os.getenv("JWT_SECRET")
if not key:
    if environment == "production":
        raise RuntimeError("JWT_SECRET must be configured in production")
    key = "lms-dev-secret-key"
alg = "HS256"

security = HTTPBearer(auto_error=False)
logger = logging.getLogger("lms.auth")

from database import get_db
from models import User


def get_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    request: Request = None,
):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization token required")
    jwt_started = time.perf_counter()
    try:
        data = jwt.decode(creds.credentials, key, algorithms=[alg])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    jwt_ms = round((time.perf_counter() - jwt_started) * 1000, 2)
    user_id = data.get("id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Invalid token")

    timings = {"jwt_verification_ms": jwt_ms}
    status = "database_failure"
    started = time.perf_counter()
    try:
        acquire_started = time.perf_counter()
        try:
            db.connection()
        finally:
            timings["db_connection_acquire_ms"] = round((time.perf_counter() - acquire_started) * 1000, 2)
        query_started = time.perf_counter()
        account = db.query(User).filter(User.id == user_id).first()
        timings["user_query_ms"] = round((time.perf_counter() - query_started) * 1000, 2)
        if not account:
            status = "account_missing"
            raise HTTPException(status_code=401, detail="Account no longer exists")
        if account.role not in {"student", "teacher", "admin"}:
            status = "role_rejected"
            raise HTTPException(status_code=403, detail="Account role is not authorized")
        status = "success"
        return {"id": account.id, "role": account.role}
    finally:
        timings["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        logger.info(json.dumps({
            "event": "auth_dependency_timing",
            "request_id": getattr(getattr(request, "state", None), "request_id", None),
            "path": getattr(request.url, "path", None) if request is not None else None,
            "status": status,
            "timings_ms": timings,
        }, separators=(",", ":")))
