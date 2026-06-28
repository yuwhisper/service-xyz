import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load config.json
with open(ROOT / "config.json") as f:
    _cfg = json.load(f)

# DB settings (env overrides config.json)
DB_HOST = os.getenv("DB_HOST", _cfg["db"].get("host", "127.0.0.1"))
DB_PORT = int(os.getenv("DB_PORT", _cfg["db"].get("port", 3306)))
DB_USER = os.getenv("DB_USER", _cfg["db"].get("user", "root"))
DB_PASS = os.getenv("DB_PASS", _cfg["db"].get("pass", ""))
DB_NAME = os.getenv("DB_NAME", _cfg["db"].get("DATABASE", "zyx"))

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", _cfg.get("jwt", {}).get("secret", "default-secret"))
JWT_EXPIRES = int(os.getenv("JWT_EXPIRES_DAYS", 7)) * 86400

# Server
PORT = int(os.getenv("PORT", _cfg.get("port", 3000)))
