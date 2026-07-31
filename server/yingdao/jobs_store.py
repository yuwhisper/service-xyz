"""Persist Yingdao job runs for the backfill console table."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from server.database import execute, execute_insert, execute_one, execute_update

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS yingdao_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_uuid VARCHAR(64) NOT NULL,
    task_name VARCHAR(200) NOT NULL DEFAULT '每日数据补全',
    robot_uuid VARCHAR(64) NOT NULL DEFAULT '',
    account_name VARCHAR(120) NOT NULL DEFAULT '',
    group_uuid VARCHAR(64) NOT NULL DEFAULT '',
    status VARCHAR(40) NOT NULL DEFAULT 'waiting',
    status_name VARCHAR(80) NOT NULL DEFAULT '已提交',
    remark VARCHAR(500) NOT NULL DEFAULT '',
    duration_sec INT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    raw_json MEDIUMTEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_job_uuid (job_uuid),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


async def ensure_table() -> None:
    from server.database import execute as _execute

    await _execute(CREATE_SQL)


def _fmt_dt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)


def row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "jobUuid": row["job_uuid"],
        "taskName": row["task_name"],
        "robotUuid": row.get("robot_uuid") or "",
        "accountName": row.get("account_name") or "",
        "groupUuid": row.get("group_uuid") or "",
        "status": row.get("status") or "",
        "statusName": row.get("status_name") or "",
        "remark": row.get("remark") or "",
        "durationSec": row.get("duration_sec"),
        "startedAt": _fmt_dt(row.get("started_at")),
        "finishedAt": _fmt_dt(row.get("finished_at")),
        "createdAt": _fmt_dt(row.get("created_at")),
        "updatedAt": _fmt_dt(row.get("updated_at")),
    }


async def insert_job(
    *,
    job_uuid: str,
    task_name: str,
    robot_uuid: str,
    account_name: str,
    group_uuid: str,
    remark: str,
    status: str = "waiting",
    status_name: str = "已提交",
    raw: Any = None,
) -> int:
    await ensure_table()
    raw_json = json.dumps(raw, ensure_ascii=False) if raw is not None else None
    return await execute_insert(
        "INSERT INTO yingdao_jobs "
        "(job_uuid, task_name, robot_uuid, account_name, group_uuid, status, status_name, remark, started_at, raw_json) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s) "
        "ON DUPLICATE KEY UPDATE "
        "task_name=VALUES(task_name), status=VALUES(status), status_name=VALUES(status_name), "
        "remark=VALUES(remark), raw_json=VALUES(raw_json), updated_at=NOW()",
        (
            job_uuid,
            task_name,
            robot_uuid,
            account_name,
            group_uuid,
            status,
            status_name,
            remark,
            raw_json,
        ),
    )


async def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    await ensure_table()
    limit = max(1, min(int(limit or 50), 200))
    rows = await execute(
        "SELECT * FROM yingdao_jobs ORDER BY id DESC LIMIT %s",
        (limit,),
    )
    return [row_to_item(r) for r in rows]


async def get_by_uuid(job_uuid: str) -> dict[str, Any] | None:
    await ensure_table()
    row = await execute_one(
        "SELECT * FROM yingdao_jobs WHERE job_uuid=%s",
        (job_uuid,),
    )
    return row_to_item(row) if row else None


_DONE = frozenset({"finish", "finished", "error", "failed", "cancel", "cancelled", "stopped"})


async def update_from_query(job_uuid: str, data: dict[str, Any]) -> dict[str, Any] | None:
    await ensure_table()
    status = str(data.get("status") or "").strip()
    status_name = str(data.get("statusName") or data.get("status_name") or "").strip()
    # 影刀 robotName = 应用名称 → 写入任务名称；备注保留启动时的日期参数，不再被覆盖
    robot_name = str(data.get("robotName") or data.get("robot_name") or "").strip()
    raw_json = json.dumps(data, ensure_ascii=False)

    row = await execute_one("SELECT * FROM yingdao_jobs WHERE job_uuid=%s", (job_uuid,))
    if not row:
        return None

    finished = status.lower() in _DONE
    # 历史数据：备注曾被误写成应用名，与 robotName 相同时清空，避免和应用名重复
    bad_remark = bool(
        robot_name and str(row.get("remark") or "").strip() == robot_name
    )
    if finished and row.get("started_at") and not row.get("finished_at"):
        await execute_update(
            "UPDATE yingdao_jobs SET status=%s, status_name=%s, "
            "task_name=IF(%s='', task_name, %s), "
            "remark=IF(%s, '', remark), "
            "raw_json=%s, finished_at=NOW(), "
            "duration_sec=TIMESTAMPDIFF(SECOND, COALESCE(started_at, created_at), NOW()), "
            "updated_at=NOW() WHERE job_uuid=%s",
            (
                status or row["status"],
                status_name or row["status_name"],
                robot_name,
                robot_name,
                1 if bad_remark else 0,
                raw_json,
                job_uuid,
            ),
        )
    else:
        await execute_update(
            "UPDATE yingdao_jobs SET status=%s, status_name=%s, "
            "task_name=IF(%s='', task_name, %s), "
            "remark=IF(%s, '', remark), "
            "raw_json=%s, updated_at=NOW() WHERE job_uuid=%s",
            (
                status or row["status"],
                status_name or row["status_name"],
                robot_name,
                robot_name,
                1 if bad_remark else 0,
                raw_json,
                job_uuid,
            ),
        )
    return await get_by_uuid(job_uuid)
