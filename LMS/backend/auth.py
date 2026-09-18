import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

key = os.getenv("JWT_SECRET", "lms-dev-secret-key")
alg = "HS256"
security = HTTPBearer()

def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(creds.credentials, key, algorithms=[alg])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
