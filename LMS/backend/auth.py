import os
from fastapi import Depends, HTTPException
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

from database import get_db
from models import User


def get_user(creds: HTTPAuthorizationCredentials | None = Depends(security), db: Session = Depends(get_db)):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization token required")
    try:
        data = jwt.decode(creds.credentials, key, algorithms=[alg])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = data.get("id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Invalid token")
    account = db.query(User).filter(User.id == user_id).first()
    if not account:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    if account.role not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Account role is not authorized")
    return {"id": account.id, "role": account.role}
