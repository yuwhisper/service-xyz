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
    OPENAPI_BASE,
    ORDER_QUERY_PATH,
    REFRESH_TOKEN_PATH,
    SKU_QUERY_BATCH_SIZE,
    SKU_QUERY_PATH,
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
        _token_expires_at = time.time() + 86400 * 30
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


def get_access_token() -> str:
    return fetch_token_info()["access_token"]


def _fetch_sku_query_datas(sku_ids: list[str]) -> list[dict[str, Any]]:
    """Call /open/sku/query and return raw datas[] items."""
    unique = list(dict.fromkeys(s.strip() for s in sku_ids if s and str(s).strip()))
    if not unique:
        return []

    items: list[dict[str, Any]] = []
    token = get_access_token()
    for i in range(0, len(unique), SKU_QUERY_BATCH_SIZE):
        batch = unique[i : i + SKU_QUERY_BATCH_SIZE]
        biz_data = {
            "sku_ids": ",".join(batch),
            "page_index": 1,
            "page_size": max(len(batch), 1),
        }
        params = {
            "access_token": token,
            "timestamp": int(time.time()),
            "version": "2",
            "biz": json.dumps(biz_data, ensure_ascii=False),
        }
        data = _post_form(SKU_QUERY_PATH, params)
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
) -> dict[str, Any]:
    """Query one order via /open/orders/single/query; return raw data dict."""
    o_text = (o_id or "").strip()
    so_text = (so_id or "").strip()
    if o_text:
        biz_data: dict[str, Any] = {"o_ids": [o_text], "is_get_cbfinance": True}
    elif so_text:
        biz_data = {"so_ids": [so_text], "is_get_cbfinance": True}
    else:
        raise ValueError("o_id 或 so_id 至少传一个")

    params = {
        "access_token": get_access_token(),
        "timestamp": int(time.time()),
        "version": "2",
        "biz": json.dumps(biz_data, ensure_ascii=False),
    }
    data = _post_form(ORDER_QUERY_PATH, params)
    return data.get("data") or {}
