"""Jushuitan OpenAPI configuration."""
import os

APP_KEY = os.getenv("JUSHUITAN_APP_KEY", "")
APP_SECRET = os.getenv("JUSHUITAN_APP_SECRET", "")
AUTH_CODE = os.getenv("JUSHUITAN_AUTH_CODE", "")

OPENAPI_BASE = os.getenv("JUSHUITAN_OPENAPI_BASE", "https://openapi.jushuitan.com")
SKU_QUERY_PATH = "/open/sku/query"
INIT_TOKEN_PATH = "/openWeb/auth/getInitToken"
ACCESS_TOKEN_PATH = "/openWeb/auth/accessToken"
REFRESH_TOKEN_PATH = "/openWeb/auth/refreshToken"

SKU_QUERY_BATCH_SIZE = int(os.getenv("JUSHUITAN_SKU_BATCH_SIZE", "50"))

_archive_root = os.getenv("OZON_ARCHIVE_ROOT", "/opt/service-zyx/ozon-fahuo-data").rstrip("/\\")
_default_token_dir = os.path.dirname(_archive_root) or "/opt/service-zyx"
TOKEN_FILE = os.getenv(
    "JUSHUITAN_TOKEN_FILE",
    os.path.join(_default_token_dir, ".jst_tokens.json"),
)
