"""Jushuitan OpenAPI client — token + SKU/order query."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime
from typing import Any

import requests

from server.jushuitan.config import (
    ACCESS_TOKEN_PATH,
    APP_KEY,
    APP_SECRET,
    AUTH_CODE,
    INIT_TOKEN_PATH,
    INVENTORY_QUERY_PATH,
    LWH_ALLOCATION_CREATE_PATH,
    LWH_OPERATION_CREATE_PATH,
    OPENAPI_BASE,
    ORDER_QUERY_PATH,
    REFRESH_TOKEN_PATH,
    SKU_QUERY_BATCH_SIZE,
    SKU_QUERY_PATH,
    TOKEN_FILE,
    WAREHOUSE_LIST_PATH,
)
from server.jushuitan.token_store import load_tokens, save_tokens

NO_PROXY = {"http": None, "https": None}

_token_lock = threading.Lock()
_cached_access_token = ""
_cached_refresh_token = ""
_token_expires_at = 0.0


def _load_from_store() -> None:
    global _cached_access_token, _cached_refresh_token, _token_expires_at
    stored = load_tokens()
    _cached_access_token = (stored.get("access_token") or "").strip()
    _cached_refresh_token = (stored.get("refresh_token") or "").strip()
    expires_at = stored.get("expires_at")
    try:
        _token_expires_at = float(expires_at) if expires_at else 0.0
    except (TypeError, ValueError):
        _token_expires_at = 0.0


_load_from_store()


def _sign(params: dict[str, Any]) -> str:
    sign_str = APP_SECRET + "".join(
        f"{k}{params[k]}" for k in sorted(params.keys()) if k != "sign"
    )
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def _post_form(path: str, params: dict[str, Any]) -> dict[str, Any]:
    if not APP_KEY or not APP_SECRET:
        raise ValueError("聚水潭凭证未配置（JUSHUITAN_APP_KEY/SECRET）")
    payload = dict(params)
    payload.setdefault("app_key", APP_KEY)
    payload.setdefault("charset", "utf-8")
    payload.setdefault("timestamp", int(time.time()))
    payload["sign"] = _sign(payload)
    url = OPENAPI_BASE.rstrip("/") + path
    resp = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        proxies=NO_PROXY,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"聚水潭响应格式异常: {data!r}")
    if data.get("code") != 0:
        raise RuntimeError(
            f"聚水潭接口失败 [{data.get('code')}]: {data.get('msg') or data}"
        )
    return data


def _apply_token_response(data: dict[str, Any], source: str) -> dict[str, Any]:
    global _cached_access_token, _cached_refresh_token, _token_expires_at
    token_data = data.get("data") or {}
    access_token = (token_data.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError(f"聚水潭未返回 access_token: {data}")
    refresh_token = (token_data.get("refresh_token") or "").strip()
    expires_in = token_data.get("expires_in")
    _cached_access_token = access_token
    if refresh_token:
        _cached_refresh_token = refresh_token
    if expires_in:
        try:
            _token_expires_at = time.time() + max(int(expires_in) - 300, 60)
        except (TypeError, ValueError):
            _token_expires_at = time.time() + 3600
    else:
        # 未返回 expires_in 时不要按 30 天缓存，避免过期仍被当成有效
        _token_expires_at = time.time() + 3600
    save_tokens(
        access_token=_cached_access_token,
        refresh_token=_cached_refresh_token,
        expires_at=_token_expires_at,
    )
    return _token_payload(source, expires_in=expires_in)


def _token_payload(source: str, expires_in: Any = None) -> dict[str, Any]:
    return {
        "access_token": _cached_access_token,
        "refresh_token": _cached_refresh_token or None,
        "expires_in": expires_in,
        "expires_at": int(_token_expires_at) if _token_expires_at else None,
        "source": source,
    }


def _fetch_init_token(code: str | None = None) -> dict[str, Any]:
    auth_code = (code or AUTH_CODE or "").strip()
    if not auth_code:
        raise ValueError("缺少聚水潭授权 code，无法换取令牌")
    data = _post_form(
        INIT_TOKEN_PATH,
        {
            "grant_type": "authorization_code",
            "code": auth_code,
        },
    )
    return _apply_token_response(data, "init_token")


def _fetch_access_token_by_code(code: str | None = None) -> dict[str, Any]:
    auth_code = (code or AUTH_CODE or "").strip()
    if not auth_code:
        raise ValueError("缺少聚水潭授权 code")
    data = _post_form(
        ACCESS_TOKEN_PATH,
        {
            "grant_type": "authorization_code",
            "code": auth_code,
        },
    )
    return _apply_token_response(data, "access_token")


def _refresh_access_token() -> dict[str, Any]:
    if not _cached_refresh_token:
        raise ValueError("缺少 refresh_token，无法刷新 access_token")
    data = _post_form(
        REFRESH_TOKEN_PATH,
        {
            "grant_type": "refresh_token",
            "refresh_token": _cached_refresh_token,
            "scope": "all",
        },
    )
    return _apply_token_response(data, "refresh_token")


def fetch_token_info(*, force: bool = False, code: str | None = None) -> dict[str, Any]:
    """获取聚水潭 access_token；force=True 时忽略内存缓存重新向 API 换取。"""
    global _cached_access_token, _token_expires_at
    with _token_lock:
        if force:
            _cached_access_token = ""
            _token_expires_at = 0.0

        if not _cached_access_token or not _cached_refresh_token or force:
            _load_from_store()

        if (
            not force
            and _cached_access_token
            and time.time() < _token_expires_at
        ):
            return _token_payload("cached")

        errors: list[str] = []
        if _cached_refresh_token and not code:
            try:
                return _refresh_access_token()
            except Exception as e:
                errors.append(f"refresh: {e}")

        for fetcher in (
            lambda: _fetch_init_token(code),
            lambda: _fetch_access_token_by_code(code),
        ):
            try:
                return fetcher()
            except Exception as e:
                errors.append(str(e))

        raise RuntimeError("获取聚水潭 access_token 失败: " + " | ".join(errors))


def get_access_token(*, force: bool = False) -> str:
    return fetch_token_info(force=force)["access_token"]


def _is_token_invalid_error(exc: BaseException) -> bool:
    text = str(exc)
    return (
        "[100]" in text
        or "access_token" in text.lower()
        or "令牌" in text
        or "认证失败" in text
    )


def _post_biz(path: str, biz_data: dict[str, Any]) -> dict[str, Any]:
    """POST business API with access_token; auto-refresh once on token failure."""
    token = get_access_token()
    params = {
        "access_token": token,
        "timestamp": int(time.time()),
        "version": "2",
        "biz": json.dumps(biz_data, ensure_ascii=False),
    }
    try:
        return _post_form(path, params)
    except RuntimeError as e:
        if not _is_token_invalid_error(e):
            raise
        # 本地缓存未过期但聚水潭已判失效 → 强制换 token 后重试一次
        token = get_access_token(force=True)
        params = {
            "access_token": token,
            "timestamp": int(time.time()),
            "version": "2",
            "biz": json.dumps(biz_data, ensure_ascii=False),
        }
        return _post_form(path, params)


def _fetch_sku_query_datas(sku_ids: list[str]) -> list[dict[str, Any]]:
    """Call /open/sku/query and return raw datas[] items."""
    unique = list(dict.fromkeys(s.strip() for s in sku_ids if s and str(s).strip()))
    if not unique:
        return []

    items: list[dict[str, Any]] = []
    for i in range(0, len(unique), SKU_QUERY_BATCH_SIZE):
        batch = unique[i : i + SKU_QUERY_BATCH_SIZE]
        biz_data = {
            "sku_ids": ",".join(batch),
            "page_index": 1,
            "page_size": max(len(batch), 1),
        }
        data = _post_biz(SKU_QUERY_PATH, biz_data)
        for item in (data.get("data") or {}).get("datas") or []:
            if isinstance(item, dict):
                items.append(item)
    return items


def query_sku_raw(sku_id: str) -> dict[str, Any] | None:
    """Query one SKU; return full raw item from Jushuitan datas[] or None."""
    sku = (sku_id or "").strip()
    if not sku:
        raise ValueError("sku 不能为空")
    items = _fetch_sku_query_datas([sku])
    return items[0] if items else None


def query_skus(sku_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch query SKU details; returns {sku: {image_url, freight_price}}."""
    result: dict[str, dict[str, Any]] = {}
    for item in _fetch_sku_query_datas(sku_ids):
        sku_id = (item.get("sku_id") or item.get("i_id") or "").strip()
        if not sku_id:
            continue
        pic = (item.get("pic") or "").strip()
        price = item.get("other_price_5")
        result[sku_id] = {
            "image_url": pic,
            "freight_price": price,
        }
    return result


