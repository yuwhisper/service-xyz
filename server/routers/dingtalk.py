from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.dingtalk.dingpan import upload_directory_as_zip, upload_file

router = APIRouter(prefix="/service/zyx/dingtalk", tags=["dingtalk"])


class DingpanUploadBody(BaseModel):
    local_path: str = Field(..., description="服务器本地文件或目录路径")
    as_zip: bool = Field(default=False, description="目录时先压缩再上传")
    save_name: str | None = Field(default=None, description="钉盘保存名，目录默认 {目录名}.zip")
    folder_url: str | None = Field(default=None, description="钉盘文件夹复制链接")
    space_id: str | None = None
    parent_folder_id: str | None = None


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
