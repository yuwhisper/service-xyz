from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from server.yingdao import client as yd
from server.yingdao.client import YingdaoHttpError

router = APIRouter(prefix="/service/zyx/yingdao", tags=["yingdao"])


class JobStartBody(BaseModel):
    robotUuid: str = Field(..., description="应用/机器人 UUID")
    accountName: str | None = Field(default=None, description="执行账号名（与分组二选一）")
    robotClientGroupUuid: str | None = Field(default=None, description="机器人分组 UUID（与账号二选一）")
    params: list[dict] | None = Field(default=None, description="应用入参列表，每项含 name/value")
    waitTimeoutSeconds: int | None = Field(default=600, description="排队等待超时（秒）")
    runTimeout: int | None = Field(default=None, description="运行超时（秒），不传则不限制")
    priority: str | None = Field(default="middle", description="优先级：high / middle / low")
    executeScope: str | None = Field(default="any", description="分组执行范围：any / all")
    useIdempotent: bool = Field(default=True, description="是否生成幂等 UUID")

    @field_validator("robotUuid")
    @classmethod
    def _strip_robot_uuid(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("robotUuid 不能为空")
        return text


class JobQueryBody(BaseModel):
    jobUuid: str = Field(..., description="任务 UUID（启动接口返回）")

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
            account_name=(body.accountName or "").strip(),
            robot_client_group_uuid=(body.robotClientGroupUuid or "").strip(),
            params=body.params,
            wait_timeout_seconds=body.waitTimeoutSeconds if body.waitTimeoutSeconds is not None else 600,
            run_timeout=body.runTimeout,
            priority=(body.priority or "middle"),
            execute_scope=(body.executeScope or "any"),
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