def query_order_raw(
    *,
    o_id: str | None = None,
    so_id: str | None = None,
    o_ids: list[Any] | None = None,
    so_ids: list[Any] | None = None,
    shop_id: int | None = None,
    is_offline_shop: bool | None = None,
    modified_begin: str | None = None,
    modified_end: str | None = None,
    date_type: int | None = None,
    status: str | None = None,
    page_index: int | None = None,
    page_size: int | None = None,
    start_ts: int | None = None,
    is_get_total: bool | None = None,
    order_types: list[Any] | None = None,
    archive: bool | None = None,
    is_get_cbfinance: bool | None = True,
    # order_flds（分开传，true 时加入自定义查询字段）
    volume: bool | None = None,
    package: bool | None = None,
    outer_drp_co_id: bool | None = None,
    cus_id: bool | None = None,
    logistics_status: bool | None = None,
    # order_item_flds
    src_combine_sku_qty: bool | None = None,
    referrer_name: bool | None = None,
    presale_date: bool | None = None,
    drp_price: bool | None = None,
    item_plan_delivery_date: bool | None = None,
    activity_u_id: bool | None = None,
    activity_u_name: bool | None = None,
) -> dict[str, Any]:
    """Query orders via /open/orders/single/query; return raw data dict."""
    oid_list = _normalize_str_list(o_ids)
    soid_list = _normalize_str_list(so_ids)
    if o_id and str(o_id).strip():
        oid_list = list(dict.fromkeys(oid_list + [str(o_id).strip()]))
    if so_id and str(so_id).strip():
        soid_list = list(dict.fromkeys(soid_list + [str(so_id).strip()]))

    begin = (modified_begin or "").strip()
    end = (modified_end or "").strip()
    has_time = bool(begin and end)
    has_ts = start_ts is not None

    if not oid_list and not soid_list and not has_time and not has_ts:
        raise ValueError(
            "o_ids/so_ids、modified_begin+modified_end、start_ts 不能同时为空"
        )
    if (begin and not end) or (end and not begin):
        raise ValueError("modified_begin 与 modified_end 必须同时存在")

    biz_data: dict[str, Any] = {}
    if oid_list:
        # 内部单号：尽量转 int（聚水潭文档为 number），失败则保留字符串
        parsed_oids: list[Any] = []
        for x in oid_list:
            try:
                parsed_oids.append(int(x))
            except (TypeError, ValueError):
                parsed_oids.append(x)
        biz_data["o_ids"] = parsed_oids
    if soid_list:
        biz_data["so_ids"] = soid_list
    if shop_id is not None:
        biz_data["shop_id"] = int(shop_id)
    if is_offline_shop is not None:
        biz_data["is_offline_shop"] = bool(is_offline_shop)
    if has_time:
        biz_data["modified_begin"] = begin
        biz_data["modified_end"] = end
    if date_type is not None:
        biz_data["date_type"] = int(date_type)
    if status is not None and str(status).strip():
        biz_data["status"] = str(status).strip()
    if page_index is not None:
        biz_data["page_index"] = int(page_index)
    if page_size is not None:
        biz_data["page_size"] = min(int(page_size), 100)
    if has_ts:
        biz_data["start_ts"] = int(start_ts)
    if is_get_total is not None:
        biz_data["is_get_total"] = bool(is_get_total)
    elif has_ts:
        # 文档：使用 start_ts 时建议传 false
        biz_data["is_get_total"] = False
    if order_types:
        types = _normalize_str_list(order_types)
        if types:
            biz_data["order_types"] = types
    if archive is not None:
        biz_data["archive"] = bool(archive)
    if is_get_cbfinance is not None:
        biz_data["is_get_cbfinance"] = bool(is_get_cbfinance)

    order_flds = [
        name
        for name, flag in (
            ("volume", volume),
            ("package", package),
            ("outer_drp_co_id", outer_drp_co_id),
            ("cus_id", cus_id),
            ("logistics_status", logistics_status),
        )
        if flag
    ]
    if order_flds:
        biz_data["order_flds"] = order_flds

    order_item_flds = [
        name
        for name, flag in (
            ("src_combine_sku_qty", src_combine_sku_qty),
            ("referrer_name", referrer_name),
            ("presale_date", presale_date),
            ("drp_price", drp_price),
            ("item_plan_delivery_date", item_plan_delivery_date),
            ("activity_u_id", activity_u_id),
            ("activity_u_name", activity_u_name),
        )
        if flag
    ]
    if order_item_flds:
        biz_data["order_item_flds"] = order_item_flds

    data = _post_biz(ORDER_QUERY_PATH, biz_data)
    return data.get("data") or {}


