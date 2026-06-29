from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from server.jushuitan.client import fetch_token_info

router = APIRouter(prefix="/service/zyx/jst", tags=["jushuitan"])


class GetTokenBody(BaseModel):
    code: str | None = Field(
        default=None,
        description="聚水潭授权 code；不传则用环境变量 JUSHUITAN_AUTH_CODE",
    )
    force: bool = Field(
        default=False,
        description="true=忽略缓存，重新向聚水潭换取 token",
    )


@router.get("/gettoken")
async def get_token_get(
    force: bool = Query(False, description="忽略缓存重新换取"),
    code: str | None = Query(None, description="聚水潭授权 code"),
):
    return _get_token(force=force, code=code)


@router.post("/gettoken")
async def get_token_post(body: GetTokenBody = Body(default_factory=GetTokenBody)):
    return _get_token(force=body.force, code=body.code)


def _get_token(*, force: bool, code: str | None):
    try:
        data = fetch_token_info(force=force, code=code)
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e
