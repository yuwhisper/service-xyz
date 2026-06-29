import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from server.ozon.fahuo_runner import run_fahuo

router = APIRouter(prefix="/service/zyx/ozon", tags=["ozon"])

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class FahuoBody(BaseModel):
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
        _set_job(job_id, status="done", result=result)
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e))


@router.post("/fahuo")
async def start_fahuo(
    body: FahuoBody,
    background_tasks: BackgroundTasks,
):
    job_id = str(uuid.uuid4())
    params = body.model_dump(exclude_none=True)
    _set_job(job_id, status="running", params=params, result=None, error=None)
    background_tasks.add_task(_run_job, job_id, params)
    return {"code": 0, "data": {"job_id": job_id, "status": "running"}}


@router.get("/fahuo/status/{job_id}")
async def fahuo_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"code": 0, "data": job}
