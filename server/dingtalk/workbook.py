"""DingTalk online workbook — read sheet props / update cell ranges."""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import requests

from server.dingtalk.config import APP_KEY, APP_SECRET

os.environ.setdefault("NO_PROXY", "*")


def _col_to_index(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _index_to_col(n: int) -> str:
    chars: list[str] = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def expand_range(start_or_range: str, values: list[list[Any]]) -> str:
    """Single cell like A2 expands by values shape; full ranges pass through."""
    addr = (start_or_range or "").strip()
    if not addr:
        raise ValueError("range_address 不能为空")
    if not values:
        raise ValueError("values 不能为空")

    if ":" in addr:
        return addr

    m = re.fullmatch(r"([A-Za-z]+)(\d+)", addr)
    if not m:
        raise ValueError(f"无效的 range_address: {start_or_range}")

    start_col = _col_to_index(m.group(1))
    start_row = int(m.group(2))
    rows = len(values)
    cols = max(len(r) for r in values)

    end_col = _index_to_col(start_col + cols - 1)
    end_row = start_row + rows - 1
    if rows == 1 and cols == 1:
        return f"{m.group(1).upper()}{start_row}"
    return f"{m.group(1).upper()}{start_row}:{end_col}{end_row}"


class DingTalkWorkbookWriter:
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
        """Resolve userid to unionId (operatorId) via user detail API."""
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

    def get_sheet(
        self,
        *,
        user_id: str,
        workbook_id: str,
        sheet_id: str,
    ) -> dict[str, Any]:
        wb = (workbook_id or "").strip()
        sh = (sheet_id or "").strip()
        if not wb:
            raise ValueError("workbook_id 不能为空")
        if not sh:
            raise ValueError("sheet_id 不能为空")

        operator_id = self.get_operator_id(user_id)
        url = (
            f"https://api.dingtalk.com/v1.0/doc/workbooks/"
            f"{quote(str(wb), safe='')}/sheets/{quote(str(sh), safe='')}"
        )
        resp = requests.get(
            url,
            params={"operatorId": operator_id},
            headers={
                "x-acs-dingtalk-access-token": self.get_access_token(),
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"获取工作表属性失败 [{resp.status_code}]: {resp.text}")
        return resp.json()

    def get_last_row(
        self,
        *,
        user_id: str,
        workbook_id: str,
        sheet_id: str,
    ) -> dict[str, Any]:
        sheet = self.get_sheet(
            user_id=user_id,
            workbook_id=workbook_id,
            sheet_id=sheet_id,
        )
        last_non_empty = int(sheet.get("lastNonEmptyRow", -1))
        if last_non_empty < 0:
            last_excel_row = 0
            next_excel_row = 1
        else:
            last_excel_row = last_non_empty + 1
            next_excel_row = last_non_empty + 2

        return {
            "id": sheet.get("id"),
            "name": sheet.get("name"),
            "lastNonEmptyRow": last_non_empty,
            "lastNonEmptyColumn": sheet.get("lastNonEmptyColumn"),
            "rowCount": sheet.get("rowCount"),
            "columnCount": sheet.get("columnCount"),
            "last_excel_row": last_excel_row,
            "next_excel_row": next_excel_row,
        }

    def update_range(
        self,
        *,
        user_id: str,
        workbook_id: str,
        sheet_id: str,
        range_address: str,
        values: list[list[Any]],
    ) -> dict[str, Any]:
        wb = (workbook_id or "").strip()
        sh = (sheet_id or "").strip()
        if not wb:
            raise ValueError("workbook_id 不能为空")
        if not sh:
            raise ValueError("sheet_id 不能为空")

        operator_id = self.get_operator_id(user_id)
        resolved = expand_range(range_address, values)
        url = (
            f"https://api.dingtalk.com/v1.0/doc/workbooks/"
            f"{quote(str(wb), safe='')}/sheets/{quote(str(sh), safe='')}/ranges/"
            f"{quote(resolved, safe='')}"
        )

        resp = requests.put(
            url,
            params={"operatorId": operator_id},
            headers={
                "x-acs-dingtalk-access-token": self.get_access_token(),
                "Content-Type": "application/json",
            },
            json={"values": values},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"写入表格失败 [{resp.status_code}] range={resolved}: {resp.text}"
            )
        return resp.json()


def get_last_row(
    *,
    user_id: str,
    workbook_id: str,
    sheet_id: str,
) -> dict[str, Any]:
    """Return last non-empty row info and next writable Excel row."""
    return DingTalkWorkbookWriter().get_last_row(
        user_id=user_id,
        workbook_id=workbook_id,
        sheet_id=sheet_id,
    )


def write_cells(
    *,
    user_id: str,
    workbook_id: str,
    sheet_id: str,
    range_address: str,
    values: list[list[Any]],
) -> dict[str, Any]:
    """Write a 2D values grid into a DingTalk online workbook range."""
    return DingTalkWorkbookWriter().update_range(
        user_id=user_id,
        workbook_id=workbook_id,
        sheet_id=sheet_id,
        range_address=range_address,
        values=values,
    )
