import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from server.jushuitan.client import (
    create_lwh_allocation,
    create_lwh_operation,
    fetch_token_info,
    get_lwh_by_name,
    query_inventory_by_sku,
    query_order_raw,
    query_sku_raw,
)

router = APIRouter(prefix="/service/zyx/jst", tags=["jushuitan"])


def _parse_list_value(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (int, float)):
        return [value]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("必须是 JSON 数组")
        return parsed
    return [x.strip() for x in text.split(",") if x.strip()]


class GetTokenBody(BaseModel):
    code: str | None = Field(
        default=None,
        description="聚水潭授权 code；不传则用环境变量 JUSHUITAN_AUTH_CODE",
    )
    force: bool = Field(
        default=False,
        description="true=忽略缓存，重新向聚水潭换取 token",
    )


class SkuQueryBody(BaseModel):
    sku: str = Field(..., description="聚水潭 SKU / 货号")


class OrderQueryBody(BaseModel):
    # 单号（兼容旧字段 + 列表）
    o_id: str | None = Field(default=None, description="内部订单号（单个，兼容旧参数）")
    so_id: str | None = Field(default=None, description="线上订单号（单个，兼容旧参数）")
    o_ids: list[Any] = Field(default_factory=list, description="内部订单号列表，最多20条")
    so_ids: list[Any] = Field(default_factory=list, description="线上单号列表，最多20条")

    shop_id: int | None = Field(default=None, description="店铺编号")
    is_offline_shop: bool | None = Field(
        default=None,
        description="shop_id 为 0 且为 true 时查询线下店铺单据",
    )
    modified_begin: str | None = Field(default=None, description="起始时间")
    modified_end: str | None = Field(default=None, description="结束时间")
    date_type: int | None = Field(
        default=None,
        description="0修改时间 / 2订单日期 / 3发货时间，默认0",
    )
    status: str | None = Field(
        default=None,
        description="订单状态：WaitPay/Delivering/Merged/Question/Split/WaitOuterSent/WaitConfirm/WaitFConfirm/Sent/Cancelled",
    )
    page_index: int | None = Field(default=None, description="页码，从1开始")
    page_size: int | None = Field(default=None, description="每页条数，最大100")
    start_ts: int | None = Field(default=None, description="ts 时间戳增量查询（>=）")
    is_get_total: bool | None = Field(
        default=None,
        description="是否查询总条数；start_ts 查询时建议 false",
    )
    order_types: list[Any] = Field(default_factory=list, description="订单类型列表")
    archive: bool | None = Field(default=None, description="是否查询历史订单，默认 false")
    is_get_cbfinance: bool | None = Field(
        default=True,
        description="是否获取跨境财务字段（兼容旧行为，默认 true）",
    )

    # order_flds：分开写，true 时加入自定义返回字段
    volume: bool | None = Field(default=None, description="订单自定义字段：体积")
    package: bool | None = Field(default=None, description="订单自定义字段：包材")
    outer_drp_co_id: bool | None = Field(default=None, description="订单自定义字段：货主分销")
    cus_id: bool | None = Field(default=None, description="订单自定义字段：货通客户id")
    logistics_status: bool | None = Field(
        default=None,
        description="订单自定义字段：o2o配送状态",
    )

    # order_item_flds
    src_combine_sku_qty: bool | None = Field(default=None, description="明细：原组合商品数量")
    referrer_name: bool | None = Field(default=None, description="明细：达人名称")
    presale_date: bool | None = Field(default=None, description="明细：预售时间")
    drp_price: bool | None = Field(default=None, description="明细：采购价")
    item_plan_delivery_date: bool | None = Field(default=None, description="明细：最晚发货时间")
    activity_u_id: bool | None = Field(default=None, description="明细：团长id")
    activity_u_name: bool | None = Field(default=None, description="明细：团长名称")

    @field_validator("o_ids", "so_ids", "order_types", mode="before")
    @classmethod
    def _parse_lists(cls, value: Any) -> list[Any]:
        return _parse_list_value(value)


