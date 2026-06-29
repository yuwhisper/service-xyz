"""Ozon fahuo configuration — production paths on server /opt/service-zyx."""
import json
import os

# Archive: default server path; override in /opt/service-zyx/.env
SHIPMENT_ARCHIVE_ROOT = os.getenv(
    "OZON_ARCHIVE_ROOT",
    "/opt/service-zyx/ozon-fahuo-data",
)

DB_CONFIG = {
    "host": os.getenv("OZON_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
    "port": int(os.getenv("OZON_DB_PORT", os.getenv("DB_PORT", "3306"))),
    "user": os.getenv("OZON_DB_USER", os.getenv("DB_USER", "root")),
    "password": os.getenv("OZON_DB_PASS", os.getenv("DB_PASS", "")),
    "database": os.getenv("OZON_DB_NAME", os.getenv("DB_NAME", "zyx")),
    "charset": "utf8mb4",
}

_raw_shops = os.getenv("OZON_SHOP_DATA", "{}")
try:
    SHOP_DATA = json.loads(_raw_shops) if _raw_shops.strip() else {}
except json.JSONDecodeError:
    SHOP_DATA = {}

DEFAULT_CROSSDOCK_DROP_OFF_NAME = os.getenv(
    "OZON_CROSSDOCK_DROP_OFF",
    "МО_ЩЕРБИНКА_ХАБ",
)
