"""DingTalk dingpan upload — file/directory zip and upload."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from server.dingtalk.config import (
    ALLOWED_FOLDER_HOSTS,
    APP_KEY,
    APP_SECRET,
    DEFAULT_FOLDER_URL,
    PARENT_FOLDER_ID,
    SPACE_ID,
    UNION_ID,
    UPLOAD_ALLOW_ROOTS,
)

os.environ.setdefault("NO_PROXY", "*")


def parse_dingpan_folder_url(url: str) -> tuple[str, str]:
    parsed = urlparse((url or "").strip())
    host = (parsed.netloc or "").lower()
    if host not in ALLOWED_FOLDER_HOSTS:
        raise ValueError(f"不支持的钉盘链接域名: {host or url!r}")
    qs = parse_qs(parsed.query)
    space_id = (qs.get("spaceId") or [""])[0].strip()
    file_id = (qs.get("fileId") or [""])[0].strip()
    if not space_id or not file_id:
        raise ValueError("钉盘链接缺少 spaceId 或 fileId")
    return space_id, file_id


def resolve_folder_target(
    folder_url: str | None = None,
    space_id: str | None = None,
    parent_folder_id: str | None = None,
) -> tuple[str, str]:
    if folder_url:
        return parse_dingpan_folder_url(folder_url)
    if space_id and parent_folder_id:
        return space_id.strip(), parent_folder_id.strip()
    if DEFAULT_FOLDER_URL:
        return parse_dingpan_folder_url(DEFAULT_FOLDER_URL)
    if SPACE_ID and PARENT_FOLDER_ID:
        return SPACE_ID, PARENT_FOLDER_ID
    raise ValueError("未配置钉盘目标文件夹（folder_url 或 DINGTALK_DEFAULT_FOLDER_URL）")


def assert_path_allowed(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    for root in UPLOAD_ALLOW_ROOTS:
        root_path = Path(root).expanduser().resolve()
        try:
            resolved.relative_to(root_path)
            return resolved
        except ValueError:
            continue
    raise PermissionError(f"路径不在允许范围内: {resolved}")


class DingPanUploader:
    def __init__(
        self,
        app_key: str = APP_KEY,
        app_secret: str = APP_SECRET,
        union_id: str = UNION_ID,
        space_id: str = "",
        parent_folder_id: str = "",
    ):
        if not app_key or not app_secret or not union_id:
            raise ValueError("钉钉凭证未配置（DINGTALK_APP_KEY/SECRET/UNION_ID）")
        self.app_key = app_key
        self.app_secret = app_secret
        self.union_id = union_id
        self.space_id = space_id
        self.parent_folder_id = parent_folder_id
        self._access_token: str | None = None

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

    def _api_headers(self) -> dict[str, str]:
        return {
            "x-acs-dingtalk-access-token": self.get_access_token(),
            "Content-Type": "application/json",
        }

    def _get_upload_info(self, file_path: Path, save_name: str) -> dict[str, Any]:
        url = (
            f"https://api.dingtalk.com/v1.0/storage/spaces/"
            f"{self.space_id}/files/uploadInfos/query"
        )
        body = {
            "protocol": "HEADER_SIGNATURE",
            "multipart": False,
            "option": {
                "storageDriver": "DINGTALK",
                "preCheckParam": {
                    "size": file_path.stat().st_size,
                    "name": save_name,
                    "parentId": self.parent_folder_id,
                },
                "preferIntranet": False,
            },
        }
        resp = requests.post(
            url,
            params={"unionId": self.union_id},
            headers=self._api_headers(),
            json=body,
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"获取上传信息失败 [{resp.status_code}]: {resp.text}")
        data = resp.json()
        upload_key = data.get("uploadKey")
        signature = data.get("headerSignatureInfo") or {}
        resource_urls = signature.get("resourceUrls") or []
        headers = signature.get("headers") or {}
        if not upload_key or not resource_urls:
            raise RuntimeError(f"上传信息不完整: {data}")
        return {
            "uploadKey": upload_key,
            "resourceUrl": resource_urls[0],
            "headers": headers,
        }

    def _upload_binary(
        self, file_path: Path, resource_url: str, headers: dict[str, str]
    ) -> None:
        upload_headers = dict(headers)
        upload_headers["Content-Type"] = ""
        with file_path.open("rb") as f:
            resp = requests.put(
                resource_url, data=f, headers=upload_headers, timeout=300
            )
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(f"文件二进制上传失败 [{resp.status_code}]: {resp.text}")

    def _commit_file(
        self, upload_key: str, save_name: str, file_size: int
    ) -> dict[str, Any]:
        url = (
            f"https://api.dingtalk.com/v1.0/storage/spaces/"
            f"{self.space_id}/files/commit"
        )
        body = {
            "uploadKey": upload_key,
            "name": save_name,
            "parentId": self.parent_folder_id,
            "option": {
                "size": file_size,
                "conflictStrategy": "AUTO_RENAME",
            },
        }
        resp = requests.post(
            url,
            params={"unionId": self.union_id},
            headers=self._api_headers(),
            json=body,
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"提交文件失败 [{resp.status_code}]: {resp.text}")
        data = resp.json()
        dentry = data.get("dentry")
        if not dentry:
            raise RuntimeError(f"提交响应缺少 dentry: {data}")
        return dentry

    def upload(self, local_path: str, save_name: str | None = None) -> dict[str, Any]:
        file_path = Path(local_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"本地文件不存在: {file_path}")
        save_name = (save_name or file_path.name).strip()
        if not save_name:
            raise ValueError("文件名不能为空")
        file_size = file_path.stat().st_size
        upload_info = self._get_upload_info(file_path, save_name)
        self._upload_binary(
            file_path, upload_info["resourceUrl"], upload_info["headers"]
        )
        dentry = self._commit_file(upload_info["uploadKey"], save_name, file_size)
        return _format_upload_result(dentry, save_name, file_size)


def _format_upload_result(
    dentry: dict[str, Any], save_name: str, file_size: int
) -> dict[str, Any]:
    extension = save_name.rsplit(".", 1)[-1] if "." in save_name else ""
    return {
        "fileId": dentry.get("id"),
        "spaceId": dentry.get("spaceId"),
        "fileName": dentry.get("name") or save_name,
        "fileSize": str(dentry.get("size") or file_size),
        "fileType": extension,
        "uuid": dentry.get("uuid"),
        "path": dentry.get("path"),
    }


def uploader_for_folder(
    folder_url: str | None = None,
    space_id: str | None = None,
    parent_folder_id: str | None = None,
) -> DingPanUploader:
    sid, pid = resolve_folder_target(folder_url, space_id, parent_folder_id)
    return DingPanUploader(space_id=sid, parent_folder_id=pid)


def zip_directory(dir_path: Path, zip_path: Path | None = None) -> Path:
    dir_path = assert_path_allowed(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"不是目录: {dir_path}")
    if zip_path is None:
        zip_path = dir_path.parent / f"{dir_path.name}.zip"
    else:
        zip_path = assert_path_allowed(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dir_path):
            for name in files:
                full = Path(root) / name
                zf.write(full, full.relative_to(dir_path))
    return zip_path


def upload_file(
    local_path: str,
    save_name: str | None = None,
    folder_url: str | None = None,
    space_id: str | None = None,
    parent_folder_id: str | None = None,
) -> dict[str, Any]:
    file_path = assert_path_allowed(Path(local_path))
    if not file_path.is_file():
        raise FileNotFoundError(f"本地文件不存在: {file_path}")
    uploader = uploader_for_folder(folder_url, space_id, parent_folder_id)
    result = uploader.upload(str(file_path), save_name)
    return {**result, "uploaded_from": str(file_path), "zip_path": None}


def upload_directory_as_zip(
    dir_path: str,
    save_name: str | None = None,
    folder_url: str | None = None,
    space_id: str | None = None,
    parent_folder_id: str | None = None,
    delete_zip_after: bool = True,
) -> dict[str, Any]:
    directory = assert_path_allowed(Path(dir_path))
    if not directory.is_dir():
        raise NotADirectoryError(f"不是目录: {directory}")
    zip_name = (save_name or f"{directory.name}.zip").strip()
    if not zip_name.endswith(".zip"):
        zip_name = f"{zip_name}.zip"
    zip_path = directory.parent / zip_name
    zip_directory(directory, zip_path)
    try:
        uploader = uploader_for_folder(folder_url, space_id, parent_folder_id)
        result = uploader.upload(str(zip_path), zip_name)
        return {**result, "uploaded_from": str(directory), "zip_path": str(zip_path)}
    finally:
        if delete_zip_after and zip_path.exists():
            zip_path.unlink()
