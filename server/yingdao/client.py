"""影刀开放 API client — token 缓存 + 启动/查询任务。"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from server.yingdao.config import (
    ACCESS_KEY_ID,
    ACCESS_KEY_SECRET,
    CLIENT_LIST_URL,
    JOB_QUERY_URL,
    JOB_START_URL,
    ROBOT_QUERY_URL,
    SCHEDULE_DETAIL_URL,
    SCHEDULE_LIST_URL,
    TOKEN_URL,
)

DEFAULT_TOKEN_TTL_SECONDS = 50 * 60

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}
_token_lock = threading.Lock()


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
    with _token_lock:
        _token_cache["token"] = ""
        _token_cache["expires_at"] = 0.0


def get_access_token(force: bool = False) -> str:
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        raise ValueError("影刀凭证未配置（YINGDAO_ACCESS_KEY_ID/SECRET）")

    with _token_lock:
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

    with _token_lock:
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + ttl
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
            "robotClientUuid": str(
                row.get("robotClientUuid") or row.get("uuid") or ""
            ).strip(),
            "status": status,
            "statusName": _STATUS_CN.get(status, status or "—"),
            "machineName": str(row.get("machineName") or "").strip(),
        })
    items.sort(key=lambda x: x["accountName"])
    return items


# 定时调度绑定缓存：应用 UUID → 机器人账号列表（仅代表定时任务绑定）
_BINDINGS_TTL_SECONDS = 10 * 60
_bindings_cache: dict[str, Any] = {"expires_at": 0.0, "by_app": {}}
_bindings_lock = threading.Lock()


def _normalize_client(row: dict[str, Any], *, schedule_name: str = "") -> dict[str, Any] | None:
    name = str(
        row.get("robotClientName")
        or row.get("accountName")
        or row.get("name")
        or ""
    ).strip()
    if not name:
        return None
    status = str(row.get("status") or "").strip()
    status_name = str(row.get("statusName") or "").strip() or _STATUS_CN.get(
        status, status or "—"
    )
    return {
        "accountName": name,
        "robotClientUuid": str(row.get("uuid") or row.get("robotClientUuid") or "").strip(),
        "status": status,
        "statusName": status_name,
        "scheduleName": schedule_name,
    }


def _list_all_schedule_uuids() -> list[dict[str, str]]:
    """分页拉取全部定时任务摘要。"""
    page = 1
    size = 50
    out: list[dict[str, str]] = []
    while True:
        result = _request_json(
            "POST",
            SCHEDULE_LIST_URL,
            json_body={"page": page, "size": size},
        )
        raw = result.get("data")
        if not isinstance(raw, list):
            raw = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            su = str(row.get("scheduleUuid") or "").strip()
            if not su:
                continue
            out.append({
                "scheduleUuid": su,
                "scheduleName": str(row.get("scheduleName") or "").strip(),
            })
        page_info = result.get("page") if isinstance(result.get("page"), dict) else {}
        pages = int(page_info.get("pages") or 1)
        if page >= pages or not raw:
            break
        page += 1
    return out


def _fetch_schedule_detail(schedule_uuid: str) -> dict[str, Any] | None:
    try:
        result = _request_json(
            "POST",
            SCHEDULE_DETAIL_URL,
            json_body={"scheduleUuid": schedule_uuid},
        )
    except Exception:
        return None
    data = result.get("data")
    return data if isinstance(data, dict) else None


def _build_schedule_bindings() -> dict[str, list[dict[str, Any]]]:
    """
    扫描全部定时任务详情，构建 应用UUID → 调度机器人 映射。
    同一应用可出现在多个定时任务中；同账号去重。
    """
    schedules = _list_all_schedule_uuids()
    by_app: dict[str, list[dict[str, Any]]] = {}
    seen_pairs: dict[str, set[str]] = {}

    def handle(summary: dict[str, str]) -> None:
        detail = _fetch_schedule_detail(summary["scheduleUuid"])
        if not detail:
            return
        schedule_name = str(
            detail.get("scheduleName") or summary.get("scheduleName") or ""
        ).strip()
        robots = detail.get("robotList") or []
        clients_raw = detail.get("robotClientList") or []
        if not isinstance(robots, list) or not isinstance(clients_raw, list):
            return
        clients: list[dict[str, Any]] = []
        for c in clients_raw:
            if isinstance(c, dict):
                item = _normalize_client(c, schedule_name=schedule_name)
                if item:
                    clients.append(item)
        if not clients:
            return
        for robot in robots:
            if not isinstance(robot, dict):
                continue
            app_uuid = str(robot.get("robotUuid") or robot.get("uuid") or "").strip()
            if not app_uuid:
                continue
            bucket = by_app.setdefault(app_uuid, [])
            seen = seen_pairs.setdefault(app_uuid, set())
            for client in clients:
                key = client["accountName"]
                if key in seen:
                    continue
                seen.add(key)
                bucket.append(dict(client))

    # 并发拉详情，控制并发避免触发限流
    workers = min(8, max(1, len(schedules)))
    if not schedules:
        return {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(handle, s) for s in schedules]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception:
                continue
    return by_app


def get_schedule_bindings(
    *,
    force: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """带 TTL 的应用→调度机器人映射。"""
    now = time.time()
    with _bindings_lock:
        cached = _bindings_cache.get("by_app") or {}
        expires_at = float(_bindings_cache.get("expires_at") or 0.0)
        if not force and cached and expires_at > now:
            return cached

    built = _build_schedule_bindings()
    with _bindings_lock:
        _bindings_cache["by_app"] = built
        _bindings_cache["expires_at"] = time.time() + _BINDINGS_TTL_SECONDS
    return built


def bindings_for_apps(robot_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """按应用 UUID 列表取调度机器人绑定。"""
    if not robot_uuids:
        return {}
    all_map = get_schedule_bindings()
    out: dict[str, list[dict[str, Any]]] = {}
    for uid in robot_uuids:
        key = str(uid or "").strip()
        if not key:
            continue
        out[key] = list(all_map.get(key) or [])
    return out


def _attach_bindings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uuids = [str(x.get("robotUuid") or "").strip() for x in items if x.get("robotUuid")]
    binding_map = bindings_for_apps(uuids)
    for item in items:
        uid = str(item.get("robotUuid") or "").strip()
        clients = binding_map.get(uid) or []
        item["runClients"] = clients
        item["bindStatus"] = "bound" if clients else "unbound"
    return items


def list_apps(
    *,
    key: str = "",
    page: int = 1,
    size: int = 20,
    with_bindings: bool = True,
) -> dict[str, Any]:
    """
    拉取影刀应用列表（GET /oapi/robot/v2/query）。
    key 为应用名称模糊搜索；with_bindings 时附加定时调度机器人。
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
            "runClients": [],
            "bindStatus": "unbound",
        })

    if with_bindings and items:
        items = _attach_bindings(items)

    page_info = result.get("page") if isinstance(result.get("page"), dict) else {}
    return {
        "items": items,
        "page": int(page_info.get("page") or page),
        "size": int(page_info.get("size") or size),
        "total": int(page_info.get("total") or len(items)),
        "pages": int(page_info.get("pages") or 1),
    }


def search_apps(*, key: str, limit: int = 20) -> list[dict[str, Any]]:
    """启动页用：按应用名模糊搜索，附带调度机器人候选。"""
    key_text = (key or "").strip()
    if not key_text:
        return []
    limit = min(50, max(1, int(limit or 20)))
    data = list_apps(key=key_text, page=1, size=limit, with_bindings=True)
    return data.get("items") or []


def get_app_binding(robot_uuid: str) -> dict[str, Any]:
    """单个应用的调度机器人绑定。"""
    uid = (robot_uuid or "").strip()
    if not uid:
        raise ValueError("robotUuid 不能为空")
    clients = bindings_for_apps([uid]).get(uid) or []
    return {
        "robotUuid": uid,
        "runClients": clients,
        "bindStatus": "bound" if clients else "unbound",
    }
