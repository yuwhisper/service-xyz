"""Persist Jushuitan tokens from API responses (not .env)."""
from __future__ import annotations

import json
import os
from typing import Any

from server.jushuitan.config import TOKEN_FILE


def load_tokens() -> dict[str, Any]:
    path = TOKEN_FILE
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_tokens(
    *,
    access_token: str,
    refresh_token: str,
    expires_at: float,
) -> None:
    path = TOKEN_FILE
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(expires_at),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
