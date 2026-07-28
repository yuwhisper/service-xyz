"""DingTalk AI Table (notable) — insert records."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import requests

from server.dingtalk.config import APP_KEY, APP_SECRET

os.environ.setdefault("NO_PROXY", "*")


class DingTalkNotableWriter:
    def __init__(self, app_key: str = APP_KEY, app_secret: str = APP_SECRET):
        if not app_key or not app_secret:
            raise ValueError("钉钉凭证未配置（DINGTALK_APP_KEY/SECRET）")
        self.app_key = app_key
        self.app_secret = app_secret
        self._access_token: str | None = None
        self._operator_cache: dict[str, str] = {}

    def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        resp = requests.get(
            "https://oapi.dingtalk.com/gettoken",
            params={"appkey": self.app_key, "appsecret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取 access_token 失败: {data}")

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"access_token 为空: {data}")

        self._access_token = token
        return token

    def get_operator_id(self, user_id: str) -> str:
        uid = (user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        cached = self._operator_cache.get(uid)
        if cached:
            return cached

        resp = requests.post(
            "https://oapi.dingtalk.com/topapi/v2/user/get",
            params={"access_token": self.get_access_token()},
            json={"userid": uid, "language": "zh_CN"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"查询用户详情失败: {data}")

        result = data.get("result") or {}
        union_id = result.get("unionid")
        if not union_id:
            raise RuntimeError(f"用户详情中无 unionid: {data}")

        self._operator_cache[uid] = union_id
        return union_id

    def insert_records(
        self,
        *,
        user_id: str,
        base_id: str,
        sheet_id: str,
        records: list[dict[str, Any]],
        client_token: str | None = None,
    ) -> dict[str, Any]:
        bid = (base_id or "").strip()
        sid = (sheet_id or "").strip()
        if not bid:
            raise ValueError("base_id 不能为空")
        if not sid:
            raise ValueError("sheet_id 不能为空")
        if not records:
            raise ValueError("records 不能为空")

        payload_records: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                raise ValueError(f"记录必须是字典: {item!r}")
            if "fields" in item and isinstance(item["fields"], dict):
                payload_records.append({"fields": item["fields"]})
            else:
                payload_records.append({"fields": item})

        operator_id = self.get_operator_id(user_id)
        url = (
            f"https://api.dingtalk.com/v1.0/notable/bases/"
            f"{quote(str(bid), safe='')}/sheets/{quote(str(sid), safe='')}/records"
        )
        resp = requests.post(
            url,
            params={
                "operatorId": operator_id,
                "clientToken": (client_token or str(uuid4())).strip(),
            },
            headers={
                "x-acs-dingtalk-access-token": self.get_access_token(),
                "Content-Type": "application/json",
            },
            json={"records": payload_records},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"写入 AI 多维表失败 [{resp.status_code}]: {resp.text}")
        return resp.json()


def insert_records(
    *,
    user_id: str,
    base_id: str,
    sheet_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Insert one or more records into a DingTalk AI Table sheet."""
    return DingTalkNotableWriter().insert_records(
        user_id=user_id,
        base_id=base_id,
        sheet_id=sheet_id,
        records=records,
    )
