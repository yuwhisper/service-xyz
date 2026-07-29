from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from server.dingtalk.dingpan import upload_directory_as_zip, upload_file
from server.dingtalk.notable import insert_records, upload_attachment
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


class NotableInsertBody(BaseModel):
    user_id: str = Field(..., description="操作人 userid，服务端会换取 unionId")
    base_id: str = Field(..., description="AI 多维表文档 ID（baseId）")
    sheet_id: str = Field(..., description="数据表名称或 ID（不是视图页签）")
    records: list[dict[str, Any]] = Field(..., description="记录列表，每项为字段名到值的字典")

    @field_validator("user_id", "base_id", "sheet_id")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("records")
    @classmethod
    def _records_not_empty(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not v:
            raise ValueError("records 不能为空")
        return v


@router.post("/notable/records")
async def notable_insert_records(body: NotableInsertBody):
    try:
        data = insert_records(
            user_id=body.user_id,
            base_id=body.base_id,
            sheet_id=body.sheet_id,
            records=body.records,
        )
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


class NotableUploadPathBody(BaseModel):
    user_id: str = Field(..., description="操作人 userid，服务端会换取 unionId")
    base_id: str = Field(..., description="AI 多维表文档 ID（docId / baseId）")
    file_path: str = Field(..., description="服务器本地文件路径（须在允许根目录内）")

    @field_validator("user_id", "base_id", "file_path")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text


@router.post("/notable/upload-attachment")
async def notable_upload_attachment_json(body: NotableUploadPathBody):
    """JSON：用服务器本地路径上传附件，返回可写入附件列的对象。"""
    try:
        data = upload_attachment(
            user_id=body.user_id,
            base_id=body.base_id,
            file_path=body.file_path,
        )
        return {"code": 0, "data": data}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.post("/notable/upload-attachment-file")
async def notable_upload_attachment_file(
    user_id: str = Form(...),
    base_id: str = Form(...),
    file: UploadFile = File(...),
):
    """multipart：上传文件内容到 AI 表格资源，返回附件对象。"""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "文件内容为空")
        data = upload_attachment(
            user_id=user_id.strip(),
            base_id=base_id.strip(),
            file_bytes=content,
            filename=file.filename or "upload.bin",
        )
        return {"code": 0, "data": data}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e
