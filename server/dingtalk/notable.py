"""DingTalk AI Table (notable) — insert records + attachment upload."""
from __future__ import annotations

import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import requests

from server.dingtalk.config import APP_KEY, APP_SECRET
from server.dingtalk.dingpan import assert_path_allowed

os.environ.setdefault("NO_PROXY", "*")


def _guess_media_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


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

    def get_resource_upload_info(
        self,
        *,
        user_id: str,
        base_id: str,
        file_path: Path,
    ) -> dict[str, Any]:
        bid = (base_id or "").strip()
        if not bid:
            raise ValueError("base_id 不能为空")
        if not file_path.is_file():
            raise FileNotFoundError(f"本地文件不存在: {file_path}")

        size = file_path.stat().st_size
        media_type = _guess_media_type(file_path)
        resource_name = file_path.name
        operator_id = self.get_operator_id(user_id)

        url = (
            f"https://api.dingtalk.com/v1.0/doc/docs/resources/"
            f"{quote(str(bid), safe='')}/uploadInfos/query"
        )
        resp = requests.post(
            url,
            params={"operatorId": operator_id},
            headers={
                "x-acs-dingtalk-access-token": self.get_access_token(),
                "Content-Type": "application/json",
            },
            json={
                "size": size,
                "mediaType": media_type,
                "resourceName": resource_name,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"获取上传信息失败 [{resp.status_code}]: {resp.text}")

        data = resp.json()
        result = data.get("result") or data
        upload_url = result.get("uploadUrl")
        resource_id = result.get("resourceId")
        resource_url = result.get("resourceUrl")
        if not upload_url or not resource_id or not resource_url:
            raise RuntimeError(f"上传信息不完整: {data}")

        return {
            "uploadUrl": upload_url,
            "resourceId": resource_id,
            "resourceUrl": resource_url,
            "size": size,
            "mediaType": media_type,
            "resourceName": resource_name,
        }

    def put_file(self, upload_url: str, file_path: Path, media_type: str) -> None:
        with file_path.open("rb") as f:
            resp = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": media_type},
                timeout=120,
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"PUT 上传失败 [{resp.status_code}]: {resp.text}")

    def upload_attachment(
        self,
        *,
        user_id: str,
        base_id: str,
        file_path: str | Path | None = None,
        file_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        三步上传后返回可写入附件字段的对象：
        {filename, size, type, url, resourceId}
        """
        tmp_path: Path | None = None
        try:
            if file_bytes is not None:
                name = (filename or "upload.bin").strip() or "upload.bin"
                suffix = Path(name).suffix or ".bin"
                fd, tmp_name = tempfile.mkstemp(prefix="notable_", suffix=suffix)
                os.close(fd)
                tmp_path = Path(tmp_name)
                tmp_path.write_bytes(file_bytes)
                path = tmp_path
                # ensure original filename used for DingTalk resourceName
                # by writing into a named temp file under same dir
                named = tmp_path.with_name(name)
                if named != tmp_path:
                    named.write_bytes(file_bytes)
                    tmp_path.unlink(missing_ok=True)
                    tmp_path = named
                    path = named
            elif file_path is not None:
                path = assert_path_allowed(Path(file_path))
                if not path.is_file():
                    raise FileNotFoundError(f"本地文件不存在: {path}")
            else:
                raise ValueError("file_path 与 file_bytes 至少提供一个")

            info = self.get_resource_upload_info(
                user_id=user_id, base_id=base_id, file_path=path
            )
            self.put_file(info["uploadUrl"], path, info["mediaType"])
            return {
                "filename": info["resourceName"],
                "size": info["size"],
                "type": info["mediaType"],
                "url": info["resourceUrl"],
                "resourceId": info["resourceId"],
            }
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

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


def upload_attachment(
    *,
    user_id: str,
    base_id: str,
    file_path: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Upload a file into AI Table resource space; return attachment field object."""
    return DingTalkNotableWriter().upload_attachment(
        user_id=user_id,
        base_id=base_id,
        file_path=file_path,
        file_bytes=file_bytes,
        filename=filename,
    )
