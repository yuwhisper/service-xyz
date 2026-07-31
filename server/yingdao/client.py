"""影刀开放 API client — token 缓存 + 启动/查询任务。"""
from __future__ import annotations

import time
import uuid
from typing import Any

import requests

from server.yingdao.config import (
    ACCESS_KEY_ID,
    ACCESS_KEY_SECRET,
    CLIENT_LIST_URL,
    JOB_QUERY_URL,
    JOB_START_URL,
    ROBOT_QUERY_URL,
    TOKEN_URL,
)

DEFAULT_TOKEN_TTL_SECONDS = 50 * 60

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


class YingdaoHttpError(Exception):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"影刀 HTTP {status_code}: {body}")


def http_status_hint(code: int) -> str:
    hints = {
        200: "正常",
        401: "接口未授权",
        400: "接口参数校验错误",
        429: "触发接口限流",
        500: "服务内部错误",
    }
    if code in hints:
        return hints[code]
    return f"HTTP {code}，请查阅影刀 API 文档或联系技术支持"


def _clear_token_cache() -> None:
    _token_cache["token"] = ""
    _token_cache["expires_at"] = 0.0


def get_access_token(force: bool = False) -> str:
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        raise ValueError("影刀凭证未配置（YINGDAO_ACCESS_KEY_ID/SECRET）")

    now = time.time()
    cached = (_token_cache.get("token") or "").strip()
    expires_at = float(_token_cache.get("expires_at") or 0.0)
    if not force and cached and expires_at > now:
        return cached

    resp = requests.post(
        TOKEN_URL,
        params={
            "accessKeyId": ACCESS_KEY_ID,
            "accessKeySecret": ACCESS_KEY_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not resp.ok:
        raise YingdaoHttpError(resp.status_code, resp.text)

    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"获取 accessToken 失败: {body}")

    data = body.get("data") or {}
    token = (data.get("accessToken") or "").strip()
    if not token:
        raise RuntimeError(f"响应中无 accessToken: {body}")

    expires_in = data.get("expiresIn") or data.get("expireIn")
    try:
        ttl = int(expires_in) if expires_in else DEFAULT_TOKEN_TTL_SECONDS
    except (TypeError, ValueError):
        ttl = DEFAULT_TOKEN_TTL_SECONDS
    if ttl <= 0:
        ttl = DEFAULT_TOKEN_TTL_SECONDS

    _token_cache["token"] = token
    _token_cache["expires_at"] = now + ttl
    return token


def _filter_params(params: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not params:
        return []
    filtered: list[dict[str, Any]] = []
    for item in params:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        value = item.get("value")
        if not name:
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        filtered.append(item)
    return filtered


def build_start_payload(
    *,
    robot_uuid: str,
    account_name: str,
    robot_client_group_uuid: str,
    params: list[dict[str, Any]] | None,
    wait_timeout_seconds: int,
    run_timeout: int | None,
    priority: str,
    execute_scope: str,
    use_idempotent: bool,
    idempotent_uuid: str | None,
) -> dict[str, Any]:
    use_group = bool((robot_client_group_uuid or "").strip())
    use_account = bool((account_name or "").strip())
    if not use_group and not use_account:
        raise ValueError("请配置账号或机器人分组（二选一）")

    payload: dict[str, Any] = {
        "robotUuid": robot_uuid,
        "priority": priority,
        "waitTimeoutSeconds": wait_timeout_seconds,
    }

    if use_group:
        payload["robotClientGroupUuid"] = robot_client_group_uuid.strip()
        payload["executeScope"] = execute_scope
    else:
        payload["accountName"] = account_name.strip()

    if run_timeout is not None:
        payload["runTimeout"] = run_timeout

    resolved_idempotent = idempotent_uuid
    if use_idempotent and not resolved_idempotent:
        resolved_idempotent = str(uuid.uuid4())
    if resolved_idempotent:
        payload["idempotentUuid"] = resolved_idempotent[:36]

    app_params = _filter_params(params)
    if app_params:
        payload["params"] = app_params

    return payload


def _request_json(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    retry_on_401: bool = True,
) -> dict[str, Any]:
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=60,
    )
    if resp.status_code == 401 and retry_on_401:
        _clear_token_cache()
        token = get_access_token(force=True)
        headers["Authorization"] = f"Bearer {token}"
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=60,
        )

    if not resp.ok:
        try:
            body: Any = resp.json()
        except ValueError:
            body = resp.text
        raise YingdaoHttpError(resp.status_code, body)

    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"影刀响应格式异常: {data}")
    if not data.get("success"):
        raise RuntimeError(f"影刀业务失败: {data}")
    return data


