from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import verify_password, create_token, get_current_user
from server.database import execute_one, execute_update

router = APIRouter(prefix="/service/zyx/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginBody):
    user = await execute_one(
        "SELECT * FROM users WHERE username=%s AND status=1",
        (body.username,),
    )
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(401, "Invalid username or password")

    await execute_update("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user["id"],))
    token = create_token(user["id"])

    return {
        "code": 0,
        "data": {
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "role": user["role"],
            },
        },
    }


@router.get("/user/me", tags=["user"])
async def me(user=Depends(get_current_user)):  # noqa: B008
    return {"code": 0, "data": user}
