import json
import time

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from server.auth import get_current_user
from server.database import execute, execute_one, execute_insert, execute_update

router = APIRouter(prefix="/service/zyx/apis", tags=["apis"])


# --------------- Schema ---------------
class ApiBody(BaseModel):
    project_id: int = 1
    name: str
    description: str = ""
    method: str = "GET"
    path: str = "/"
    body_type: str = "none"


class ExecuteBody(BaseModel):
    params: dict = {}
    headers: dict = {}


# --------------- List ---------------
@router.get("")
async def list_apis(
    project_id: int = Query(1),
    keyword: str = Query(""),
    method: str = Query(""),
    user=Depends(get_current_user),  # noqa: B008
):
    sql = "SELECT * FROM interfaces WHERE project_id=%s"
    params = [project_id]
    if keyword:
        sql += " AND (name LIKE %s OR path LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if method:
        sql += " AND method=%s"
        params.append(method.upper())
    sql += " ORDER BY sort_order ASC, created_at DESC"
    rows = await execute(sql, params)
    return {"code": 0, "data": rows}


# --------------- Detail ---------------
@router.get("/{api_id}")
async def get_api(api_id: int, user=Depends(get_current_user)):  # noqa: B008
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    if not row:
        raise HTTPException(404, "API not found")
    return {"code": 0, "data": row}


# --------------- Create ---------------
@router.post("")
async def create_api(body: ApiBody, user=Depends(get_current_user)):  # noqa: B008
    api_id = await execute_insert(
        "INSERT INTO interfaces (project_id,name,description,method,path,body_type,status) VALUES (%s,%s,%s,%s,%s,%s,'published')",
        (body.project_id, body.name, body.description, body.method.upper(), body.path, body.body_type),
    )
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "data": row}


# --------------- Update ---------------
@router.put("/{api_id}")
async def update_api(api_id: int, body: ApiBody, user=Depends(get_current_user)):  # noqa: B008
    await execute_update(
        "UPDATE interfaces SET name=%s,description=%s,method=%s,path=%s,body_type=%s WHERE id=%s",
        (body.name, body.description, body.method.upper(), body.path, body.body_type, api_id),
    )
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "data": row}


# --------------- Delete ---------------
@router.delete("/{api_id}")
async def delete_api(api_id: int, user=Depends(get_current_user)):  # noqa: B008
    await execute_update("DELETE FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "message": "deleted"}


# --------------- Execute ---------------
@router.post("/{api_id}/execute")
async def execute_api(api_id: int, body: ExecuteBody, user=Depends(get_current_user)):  # noqa: B008
    api = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    if not api:
        raise HTTPException(404, "API not found")

    start = time.time()
    url = api["path"]  # full URL or relative; use as-is for now
    method = api["method"].upper()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, params=body.params, headers=body.headers, timeout=30
            ) as resp:
                resp_body = await resp.text()
                status = resp.status
    except Exception as e:
        resp_body = str(e)
        status = 0

    duration = int((time.time() - start) * 1000)

    # Save log
    log_id = await execute_insert(
        "INSERT INTO api_logs (api_id, request_params, response_body, status_code, duration_ms, triggered_by) "
        "VALUES (%s,%s,%s,%s,%s,'manual')",
        (api_id, json.dumps(body.params), resp_body[:5000], status, duration),
    )

    return {
        "code": 0,
        "data": {
            "log_id": log_id,
            "status_code": status,
            "duration_ms": duration,
            "response": resp_body[:2000],
        },
    }


# --------------- Logs ---------------
@router.get("/{api_id}/logs")
async def api_logs(api_id: int, user=Depends(get_current_user)):  # noqa: B008
    rows = await execute(
        "SELECT * FROM api_logs WHERE api_id=%s ORDER BY created_at DESC LIMIT 50",
        (api_id,),
    )
    return {"code": 0, "data": rows}
