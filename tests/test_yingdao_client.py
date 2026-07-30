# tests/test_yingdao_client.py
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.yingdao import client as yd


def test_build_start_payload_account_mode():
    body = yd.build_start_payload(
        robot_uuid="r1",
        account_name="admin@wxbh",
        robot_client_group_uuid="",
        params=[{"name": "开始日期", "value": "2026-07-27", "type": "str"}],
        wait_timeout_seconds=600,
        run_timeout=None,
        priority="middle",
        execute_scope="any",
        use_idempotent=False,
        idempotent_uuid=None,
    )
    assert body["robotUuid"] == "r1"
    assert body["accountName"] == "admin@wxbh"
    assert "robotClientGroupUuid" not in body
    assert body["params"][0]["name"] == "开始日期"
    assert body["waitTimeoutSeconds"] == 600


def test_build_start_payload_group_wins():
    body = yd.build_start_payload(
        robot_uuid="r1",
        account_name="admin@wxbh",
        robot_client_group_uuid="g1",
        params=None,
        wait_timeout_seconds=120,
        run_timeout=300,
        priority="high",
        execute_scope="all",
        use_idempotent=True,
        idempotent_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert body["robotClientGroupUuid"] == "g1"
    assert body["executeScope"] == "all"
    assert "accountName" not in body
    assert body["runTimeout"] == 300
    assert body["idempotentUuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_build_start_payload_requires_target():
    with pytest.raises(ValueError, match="账号|分组"):
        yd.build_start_payload(
            robot_uuid="r1",
            account_name="",
            robot_client_group_uuid="",
            params=None,
            wait_timeout_seconds=600,
            run_timeout=None,
            priority="middle",
            execute_scope="any",
            use_idempotent=False,
            idempotent_uuid=None,
        )


def test_map_yingdao_http_hint():
    assert "限流" in yd.http_status_hint(429)
    assert "未授权" in yd.http_status_hint(401)
