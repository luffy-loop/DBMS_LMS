import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

environment = os.getenv("ENVIRONMENT", "development").lower()
key = os.getenv("JWT_SECRET")
if not key:
    if environment == "production":
        raise RuntimeError("JWT_SECRET must be configured in production")
    key = "lms-dev-secret-key"
alg = "HS256"

security = HTTPBearer(auto_error=False)

def get_user(creds: HTTPAuthorizationCredentials | None = Depends(security)):
    try:
        if not creds:
            raise HTTPException(status_code=401, detail="Authorization token required")
        data = jwt.decode(creds.credentials, key, algorithms=[alg])
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")