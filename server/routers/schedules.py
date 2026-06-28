from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_current_user
from server.database import execute, execute_one, execute_insert, execute_update

router = APIRouter(prefix="/service/zyx/schedules", tags=["schedules"])


class ScheduleBody(BaseModel):
    api_id: int
    name: str
    cron_expression: str = "0 0 * * *"
    params: str = "{}"
    enabled: int = 1


@router.get("")
async def list_schedules(user=Depends(get_current_user)):  # noqa: B008
    rows = await execute(
        "SELECT s.*, i.name AS api_name, i.method, i.path "
        "FROM schedules s JOIN interfaces i ON s.api_id=i.id "
        "ORDER BY s.created_at DESC"
    )
    return {"code": 0, "data": rows}


@router.post("")
async def create_schedule(body: ScheduleBody, user=Depends(get_current_user)):  # noqa: B008
    sid = await execute_insert(
        "INSERT INTO schedules (api_id,name,cron_expression,params,enabled) VALUES (%s,%s,%s,%s,%s)",
        (body.api_id, body.name, body.cron_expression, body.params, body.enabled),
    )
    row = await execute_one("SELECT * FROM schedules WHERE id=%s", (sid,))
    return {"code": 0, "data": row}


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: int, body: ScheduleBody, user=Depends(get_current_user)):  # noqa: B008
    await execute_update(
        "UPDATE schedules SET api_id=%s,name=%s,cron_expression=%s,params=%s,enabled=%s WHERE id=%s",
        (body.api_id, body.name, body.cron_expression, body.params, body.enabled, schedule_id),
    )
    row = await execute_one("SELECT * FROM schedules WHERE id=%s", (schedule_id,))
    return {"code": 0, "data": row}


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: int, user=Depends(get_current_user)):  # noqa: B008
    await execute_update("DELETE FROM schedules WHERE id=%s", (schedule_id,))
    return {"code": 0, "message": "deleted"}