def start_job(
    *,
    robot_uuid: str,
    account_name: str = "",
    robot_client_group_uuid: str = "",
    params: list[dict[str, Any]] | None = None,
    wait_timeout_seconds: int = 600,
    run_timeout: int | None = None,
    priority: str = "middle",
    execute_scope: str = "any",
    use_idempotent: bool = True,
    idempotent_uuid: str | None = None,
) -> dict[str, Any]:
    payload = build_start_payload(
        robot_uuid=robot_uuid,
        account_name=account_name,
        robot_client_group_uuid=robot_client_group_uuid,
        params=params,
        wait_timeout_seconds=wait_timeout_seconds,
        run_timeout=run_timeout,
        priority=priority,
        execute_scope=execute_scope,
        use_idempotent=use_idempotent,
        idempotent_uuid=idempotent_uuid,
    )
    return _request_json("POST", JOB_START_URL, json_body=payload)


def query_job(job_uuid: str) -> dict[str, Any]:
    if not (job_uuid or "").strip():
        raise ValueError("jobUuid 不能为空")
    return _request_json(
        "POST",
        JOB_QUERY_URL,
        json_body={"jobUuid": job_uuid.strip()},
    )


_STATUS_CN = {
    "idle": "空闲",
    "running": "运行中",
    "offline": "离线",
    "connected": "已连接",
    "allocated": "已分配",
    "abnormal": "异常",
}


def list_clients() -> list[dict[str, Any]]:
    """拉取影刀机器人列表，供下拉选择 accountName。"""
    result = _request_json("POST", CLIENT_LIST_URL, json_body={})
    raw = result.get("data")
    if isinstance(raw, dict):
        raw = raw.get("list") or raw.get("items") or raw.get("data") or []
    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = str(
            row.get("robotClientName")
            or row.get("accountName")
            or row.get("name")
            or ""
        ).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        status = str(row.get("status") or "").strip()
        items.append({
            "accountName": name,
            "robotClientUuid": str(row.get("robotClientUuid") or "").strip(),
            "status": status,
            "statusName": _STATUS_CN.get(status, status or "—"),
            "machineName": str(row.get("machineName") or "").strip(),
        })
    items.sort(key=lambda x: x["accountName"])
    return items


def list_apps(
    *,
    key: str = "",
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """
    拉取影刀应用列表（GET /oapi/robot/v2/query）。
    key 为应用名称模糊搜索；运行机器人字段接口不提供。
    """
    page = max(1, int(page or 1))
    size = min(100, max(1, int(size or 20)))
    params: dict[str, Any] = {"page": page, "size": size}
    key_text = (key or "").strip()
    if key_text:
        params["key"] = key_text

    result = _request_json("GET", ROBOT_QUERY_URL, params=params)
    raw = result.get("data")
    if not isinstance(raw, list):
        raw = []

    items: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        items.append({
            "robotName": str(row.get("robotName") or "").strip(),
            "robotUuid": str(row.get("robotUuid") or "").strip(),
            "createTime": str(row.get("createTime") or "").strip(),
            "updateTime": str(row.get("updateTime") or "").strip(),
            "ownerName": str(row.get("ownerName") or "").strip(),
            "ownerUuid": str(row.get("ownerUuid") or "").strip(),
            # 影刀应用列表不返回绑定运行机器人；定时任务详情才有 robotClientList
            "runClients": [],
        })

    page_info = result.get("page") if isinstance(result.get("page"), dict) else {}
    return {
        "items": items,
        "page": int(page_info.get("page") or page),
        "size": int(page_info.get("size") or size),
        "total": int(page_info.get("total") or len(items)),
        "pages": int(page_info.get("pages") or 1),
    }
