from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from server.yingdao import client as yd
from server.yingdao.client import YingdaoHttpError

router = APIRouter(prefix="/service/zyx/yingdao", tags=["yingdao"])


class JobStartBody(BaseModel):
    robotUuid: str = Field(...)
    accountName: str | None = None
    robotClientGroupUuid: str | None = None
    params: list[dict] | None = None
    waitTimeoutSeconds: int | None = 600
    runTimeout: int | None = None
    priority: str | None = "middle"
    executeScope: str | None = "any"
    useIdempotent: bool = True

    @field_validator("robotUuid")
    @classmethod
    def _strip_robot_uuid(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("robotUuid 不能为空")
        return text


class JobQueryBody(BaseModel):
    jobUuid: str = Field(...)

    @field_validator("jobUuid")
    @classmethod
    def _strip_job_uuid(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("jobUuid 不能为空")
        return text


def _raise_yd(e: YingdaoHttpError):
    hint = yd.http_status_hint(e.status_code)
    raise HTTPException(
        e.status_code if e.status_code in (400, 401, 429, 500) else 502,
        detail={"hint": hint, "yingdao_status": e.status_code, "body": e.body},
    ) from e


@router.post("/job/start")
async def job_start(body: JobStartBody):
    try:
        result = yd.start_job(
            robot_uuid=body.robotUuid,
            account_name=(body.accountName or "").strip() or None,
            robot_client_group_uuid=(body.robotClientGroupUuid or "").strip() or None,
            params=body.params,
            wait_timeout_seconds=body.waitTimeoutSeconds,
            run_timeout=body.runTimeout,
            priority=body.priority,
            execute_scope=body.executeScope,
            use_idempotent=body.useIdempotent,
        )
        data = result.get("data") if isinstance(result, dict) else result
        return {"code": 0, "data": data if data is not None else result}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except YingdaoHttpError as e:
        _raise_yd(e)
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.post("/job/query")
async def job_query(body: JobQueryBody):
    try:
        result = yd.query_job(body.jobUuid)
        data = result.get("data") if isinstance(result, dict) else result
        return {"code": 0, "data": data if data is not None else result}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except YingdaoHttpError as e:
        _raise_yd(e)
    except Exception as e:
        raise HTTPException(500, str(e)) from e
