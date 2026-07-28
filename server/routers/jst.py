import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from server.jushuitan.client import (
    fetch_token_info,
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
