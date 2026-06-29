from fastapi import APIRouter

from server.database import execute_one, execute

router = APIRouter(prefix="/service/zyx/dashboard", tags=["dashboard"])


@router.get("/stats")
async def stats():
    total_apis = await execute_one("SELECT COUNT(*) AS cnt FROM interfaces WHERE status='published'")
    today_calls = await execute_one(
        "SELECT COUNT(*) AS cnt FROM api_logs WHERE DATE(created_at)=CURDATE()"
    )
    total_logs = await execute_one("SELECT COUNT(*) AS cnt FROM api_logs")
    total_schedules = await execute_one(
        "SELECT COUNT(*) AS cnt FROM schedules WHERE enabled=1"
    )
    recent_logs = await execute(
        "SELECT al.*, i.name AS api_name, i.method, i.path "
        "FROM api_logs al JOIN interfaces i ON al.api_id=i.id "
        "ORDER BY al.created_at DESC LIMIT 10"
    )

    return {
        "code": 0,
        "data": {
            "total_apis": total_apis["cnt"] if total_apis else 0,
            "today_calls": today_calls["cnt"] if today_calls else 0,
            "total_logs": total_logs["cnt"] if total_logs else 0,
            "active_schedules": total_schedules["cnt"] if total_schedules else 0,
            "recent_logs": recent_logs,
        },
    }
