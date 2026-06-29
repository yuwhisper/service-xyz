import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from pydantic import BaseModel, Field

from server.database import execute_insert, execute_one
from server.ozon.fahuo_runner import run_fahuo

router = APIRouter(prefix="/service/zyx/ozon", tags=["ozon"])

FAHUO_API_PATH = "/service/zyx/ozon/fahuo"

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

_RESULT_KEYS = (
    "run_status",
    "executed",
    "reason",
    "success",
    "failed",
    "dingpan_uploads",
)


class FahuoBody(BaseModel):
    wait: bool = Field(
        default=False,
        description="true=同步等待完成并返回 success/failed；false=异步返回 job_id",
    )
    resume_cargoes: bool = False
    shop: str | None = None
    batch: str | None = None
    order_id: int | None = None
    supply_id: int | None = None
    supply_ids: str | None = None
    all_supplies: bool = False
    ship_date: str | None = Field(
        default=None,
        description="运营发货日期 YYYY-MM-DD，默认今天",
    )
    drop_off_warehouse_name: str | None = None
    upload_to_dingpan: bool = True
    dingpan_folder_url: str | None = Field(
        default=None,
        description="钉盘文件夹链接，不传则用 DINGTALK_DEFAULT_FOLDER_URL",
    )


def _runner_params(body: FahuoBody) -> dict[str, Any]:
    params = body.model_dump(exclude_none=True)
    params.pop("wait", None)
    return params


def _set_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        entry = _jobs.setdefault(job_id, {"job_id": job_id})
        entry.update(kwargs)
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _run_job(job_id: str, params: dict) -> None:
    try:
        result = run_fahuo(params)
        _set_job(job_id, status="done", job_status="done", **result)
    except Exception as e:
        _set_job(
            job_id,
            status="failed",
            job_status="failed",
            error=str(e),
            run_status="failed",
            executed=True,
            reason=str(e),
            success=[],
            failed=[],
        )


def _format_job_data(job: dict) -> dict[str, Any]:
    data: dict[str, Any] = {"job_id": job.get("job_id")}
    job_status = job.get("job_status") or job.get("status", "unknown")
    data["job_status"] = job_status

    if job_status == "running":
        return data

    if job_status == "failed":
        data["error"] = job.get("error")
        data["run_status"] = job.get("run_status", "failed")
        data["executed"] = job.get("executed", True)
        data["reason"] = job.get("reason") or job.get("error")
        data["success"] = job.get("success", [])
        data["failed"] = job.get("failed", [])
        return data

    for key in _RESULT_KEYS:
        if key in job:
            data[key] = job[key]
    if "result" in job and isinstance(job["result"], dict):
        for key in _RESULT_KEYS:
            if key in job["result"] and key not in data:
                data[key] = job["result"][key]
    if "updated_at" in job:
        data["updated_at"] = job["updated_at"]
    return data


async def _log_fahuo_call(request_params: dict, response_body: str, status_code: int) -> None:
    row = await execute_one(
        "SELECT id FROM interfaces WHERE path=%s LIMIT 1",
        (FAHUO_API_PATH,),
    )
    if not row:
        return
    await execute_insert(
        "INSERT INTO api_logs (api_id, request_params, response_body, status_code, "
        "duration_ms, triggered_by) VALUES (%s,%s,%s,%s,%s,'manual')",
        (row["id"], json.dumps(request_params, ensure_ascii=False), response_body[:5000], status_code, 0),
    )


@router.post("/fahuo")
async def start_fahuo(
    background_tasks: BackgroundTasks,
    body: FahuoBody = Body(default_factory=FahuoBody),
):
    params = _runner_params(body)
    job_id = str(uuid.uuid4())

    if body.wait:
        result = await asyncio.to_thread(run_fahuo, params)
        data = {"job_id": job_id, "job_status": "done", **result}
        resp = {"code": 0, "data": data}
        await _log_fahuo_call(
            {**params, "wait": True},
            json.dumps(resp, ensure_ascii=False),
            200,
        )
        return resp

    _set_job(job_id, status="running", job_status="running", params=params)
    background_tasks.add_task(_run_job, job_id, params)
    resp = {"code": 0, "data": {"job_id": job_id, "job_status": "running"}}
    await _log_fahuo_call(params, json.dumps(resp, ensure_ascii=False), 200)
    return resp


@router.get("/fahuo/status/{job_id}")
async def fahuo_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"code": 0, "data": _format_job_data(job)}
