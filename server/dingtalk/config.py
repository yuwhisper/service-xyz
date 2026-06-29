"""DingTalk dingpan configuration."""
import os

from server.ozon.config import SHIPMENT_ARCHIVE_ROOT

APP_KEY = os.getenv("DINGTALK_APP_KEY", "")
APP_SECRET = os.getenv("DINGTALK_APP_SECRET", "")
UNION_ID = os.getenv("DINGTALK_UNION_ID", "")

DEFAULT_FOLDER_URL = os.getenv("DINGTALK_DEFAULT_FOLDER_URL", "")
SPACE_ID = os.getenv("DINGTALK_SPACE_ID", "")
PARENT_FOLDER_ID = os.getenv("DINGTALK_PARENT_FOLDER_ID", "")

_raw_roots = os.getenv("DINGTALK_UPLOAD_ALLOW_ROOTS", SHIPMENT_ARCHIVE_ROOT)
UPLOAD_ALLOW_ROOTS = [p.strip() for p in _raw_roots.split(",") if p.strip()]

OZON_UPLOAD_DINGPAN = os.getenv("OZON_UPLOAD_DINGPAN", "true").lower() in (
    "1",
    "true",
    "yes",
)

ALLOWED_FOLDER_HOSTS = frozenset(
    {"qr.dingtalk.com", "dingtalk.com", "www.dingtalk.com"}
)
