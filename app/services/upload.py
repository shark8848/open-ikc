from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.error_codes import CommonErrorCodes, DocumentErrorCodes, DocumentException
from app.core.responses import document_upload_response
from app.services.upload_store import UploadRecord, file_path, load_record, remove, save_upload


UPLOAD_PATH = "/api/v1/knowledge-documents/upload"


class UploadService:
    """文档 7 天暂存服务：上传落盘、临时地址访问、过期清理。"""

    @staticmethod
    def upload_file(
        content: bytes,
        *,
        file_name: str,
        content_type: str,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict:
        try:
            record = save_upload(
                content,
                file_name=file_name,
                content_type=content_type,
                owner_id=owner_id,
                tenant_id=tenant_id,
            )
        except ValueError as exc:
            raise DocumentException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "file", "reason": str(exc)},
            ) from exc
        except OSError as exc:
            raise DocumentException(
                DocumentErrorCodes.UPLOAD_FAILED,
                {"field": "file", "reason": f"暂存文件落盘失败：{exc}"},
            ) from exc
        return document_upload_response(record)

    @staticmethod
    def get_staged_file(file_id: str, *, owner_id: str = "") -> tuple[Path, UploadRecord]:
        record = load_record(file_id)
        if record is None:
            raise DocumentException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "fileId", "reason": f"暂存文件不存在：{file_id}"},
            )
        if record.owner_id != owner_id:
            raise DocumentException(
                CommonErrorCodes.FORBIDDEN,
                {"field": "fileId", "reason": "暂存文件仅创建者可访问"},
            )
        now = datetime.now(timezone.utc)
        try:
            expired_at = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
        except ValueError:
            expired_at = datetime.min.replace(tzinfo=timezone.utc)
        if expired_at <= now:
            remove(file_id)
            raise DocumentException(
                DocumentErrorCodes.STAGED_FILE_EXPIRED,
                {"field": "fileId", "reason": "暂存文件已过期，请重新上传"},
            )
        path = file_path(file_id)
        if not path.is_file():
            raise DocumentException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "fileId", "reason": "暂存文件不存在或已被清理"},
            )
        return path, record
