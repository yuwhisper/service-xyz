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
    o_id: str | None = Field(default=None, description="聚水潭内部订单号")
    so_id: str | None = Field(default=None, description="线上订单号")


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
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (int, float)):
            return [int(value)]
        text = str(value).strip()
        if not text:
            return []
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("wms_co_ids JSON 必须是数组")
            return parsed
        return [x.strip() for x in text.split(",") if x.strip()]


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
    o_id: str | None = Query(None, description="聚水潭内部订单号"),
    so_id: str | None = Query(None, description="线上订单号"),
):
    return await _query_order(o_id=o_id, so_id=so_id)


@router.post("/order/query")
async def query_order_post(body: OrderQueryBody):
    return await _query_order(o_id=body.o_id, so_id=body.so_id)


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


async def _query_order(*, o_id: str | None, so_id: str | None):
    try:
        data = await asyncio.to_thread(query_order_raw, o_id=o_id, so_id=so_id)
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
