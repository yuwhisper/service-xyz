from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from server.dingtalk.dingpan import upload_directory_as_zip, upload_file
from server.dingtalk.workbook import get_last_row, write_cells

router = APIRouter(prefix="/service/zyx/dingtalk", tags=["dingtalk"])


class DingpanUploadBody(BaseModel):
    local_path: str = Field(..., description="服务器本地文件或目录路径")
    as_zip: bool = Field(default=False, description="目录时先压缩再上传")
    save_name: str | None = Field(default=None, description="钉盘保存名，目录默认 {目录名}.zip")
    folder_url: str | None = Field(default=None, description="钉盘文件夹复制链接")
    space_id: str | None = None
    parent_folder_id: str | None = None


class WorkbookWriteBody(BaseModel):
    user_id: str = Field(..., description="操作人 userid，服务端会换取 unionId")
    workbook_id: str = Field(..., description="表格文件 ID（文档ID / nodeId）")
    sheet_id: str = Field(..., description="工作表名称或 ID")
    range_address: str = Field(..., description="起始单元格或区域，如 A2 / A2:B3")
    values: list[list[Any]] = Field(..., description="要写入的二维列表")

    @field_validator("user_id", "workbook_id", "sheet_id", "range_address")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("values")
    @classmethod
    def _values_not_empty(cls, v: list[list[Any]]) -> list[list[Any]]:
        if not v:
            raise ValueError("values 不能为空")
        return v


@router.post("/dingpan/upload")
async def dingpan_upload(body: DingpanUploadBody):
    try:
        if body.as_zip:
            data = upload_directory_as_zip(
                body.local_path,
                save_name=body.save_name,
                folder_url=body.folder_url,
                space_id=body.space_id,
                parent_folder_id=body.parent_folder_id,
            )
        else:
            data = upload_file(
                body.local_path,
                save_name=body.save_name,
                folder_url=body.folder_url,
                space_id=body.space_id,
                parent_folder_id=body.parent_folder_id,
            )
        return {"code": 0, "data": data}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except (ValueError, NotADirectoryError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


class WorkbookLastRowBody(BaseModel):
    user_id: str = Field(..., description="操作人 userid，服务端会换取 unionId")
    workbook_id: str = Field(..., description="表格文件 ID（文档ID / nodeId）")
    sheet_id: str = Field(..., description="工作表名称或 ID")

    @field_validator("user_id", "workbook_id", "sheet_id")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text


@router.post("/workbook/write")
async def workbook_write(body: WorkbookWriteBody):
    try:
        data = write_cells(
            user_id=body.user_id,
            workbook_id=body.workbook_id,
            sheet_id=body.sheet_id,
            range_address=body.range_address,
            values=body.values,
        )
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.post("/workbook/last-row")
async def workbook_last_row(body: WorkbookLastRowBody):
    try:
        data = get_last_row(
            user_id=body.user_id,
            workbook_id=body.workbook_id,
            sheet_id=body.sheet_id,
        )
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e