def _normalize_str_list(values: list[Any] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for x in values:
        if x is None:
            continue
        text = str(x).strip()
        if text:
            out.append(text)
    return out


def _normalize_wms_co_ids(wms_co_ids: list[Any] | None) -> list[int]:
    """Normalize warehouse ids; empty/None → [0] (all warehouses total)."""
    if not wms_co_ids:
        return [0]
    ids: list[int] = []
    for x in wms_co_ids:
        if x is None or str(x).strip() == "":
            continue
        ids.append(int(x))
    return ids or [0]


def query_inventory_by_sku(
    sku_id: str,
    wms_co_ids: list[Any] | None = None,
    *,
    has_lock_qty: bool = True,
) -> list[dict[str, Any]]:
    """
    Query inventory for one SKU across one or more warehouses.

    Returns a list of raw inventory dicts (each includes wms_co_id).
    Warehouses with no row are omitted.
    Empty wms_co_ids → query all-warehouse total (wms_co_id=0).
    """
    sku = (sku_id or "").strip()
    if not sku:
        raise ValueError("sku 不能为空")

    warehouse_ids = _normalize_wms_co_ids(wms_co_ids)
    results: list[dict[str, Any]] = []

    for wid in warehouse_ids:
        biz_data = {
            "sku_ids": sku,
            "page_index": 1,
            "page_size": 30,
            "has_lock_qty": bool(has_lock_qty),
            "wms_co_id": int(wid),
        }
        data = _post_biz(INVENTORY_QUERY_PATH, biz_data)
        inventorys = (data.get("data") or {}).get("inventorys") or []
        if not inventorys:
            continue
        item = dict(inventorys[0])
        item["wms_co_id"] = int(wid)
        results.append(item)

    return results


def list_lock_warehouses() -> list[dict[str, Any]]:
    """Call getwarehouselist; return list of virtual warehouse dicts."""
    data = _post_biz(WAREHOUSE_LIST_PATH, {})
    warehouses = data.get("data") or []
    if not isinstance(warehouses, list):
        raise RuntimeError(f"虚拟仓列表格式异常: {warehouses!r}")
    return warehouses


def get_lwh_by_name(name: str) -> dict[str, Any]:
    """
    Resolve Chinese virtual warehouse name (exact match on name).
    Returns {lwh_id, bind_wms}. Raises ValueError if empty / not found / duplicate.
    """
    text = (name or "").strip()
    if not text:
        raise ValueError("name 不能为空")

    warehouses = list_lock_warehouses()
    matched = [
        wh for wh in warehouses if str(wh.get("name") or "").strip() == text
    ]
    if not matched:
        raise ValueError(f"未找到虚拟仓「{text}」")
    if len(matched) > 1:
        raise ValueError(f"虚拟仓「{text}」匹配到多条")

    item = matched[0]
    bind_wms = item.get("bind_wms") or []
    if not isinstance(bind_wms, list):
        bind_wms = []
    return {
        "lwh_id": item.get("lwh_id"),
        "bind_wms": bind_wms,
    }


def get_lwh_id_by_name(name: str) -> Any:
    """Backward-compatible: return only lwh_id."""
    return get_lwh_by_name(name)["lwh_id"]


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    try:
        num = float(text)
        if num.is_integer():
            return int(num)
    except (TypeError, ValueError):
        pass
    return None


def _bind_wms_list(warehouse: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not warehouse:
        return []
    binds = warehouse.get("bind_wms") or []
    return binds if isinstance(binds, list) else []


def _resolve_lwh(
    name_or_id: Any,
    warehouses: list[dict[str, Any]],
    *,
    label: str,
    not_found_prefix: str,
) -> tuple[Any, dict[str, Any] | None]:
    if name_or_id is None or str(name_or_id).strip() == "":
        raise ValueError(f"{label}不能为空")

    as_id = _as_int_or_none(name_or_id)
    if as_id is not None:
        for wh in warehouses:
            if wh.get("lwh_id") == as_id or str(wh.get("lwh_id")) == str(as_id):
                return as_id, wh
        raise ValueError(f"{not_found_prefix}「{name_or_id}」")

    name = str(name_or_id).strip()
    matched = [wh for wh in warehouses if str(wh.get("name") or "").strip() == name]
    if not matched:
        raise ValueError(f"{not_found_prefix}「{name}」")
    if len(matched) > 1:
        raise ValueError(f"{label}「{name}」匹配到多条")
    return matched[0].get("lwh_id"), matched[0]


def _resolve_wms_co_id(
    wms_value: Any,
    out_wh: dict[str, Any] | None,
    in_wh: dict[str, Any] | None,
) -> int:
    out_binds = _bind_wms_list(out_wh)
    in_binds = _bind_wms_list(in_wh)
    out_ids = {b.get("wms_co_id") for b in out_binds if b.get("wms_co_id") is not None}
    in_ids = {b.get("wms_co_id") for b in in_binds if b.get("wms_co_id") is not None}
    shared_ids = out_ids & in_ids if in_ids else out_ids
    candidate_binds = [
        b for b in out_binds if b.get("wms_co_id") in shared_ids
    ] or out_binds or in_binds

    if wms_value is None or str(wms_value).strip() == "":
        if len(candidate_binds) == 1:
            return int(candidate_binds[0].get("wms_co_id"))
        raise ValueError("实体仓有多个绑定，请填写 wms（中文名或 id）")

    as_id = _as_int_or_none(wms_value)
    if as_id is not None:
        return int(as_id)

    name = str(wms_value).strip()
    pool = list(out_binds)
    for b in in_binds:
        if b not in pool:
            pool.append(b)
    matched = [b for b in pool if str(b.get("wms_name") or "").strip() == name]
    uniq: dict[Any, dict[str, Any]] = {}
    for b in matched:
        uniq[b.get("wms_co_id")] = b
    matched = list(uniq.values())
    if not matched:
        raise ValueError(f"查不到实体仓「{name}」")
    if len(matched) > 1:
        raise ValueError(f"实体仓「{name}」匹配到多条")
    return int(matched[0].get("wms_co_id"))


def _normalize_allocation_items(raw_items: list[Any] | None) -> list[dict[str, Any]]:
    if not raw_items or not isinstance(raw_items, list):
        raise ValueError("items 为必填数组")
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw_items):
        if not isinstance(row, dict):
            raise ValueError(f"items[{i}] 必须是对象")
        sku_id = str(row.get("sku_id") or "").strip()
        if not sku_id:
            raise ValueError(f"items[{i}].sku_id 为必填")
        item: dict[str, Any] = {"sku_id": sku_id}
        if row.get("qty") is not None and str(row.get("qty")).strip() != "":
            item["qty"] = int(row["qty"])
        sku_sns = row.get("sku_sns")
        if sku_sns:
            if not isinstance(sku_sns, list):
                raise ValueError(f"items[{i}].sku_sns 必须是数组")
            sns: list[dict[str, str]] = []
            for j, sn in enumerate(sku_sns):
                if not isinstance(sn, dict):
                    raise ValueError(f"items[{i}].sku_sns[{j}] 必须是对象")
                sid = str(sn.get("sku_id") or "").strip()
                sn_code = str(sn.get("sku_sn") or "").strip()
                if not sid or not sn_code:
                    raise ValueError(
                        f"items[{i}].sku_sns[{j}] 需同时有 sku_id 与 sku_sn"
                    )
                sns.append({"sku_id": sid, "sku_sn": sn_code})
            item["sku_sns"] = sns
        out.append(item)
    return out


_so_id_lock = threading.Lock()


def next_allocation_so_id() -> str:
    """Generate external so_id: YYYYMMDD + 4-digit daily sequence."""
    today = datetime.now().strftime("%Y%m%d")
    seq_path = os.path.join(os.path.dirname(TOKEN_FILE), ".jst_lwh_so_id_seq.json")
    with _so_id_lock:
        data: dict[str, Any] = {"date": today, "seq": 0}
        if os.path.isfile(seq_path):
            try:
                with open(seq_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and loaded.get("date") == today:
                    data = loaded
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        data["seq"] = int(data.get("seq") or 0) + 1
        data["date"] = today
        os.makedirs(os.path.dirname(seq_path) or ".", exist_ok=True)
        with open(seq_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return f"{today}{int(data['seq']):04d}"


def _available_qty(inv: dict[str, Any] | None) -> float:
    if not inv:
        return 0
    for key in ("orderable", "qty"):
        if inv.get(key) is not None and str(inv.get(key)).strip() != "":
            try:
                return float(inv[key])
            except (TypeError, ValueError):
                continue
    return 0


def create_lwh_allocation(
    *,
    out_lwh: Any,
    in_lwh: Any,
    remark: str,
    items: list[Any],
    wms: Any = None,
    so_id: str | None = None,
    examine: bool = False,
) -> dict[str, Any]:
    """
    Create virtual-warehouse allocation after resolving names and pre-checks.
    Returns {io_id, so_id, out_lwh_id, in_lwh_id, wms_co_id}.
    """
    rem = str(remark or "").strip()
    if not rem:
        raise ValueError("remark 为必填")

    warehouses = list_lock_warehouses()
    out_id, out_wh = _resolve_lwh(
        out_lwh,
        warehouses,
        label="调出云仓",
        not_found_prefix="查不到调出云仓",
    )
    in_id, in_wh = _resolve_lwh(
        in_lwh,
        warehouses,
        label="调入云仓",
        not_found_prefix="查不到调入云仓",
    )
    wms_co_id = _resolve_wms_co_id(wms, out_wh, in_wh)
    item_list = _normalize_allocation_items(items)

    for item in item_list:
        sku_id = item["sku_id"]
        if query_sku_raw(sku_id) is None:
            raise ValueError(f"查不到SKU「{sku_id}」")

    for item in item_list:
        if "qty" not in item:
            continue
        need = int(item["qty"])
        sku_id = item["sku_id"]
        inv_rows = query_inventory_by_sku(sku_id, [wms_co_id], has_lock_qty=True)
        inv = inv_rows[0] if inv_rows else None
        available = _available_qty(inv)
        if available < need:
            raise ValueError(
                f"SKU「{sku_id}」库存不足（可用{available:g}/需要{need}）"
            )

    so = str(so_id or "").strip() or next_allocation_so_id()
    biz_data = {
        "out_lwh_id": int(out_id),
        "in_lwh_id": int(in_id),
        "wms_co_id": int(wms_co_id),
        "so_id": so,
        "remark": rem,
        "items": item_list,
        "examine": bool(examine),
    }

    try:
        result = _post_biz(LWH_ALLOCATION_CREATE_PATH, biz_data)
    except RuntimeError as e:
        raise ValueError(f"创建调拨失败：{e}") from e

    if result.get("code") != 0:
        raise ValueError(
            f"创建调拨失败：[{result.get('code')}] {result.get('msg') or result}"
        )

    data = result.get("data") or {}
    if isinstance(data, dict) and data.get("code") not in (None, 0, "0"):
        raise ValueError(
            f"创建调拨失败：[{data.get('code')}] {data.get('msg') or data}"
        )

    io_id = data.get("io_id") if isinstance(data, dict) else None
    return {
        "io_id": io_id,
        "so_id": so,
        "out_lwh_id": int(out_id),
        "in_lwh_id": int(in_id),
        "wms_co_id": int(wms_co_id),
    }


def next_operation_so_id() -> str:
    """外部单号：当天日期 + 时分秒毫秒。"""
    return datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]


def create_lwh_operation(
    *,
    lwh: Any,
    op_type: str,
    items: list[Any],
    wms: Any = None,
    so_id: str | None = None,
    remark: str | None = None,
    examine: bool = False,
    is_ignore_check_stock: bool | None = None,
) -> dict[str, Any]:
    """
    Create virtual-warehouse allocate/return (lwhoperationcreate).
    Returns {io_id, so_id, lwh_id, wms_co_id, type}.
    """
    type_text = str(op_type or "").strip()
    if type_text not in ("虚拟仓分配", "虚拟仓归还"):
        raise ValueError("type 必须是「虚拟仓分配」或「虚拟仓归还」")

    warehouses = list_lock_warehouses()
    lwh_id, wh = _resolve_lwh(
        lwh,
        warehouses,
        label="虚拟仓",
        not_found_prefix="查不到虚拟仓",
    )
    # 单仓场景：把同一仓作为 out/in 传入，复用实体仓解析
    wms_co_id = _resolve_wms_co_id(wms, wh, wh)
    item_list = _normalize_allocation_items(items)
    so = str(so_id or "").strip() or next_operation_so_id()

    biz_data: dict[str, Any] = {
        "lwh_id": int(lwh_id),
        "wms_co_id": int(wms_co_id),
        "so_id": so,
        "type": type_text,
        "items": item_list,
        "examine": bool(examine),
    }
    rem = str(remark or "").strip()
    if rem:
        biz_data["remark"] = rem
    if is_ignore_check_stock is not None:
        biz_data["isIgnore_check_stock"] = bool(is_ignore_check_stock)

    try:
        result = _post_biz(LWH_OPERATION_CREATE_PATH, biz_data)
    except RuntimeError as e:
        raise ValueError(f"创建失败：{e}") from e

    if result.get("code") != 0:
        raise ValueError(
            f"创建失败：[{result.get('code')}] {result.get('msg') or result}"
        )

    data = result.get("data") or {}
    if isinstance(data, dict) and data.get("code") not in (None, 0, "0"):
        raise ValueError(
            f"创建失败：[{data.get('code')}] {data.get('msg') or data}"
        )

    io_id = data.get("io_id") if isinstance(data, dict) else None
    return {
        "io_id": io_id,
        "so_id": so,
        "lwh_id": int(lwh_id),
        "wms_co_id": int(wms_co_id),
        "type": type_text,
    }
