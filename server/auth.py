import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from server.config import JWT_SECRET, JWT_EXPIRES
from server.database import execute_one

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha512", password.encode(), salt.encode(), 1000)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, dk_hex = stored.split(":")
    dk = hashlib.pbkdf2_hmac("sha512", password.encode(), salt.encode(), 1000)
    return dk.hex() == dk_hex


def create_token(user_id: int) -> str:
    payload = {
        "uid": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_EXPIRES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user(
    req: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await execute_one(
            "SELECT id, email, username, role, status FROM users WHERE id=%s",
            (payload["uid"],),
        )
        if not user or user["status"] != 1:
            raise HTTPException(401, "Invalid user")
        return dict(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
