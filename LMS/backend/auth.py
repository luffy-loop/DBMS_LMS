import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

key = os.getenv("JWT_SECRET", "lms-dev-secret-key")
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