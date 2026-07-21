from fastapi import APIRouter, Query

from server.database import execute_one, execute

router = APIRouter(prefix="/service/zyx/dashboard", tags=["dashboard"])

_ALLOWED_PAGE_SIZES = {20, 50, 100, 200}


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

    return {
        "code": 0,
        "data": {
            "total_apis": total_apis["cnt"] if total_apis else 0,
            "today_calls": today_calls["cnt"] if today_calls else 0,
            "total_logs": total_logs["cnt"] if total_logs else 0,
            "active_schedules": total_schedules["cnt"] if total_schedules else 0,
        },
    }


@router.get("/logs")
async def list_logs(
    keyword: str = Query("", description="按路径或接口名搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
):
    if page_size not in _ALLOWED_PAGE_SIZES:
        page_size = 20

    where = ""
    params: list = []
    kw = (keyword or "").strip()
    if kw:
        where = " WHERE i.name LIKE %s OR i.path LIKE %s"
        like = f"%{kw}%"
        params.extend([like, like])

    total_row = await execute_one(
        "SELECT COUNT(*) AS cnt FROM api_logs al "
        "JOIN interfaces i ON al.api_id=i.id" + where,
        params,
    )
    total = total_row["cnt"] if total_row else 0
    offset = (page - 1) * page_size

    rows = await execute(
        "SELECT al.*, i.name AS api_name, i.method, i.path "
        "FROM api_logs al JOIN interfaces i ON al.api_id=i.id"
        + where
        + " ORDER BY al.created_at DESC LIMIT %s OFFSET %s",
        params + [page_size, offset],
    )

    return {
        "code": 0,
        "data": {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
