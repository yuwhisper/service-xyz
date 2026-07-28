"""Jushuitan OpenAPI client — token + SKU/order query."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

import requests

from server.jushuitan.config import (
    ACCESS_TOKEN_PATH,
    APP_KEY,
    APP_SECRET,
    AUTH_CODE,
    INIT_TOKEN_PATH,
    INVENTORY_QUERY_PATH,
    OPENAPI_BASE,
    ORDER_QUERY_PATH,
    REFRESH_TOKEN_PATH,
    SKU_QUERY_BATCH_SIZE,
    SKU_QUERY_PATH,
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
        names = [str(wh.get("name") or "") for wh in warehouses[:30]]
        raise ValueError(f"未找到虚拟仓「{text}」。前若干名称示例: {names}")
    if len(matched) > 1:
        ids = [wh.get("lwh_id") for wh in matched]
        raise ValueError(f"虚拟仓「{text}」匹配到多条: {ids}")

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
