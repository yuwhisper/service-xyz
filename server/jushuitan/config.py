"""Jushuitan OpenAPI configuration."""
import os

APP_KEY = os.getenv("JUSHUITAN_APP_KEY", "")
APP_SECRET = os.getenv("JUSHUITAN_APP_SECRET", "")
AUTH_CODE = os.getenv("JUSHUITAN_AUTH_CODE", "")
ACCESS_TOKEN = os.getenv("JUSHUITAN_ACCESS_TOKEN", "")
REFRESH_TOKEN = os.getenv("JUSHUITAN_REFRESH_TOKEN", "")

OPENAPI_BASE = os.getenv("JUSHUITAN_OPENAPI_BASE", "https://openapi.jushuitan.com")
SKU_QUERY_PATH = "/open/sku/query"
INIT_TOKEN_PATH = "/openWeb/auth/getInitToken"
ACCESS_TOKEN_PATH = "/openWeb/auth/accessToken"
REFRESH_TOKEN_PATH = "/openWeb/auth/refreshToken"

SKU_QUERY_BATCH_SIZE = int(os.getenv("JUSHUITAN_SKU_BATCH_SIZE", "50"))