class InventoryQueryBody(BaseModel):
    sku: str = Field(..., description="商品编码")
    wms_co_ids: list[int] = Field(
        default_factory=list,
        description="分仓公司编号列表；空列表表示查所有仓总库存(wms_co_id=0)",
    )
    has_lock_qty: bool = Field(default=True, description="是否返回库存锁定数")

    @field_validator("wms_co_ids", mode="before")
    @classmethod
    def _parse_wms_co_ids(cls, value: Any) -> list[Any]:
        return _parse_list_value(value)


class LwhQueryBody(BaseModel):
    name: str = Field(..., description="虚拟仓中文名，精确匹配")


class AllocationCreateBody(BaseModel):
    out_lwh: str = Field(..., description="调出虚拟仓：中文名或数字 id")
    in_lwh: str = Field(..., description="调入虚拟仓：中文名或数字 id")
    wms: str | None = Field(
        default=None,
        description="实体仓：中文名或 id；两边共有仅1绑定时可空",
    )
    so_id: str | None = Field(
        default=None,
        description="外部单号；空则自动 YYYYMMDD+流水",
    )
    remark: str = Field(..., description="备注")
    items: list[Any] = Field(..., description="明细 [{sku_id, qty?, sku_sns?}]")
    examine: bool = Field(default=False, description="是否审核生效")

    @field_validator("items", mode="before")
    @classmethod
    def _parse_items(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            raise ValueError("items 为必填数组")
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("items 为必填数组")
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("items 必须是 JSON 数组")
            return parsed
        raise ValueError("items 必须是数组")


class LwhOperationCreateBody(BaseModel):
    lwh: str = Field(..., description="虚拟仓：中文名或数字 id")
    type: str = Field(..., description="虚拟仓分配 / 虚拟仓归还")
    items: list[Any] = Field(..., description="明细 [{sku_id, qty?}]，qty 空或0取可用数")
    wms: str | None = Field(
        default=None,
        description="实体仓：中文名或 id；该虚拟仓仅绑定1个实体仓时可空",
    )
    so_id: str | None = Field(
        default=None,
        description="外部单号；空则自动生成日期时分秒毫秒",
    )
    remark: str | None = Field(default=None, description="备注")
    examine: bool = Field(default=False, description="是否审核生效")
    isIgnore_check_stock: bool | None = Field(
        default=None,
        description="是否允许超锁；仅 examine=true 时有效",
    )

    @field_validator("items", mode="before")
    @classmethod
    def _parse_op_items(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            raise ValueError("items 为必填数组")
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("items 为必填数组")
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("items 必须是 JSON 数组")
            return parsed
        raise ValueError("items 必须是数组")

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        text = str(value or "").strip()
        if text not in ("虚拟仓分配", "虚拟仓归还"):
            raise ValueError("type 必须是「虚拟仓分配」或「虚拟仓归还」")
        return text


@router.get("/gettoken")
async def get_token_get(
    force: bool = Query(False, description="忽略缓存重新换取"),
    code: str | None = Query(None, description="聚水潭授权 code"),
):
    return _get_token(force=force, code=code)


@router.post("/gettoken")
async def get_token_post(body: GetTokenBody = Body(default_factory=GetTokenBody)):
    return _get_token(force=body.force, code=body.code)


@router.get("/sku/query")
async def query_sku_get(
    sku: str = Query(..., description="聚水潭 SKU / 货号"),
):
    return await _query_sku(sku)


@router.post("/sku/query")
async def query_sku_post(body: SkuQueryBody):
    return await _query_sku(body.sku)


@router.get("/order/query")
async def query_order_get(
    o_id: str | None = Query(None, description="内部订单号"),
    so_id: str | None = Query(None, description="线上订单号"),
    shop_id: int | None = Query(None, description="店铺编号"),
    modified_begin: str | None = Query(None, description="起始时间"),
    modified_end: str | None = Query(None, description="结束时间"),
    status: str | None = Query(None, description="订单状态"),
    page_index: int | None = Query(None, description="页码"),
    page_size: int | None = Query(None, description="每页条数"),
    start_ts: int | None = Query(None, description="ts 增量"),
):
    return await _query_order(
        o_id=o_id,
        so_id=so_id,
        shop_id=shop_id,
        modified_begin=modified_begin,
        modified_end=modified_end,
        status=status,
        page_index=page_index,
        page_size=page_size,
        start_ts=start_ts,
    )


@router.post("/order/query")
async def query_order_post(body: OrderQueryBody):
    return await _query_order(**body.model_dump())


@router.get("/inventory/query")
async def query_inventory_get(
    sku: str = Query(..., description="商品编码"),
    wms_co_ids: str = Query(
        "",
        description="分仓公司编号，逗号分隔；空=所有仓总库存",
    ),
    has_lock_qty: bool = Query(True, description="是否返回库存锁定数"),
):
    ids = [int(x.strip()) for x in wms_co_ids.split(",") if x.strip()]
    return await _query_inventory(sku=sku, wms_co_ids=ids, has_lock_qty=has_lock_qty)


@router.post("/inventory/query")
async def query_inventory_post(body: InventoryQueryBody):
    return await _query_inventory(
        sku=body.sku,
        wms_co_ids=body.wms_co_ids,
        has_lock_qty=body.has_lock_qty,
    )


@router.get("/lwh/query")
async def query_lwh_get(
    name: str = Query(..., description="虚拟仓中文名，精确匹配"),
):
    return await _query_lwh(name)


@router.post("/lwh/query")
async def query_lwh_post(body: LwhQueryBody):
    return await _query_lwh(body.name)


@router.post("/lwh/allocation/create")
async def create_allocation_post(body: AllocationCreateBody):
    return await _create_allocation(
        out_lwh=body.out_lwh,
        in_lwh=body.in_lwh,
        wms=body.wms,
        so_id=body.so_id,
        remark=body.remark,
        items=body.items,
        examine=body.examine,
    )


@router.post("/lwh/operation/create")
async def create_operation_post(body: LwhOperationCreateBody):
    return await _create_operation(
        lwh=body.lwh,
        op_type=body.type,
        items=body.items,
        wms=body.wms,
        so_id=body.so_id,
        remark=body.remark,
        examine=body.examine,
        is_ignore_check_stock=body.isIgnore_check_stock,
    )


def _allocation_fail_rows(
    *,
    out_lwh: Any,
    in_lwh: Any,
    wms: Any,
    remark: str,
    items: list[Any],
    reason: str,
) -> list[list[Any]]:
    """失败时展开为二维列表：调出仓,实体仓,调入仓,SKU,数量,备注,失败原因。"""
    reason_text = str(reason or "").strip()
    out_text = "" if out_lwh is None else str(out_lwh).strip()
    in_text = "" if in_lwh is None else str(in_lwh).strip()
    wms_text = "" if wms is None else str(wms).strip()
    remark_text = "" if remark is None else str(remark).strip()

    rows: list[list[Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        sku_id = str(item.get("sku_id") or "").strip()
        qty = item.get("qty")
        if qty is None or str(qty).strip() == "":
            qty_val: Any = ""
        else:
            qty_val = qty
        rows.append([
            out_text,
            wms_text,
            in_text,
            sku_id,
            qty_val,
            remark_text,
            reason_text,
        ])
    if not rows:
        rows.append([
            out_text,
            wms_text,
            in_text,
            "",
            "",
            remark_text,
            reason_text,
        ])
    return rows


def _get_token(*, force: bool, code: str | None):
    try:
        data = fetch_token_info(force=force, code=code)
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


async def _query_sku(sku: str):
    sku_text = (sku or "").strip()
    if not sku_text:
        raise HTTPException(400, "sku 不能为空")
    try:
        item = await asyncio.to_thread(query_sku_raw, sku_text)
        return {
            "code": 0,
            "data": {
                "sku": sku_text,
                "found": item is not None,
                "item": item,
            },
        }
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


async def _query_order(**kwargs: Any):
    try:
        data = await asyncio.to_thread(query_order_raw, **kwargs)
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


async def _query_inventory(
    *,
    sku: str,
    wms_co_ids: list[Any],
    has_lock_qty: bool = True,
):
    sku_text = (sku or "").strip()
    if not sku_text:
        raise HTTPException(400, "sku 不能为空")
    try:
        items = await asyncio.to_thread(
            query_inventory_by_sku,
            sku_text,
            wms_co_ids,
            has_lock_qty=has_lock_qty,
        )
        return {
            "code": 0,
            "data": {
                "sku": sku_text,
                "wms_co_ids": list(wms_co_ids) if wms_co_ids else [0],
                "count": len(items),
                "items": items,
            },
        }
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


async def _query_lwh(name: str):
    try:
        data = await asyncio.to_thread(get_lwh_by_name, name)
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


async def _create_allocation(
    *,
    out_lwh: Any,
    in_lwh: Any,
    remark: str,
    items: list[Any],
    wms: Any = None,
    so_id: str | None = None,
    examine: bool = False,
):
    try:
        data = await asyncio.to_thread(
            create_lwh_allocation,
            out_lwh=out_lwh,
            in_lwh=in_lwh,
            wms=wms,
            so_id=so_id,
            remark=remark,
            items=items,
            examine=examine,
        )
        return {"code": 0, "data": data}
    except ValueError as e:
        # 与之前一致：业务校验失败 HTTP 400；body 为二维列表
        return JSONResponse(
            status_code=400,
            content={
                "detail": _allocation_fail_rows(
                    out_lwh=out_lwh,
                    in_lwh=in_lwh,
                    wms=wms,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )
    except RuntimeError as e:
        return JSONResponse(
            status_code=502,
            content={
                "detail": _allocation_fail_rows(
                    out_lwh=out_lwh,
                    in_lwh=in_lwh,
                    wms=wms,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "detail": _allocation_fail_rows(
                    out_lwh=out_lwh,
                    in_lwh=in_lwh,
                    wms=wms,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )


def _operation_fail_rows(
    *,
    lwh: Any,
    wms: Any,
    op_type: str,
    remark: str | None,
    items: list[Any],
    reason: str,
) -> list[list[Any]]:
    """失败二维列表：虚拟仓,实体仓,类型,SKU,数量,备注,失败原因。"""
    reason_text = str(reason or "").strip()
    lwh_text = "" if lwh is None else str(lwh).strip()
    wms_text = "" if wms is None else str(wms).strip()
    type_text = "" if op_type is None else str(op_type).strip()
    remark_text = "" if remark is None else str(remark).strip()

    rows: list[list[Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        sku_id = str(item.get("sku_id") or "").strip()
        qty = item.get("qty")
        qty_val: Any = "" if qty is None or str(qty).strip() == "" else qty
        rows.append([
            lwh_text,
            wms_text,
            type_text,
            sku_id,
            qty_val,
            remark_text,
            reason_text,
        ])
    if not rows:
        rows.append([
            lwh_text,
            wms_text,
            type_text,
            "",
            "",
            remark_text,
            reason_text,
        ])
    return rows


async def _create_operation(
    *,
    lwh: Any,
    op_type: str,
    items: list[Any],
    wms: Any = None,
    so_id: str | None = None,
    remark: str | None = None,
    examine: bool = False,
    is_ignore_check_stock: bool | None = None,
):
    try:
        data = await asyncio.to_thread(
            create_lwh_operation,
            lwh=lwh,
            op_type=op_type,
            items=items,
            wms=wms,
            so_id=so_id,
            remark=remark,
            examine=examine,
            is_ignore_check_stock=is_ignore_check_stock,
        )
        return {"code": 0, "data": data}
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "detail": _operation_fail_rows(
                    lwh=lwh,
                    wms=wms,
                    op_type=op_type,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )
    except RuntimeError as e:
        return JSONResponse(
            status_code=502,
            content={
                "detail": _operation_fail_rows(
                    lwh=lwh,
                    wms=wms,
                    op_type=op_type,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "detail": _operation_fail_rows(
                    lwh=lwh,
                    wms=wms,
                    op_type=op_type,
                    remark=remark,
                    items=items,
                    reason=str(e),
                ),
            },
        )
