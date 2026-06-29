"""Ozon FBO shipment runner — wraps fahuo_core and tracks 唯一ID results."""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from server.ozon import fahuo_core as core
from server.ozon.config import DEFAULT_CROSSDOCK_DROP_OFF_NAME


def _row_ids(rows) -> list[str]:
    ids: list[str] = []
    for row in rows or []:
        uid = row.get("唯一ID") if isinstance(row, dict) else row
        if uid is None or uid == "":
            continue
        ids.append(str(int(uid)))
    return list(dict.fromkeys(ids))


def _parse_ship_date(raw) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if hasattr(raw, "year"):
        return raw
    return datetime.strptime(str(raw), "%Y-%m-%d").date()


def _fail_rows(failed: list[dict], rows, reason: str) -> None:
    for uid in _row_ids(rows):
        failed.append({"id": uid, "reason": reason})


def _run_full(params: dict[str, Any]) -> dict[str, Any]:
    drop_off = params.get("drop_off_warehouse_name") or DEFAULT_CROSSDOCK_DROP_OFF_NAME
    ship_date = _parse_ship_date(params.get("ship_date"))

    success: list[str] = []
    failed: list[dict] = []

    try:
        groups = core.fetch_pending_shipment_groups(ship_date=ship_date)
    except Exception as e:
        return {"success": [], "failed": [{"id": "", "reason": f"读取数据库失败: {e}"}]}

    if not groups:
        return {"success": [], "failed": []}

    bundle_map: dict = defaultdict(list)
    for group in groups:
        bundle_map[group["bundle_key"]].append(group)

    task_idx = 0
    for bundle_key, method_groups in sorted(
        bundle_map.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3]),
    ):
        ship_d, shop, shipper, batch_or_order = bundle_key
        export_bundles = []

        for group in sorted(
            method_groups,
            key=lambda g: 0 if g["shipping_method"] == "直发" else 1,
        ):
            task_idx += 1
            group_rows = group.get("rows") or []
            try:
                export_bundle = core.run_group_application(
                    group,
                    drop_off_warehouse_name=drop_off,
                )
            except Exception as e:
                _fail_rows(failed, group_rows, f"执行异常: {e}")
                continue

            if not export_bundle:
                _fail_rows(
                    failed,
                    group_rows,
                    f"{group['shipping_method']}单 {shipper} 申请失败",
                )
                continue

            success.extend(_row_ids(group_rows))
            export_bundles.append(export_bundle)
            if len(export_bundles) < len(method_groups):
                time.sleep(10)

        if not export_bundles:
            continue

        order_dir = core.build_order_output_dir(
            shipper, shop, batch_or_order, archive_date=ship_d
        )
        all_rows = []
        for group in method_groups:
            all_rows.extend(group.get("rows") or [])
        internal_order_no = core.combine_internal_order_nos(all_rows)
        try:
            core.finalize_combined_exports(
                order_dir, export_bundles, internal_order_no
            )
        except Exception as e:
            _fail_rows(
                failed,
                all_rows,
                f"发货包 {shipper}+{shop}+{batch_or_order} 总表合并失败: {e}",
            )

    success = list(dict.fromkeys(success))
    failed_ids = {item["id"] for item in failed if item.get("id")}
    success = [uid for uid in success if uid not in failed_ids]
    return {"success": success, "failed": failed}


def _run_resume(params: dict[str, Any]) -> dict[str, Any]:
    success: list[str] = []
    failed: list[dict] = []

    shop = (params.get("shop") or "").strip()
    batch = (params.get("batch") or "").strip()
    if not shop or not batch:
        return {
            "success": [],
            "failed": [{"id": "", "reason": "续传模式需要 shop 与 batch"}],
        }

    ship_date = _parse_ship_date(params.get("ship_date")) or datetime.now().date()
    try:
        rows = core.fetch_batch_rows(shop, batch, ship_date=ship_date)
        items = core.build_items_from_rows(rows)
        internal_order_no = core.combine_internal_order_nos(rows)
        shipper = core.combine_shippers(rows)
        batch_or_order = core.resolve_batch_or_order_from_rows(rows)
        clusters = sorted(
            {
                (row.get("集群") or "").strip() or "未知集群"
                for row in rows
                if (row.get("集群") or "").strip()
            }
        )
        cluster = core.cluster_folder_label(clusters) if clusters else ""
    except Exception as e:
        return {"success": [], "failed": [{"id": "", "reason": f"读取批次失败: {e}"}]}

    row_ids = _row_ids(rows)
    order_id = None

    if params.get("all_supplies"):
        if not params.get("order_id"):
            return {
                "success": [],
                "failed": [{"id": "", "reason": "--all-supplies 需要 order_id"}],
            }
        order_id = core.run_resume_merged_cargoes(
            target_shop=shop,
            order_id=int(params["order_id"]),
            items=items,
            rows=rows,
            batch_no=batch,
            internal_order_no=internal_order_no,
            shipper=shipper,
            archive_date=ship_date,
            clusters=clusters,
            batch_or_order=batch_or_order,
        )
    elif params.get("supply_ids"):
        if not params.get("order_id"):
            return {
                "success": [],
                "failed": [{"id": "", "reason": "supply_ids 需要 order_id"}],
            }
        order_id = core.run_resume_merged_cargoes(
            target_shop=shop,
            order_id=int(params["order_id"]),
            items=items,
            rows=rows,
            batch_no=batch,
            internal_order_no=internal_order_no,
            shipper=shipper,
            archive_date=ship_date,
            clusters=clusters,
            batch_or_order=batch_or_order,
        )
    else:
        if not params.get("supply_id") or not params.get("order_id"):
            return {
                "success": [],
                "failed": [
                    {
                        "id": "",
                        "reason": "续传需要 order_id 与 supply_id，或 all_supplies",
                    }
                ],
            }
        order_id = core.run_resume_cargoes_only(
            target_shop=shop,
            supply_id=int(params["supply_id"]),
            order_id=int(params["order_id"]),
            items=items,
            batch_no=batch,
            internal_order_no=internal_order_no,
            shipper=shipper,
            archive_date=ship_date,
            source_rows=rows,
            cluster=cluster,
            batch_or_order=batch_or_order,
        )

    if order_id:
        success = row_ids
    else:
        _fail_rows(failed, rows, "续传失败")

    return {"success": success, "failed": failed}


def run_fahuo(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run Ozon shipment workflow; returns {success: [...], failed: [{id, reason}]}."""
    params = params or {}
    if params.get("resume_cargoes"):
        return _run_resume(params)
    return _run_full(params)
