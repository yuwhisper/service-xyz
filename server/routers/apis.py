import asyncio
import json
import os
import time

import aiohttp
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.config import PORT
from server.database import execute, execute_one, execute_insert, execute_update

router = APIRouter(prefix="/service/zyx/apis", tags=["apis"])

INTERNAL_API_BASE = os.getenv("INTERNAL_API_BASE", f"http://127.0.0.1:{PORT}")
FAHUO_STATUS_PATH = "/service/zyx/ozon/fahuo/status"
FAHUO_POLL_INTERVAL_SEC = 2
FAHUO_POLL_TIMEOUT_SEC = 600


async def _wait_fahuo_job_result(session: aiohttp.ClientSession, resp_body: str) -> str:
    try:
        parsed = json.loads(resp_body)
    except json.JSONDecodeError:
        return resp_body
    data = parsed.get("data") or {}
    if data.get("job_status") != "running":
        return resp_body
    job_id = data.get("job_id")
    if not job_id:
        return resp_body

    status_url = INTERNAL_API_BASE.rstrip("/") + f"{FAHUO_STATUS_PATH}/{job_id}"
    deadline = time.time() + FAHUO_POLL_TIMEOUT_SEC
    while time.time() < deadline:
        await asyncio.sleep(FAHUO_POLL_INTERVAL_SEC)
        try:
            async with session.get(status_url) as status_resp:
                body = await status_resp.text()
        except Exception:
            continue
        try:
            status_data = json.loads(body).get("data") or {}
        except json.JSONDecodeError:
            continue
        if status_data.get("job_status") != "running":
            return body
    return resp_body


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
async def get_api(api_id: int):
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    if not row:
        raise HTTPException(404, "API not found")
    return {"code": 0, "data": row}


# --------------- Create ---------------
@router.post("")
async def create_api(body: ApiBody):
    api_id = await execute_insert(
        "INSERT INTO interfaces (project_id,name,description,method,path,body_type,status) VALUES (%s,%s,%s,%s,%s,%s,'published')",
        (body.project_id, body.name, body.description, body.method.upper(), body.path, body.body_type),
    )
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "data": row}


# --------------- Update ---------------
@router.put("/{api_id}")
async def update_api(api_id: int, body: ApiBody):
    await execute_update(
        "UPDATE interfaces SET name=%s,description=%s,method=%s,path=%s,body_type=%s WHERE id=%s",
        (body.name, body.description, body.method.upper(), body.path, body.body_type, api_id),
    )
    row = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "data": row}


# --------------- Delete ---------------
@router.delete("/{api_id}")
async def delete_api(api_id: int):
    await execute_update("DELETE FROM interfaces WHERE id=%s", (api_id,))
    return {"code": 0, "message": "deleted"}


# --------------- Execute ---------------
@router.post("/{api_id}/execute")
async def execute_api(api_id: int, body: ExecuteBody):
    api = await execute_one("SELECT * FROM interfaces WHERE id=%s", (api_id,))
    if not api:
        raise HTTPException(404, "API not found")

    start = time.time()
    url = api["path"]
    if url.startswith("/"):
        url = INTERNAL_API_BASE.rstrip("/") + url
    method = api["method"].upper()
    body_type = (api.get("body_type") or "none").lower()

    req_kwargs = {
        "headers": dict(body.headers or {}),
        "timeout": aiohttp.ClientTimeout(total=300),
    }
    if method in ("GET", "DELETE"):
        req_kwargs["params"] = body.params
    elif body_type == "json":
        req_kwargs["json"] = body.params
    else:
        req_kwargs["params"] = body.params

    is_fahuo = api["path"].rstrip("/").endswith("/ozon/fahuo")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **req_kwargs) as resp:
                resp_body = await resp.text()
                status = resp.status
            if is_fahuo:
                resp_body = await _wait_fahuo_job_result(session, resp_body)
    except Exception as e:
        resp_body = str(e)
        status = 0

    duration = int((time.time() - start) * 1000)

    log_id = None
    if not is_fahuo:
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
async def api_logs(api_id: int):
    rows = await execute(
        "SELECT * FROM api_logs WHERE api_id=%s ORDER BY created_at DESC LIMIT 50",
        (api_id,),
    )
    return {"code": 0, "data": rows}
