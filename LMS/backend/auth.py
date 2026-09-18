from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

key = "lms-secret-key"
alg = "HS256"

security = HTTPBearer()

def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = creds.credentials
        data = jwt.decode(token, key, algorithms=[alg])
        return data
    except:
        raise HTTPException(status_code=401, detail="Invalid token")