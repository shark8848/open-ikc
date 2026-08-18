from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_UPLOAD_DIR = "data/uploads"
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
FILE_ID_PREFIX = "up_"

# 文档域允许暂存的扩展名（大小写不敏感）
ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "md",
    "csv",
    "html",
    "htm",
    "xml",
    "json",
    "yaml",
    "yml",
    "zip",
    "rar",
    "7z",
}


@dataclass
class UploadRecord:
    file_id: str
    file_name: str
    content_type: str
    file_size: int
    owner_id: str
    tenant_id: str
    created_at: str
    expires_at: str
    expires_in: int


def upload_dir() -> Path:
    return Path(os.getenv("OPEN_PLATFORM_UPLOAD_DIR", DEFAULT_UPLOAD_DIR)).resolve()


def ttl_seconds() -> int:
    raw = os.getenv("OPEN_PLATFORM_UPLOAD_TTL_SECONDS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS
    return value if value > 0 else DEFAULT_TTL_SECONDS


def max_bytes() -> int:
    raw = os.getenv("OPEN_PLATFORM_UPLOAD_MAX_BYTES", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES
    return value if value > 0 else DEFAULT_MAX_BYTES


def sanitize_file_name(file_name: str) -> str:
    """清洗原始文件名：仅保留 basename，剔除路径与危险字符。"""
    name = os.path.basename(file_name or "").strip()
    name = name.replace("\\", "").replace("/", "").replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        return "upload.bin"
    return name[:255]


def _file_path(upload_dir: Path, file_id: str) -> Path:
    return upload_dir / file_id


def _sidecar_path(upload_dir: Path, file_id: str) -> Path:
    return upload_dir / f"{file_id}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def save_upload(
    content: bytes,
    *,
    file_name: str,
    content_type: str,
    owner_id: str = "",
    tenant_id: str = "",
) -> UploadRecord:
    """保存暂存文件并返回记录；校验失败抛 ValueError，落盘失败抛 OSError。"""
    purge_expired()

    name = sanitize_file_name(file_name)
    ext = Path(name).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"不支持的文件类型：{ext or '无扩展名'}，仅支持 {allowed}")
    if not content:
        raise ValueError("上传文件内容为空")
    size = len(content)
    limit = max_bytes()
    if size > limit:
        raise ValueError(f"文件大小 {size} 字节超过上限 {limit} 字节")

    file_id = f"{FILE_ID_PREFIX}{secrets.token_hex(16)}"
    now = datetime.now(timezone.utc)
    ttl = ttl_seconds()
    expire_at = now + timedelta(seconds=ttl)
    record = UploadRecord(
        file_id=file_id,
        file_name=name,
        content_type=content_type or "application/octet-stream",
        file_size=size,
        owner_id=owner_id,
        tenant_id=tenant_id,
        created_at=_now_iso(),
        expires_at=expire_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        expires_in=ttl,
    )

    target_dir = upload_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    _file_path(target_dir, file_id).write_bytes(content)
    _sidecar_path(target_dir, file_id).write_text(
        json.dumps(asdict(record), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return record


def load_record(file_id: str) -> UploadRecord | None:
    """读取暂存记录（不做过期判断）；不存在返回 None。"""
    sidecar = _sidecar_path(upload_dir(), file_id)
    if not sidecar.is_file():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return UploadRecord(**payload)


def file_path(file_id: str) -> Path:
    return _file_path(upload_dir(), file_id)


def remove(file_id: str) -> None:
    """删除暂存文件与其元数据侧车。"""
    target_dir = upload_dir()
    for candidate in (_file_path(target_dir, file_id), _sidecar_path(target_dir, file_id)):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def purge_expired() -> int:
    """惰性清理过期暂存文件，返回清理数量。"""
    target_dir = upload_dir()
    if not target_dir.is_dir():
        return 0
    now = datetime.now(timezone.utc)
    cleaned = 0
    for sidecar in target_dir.glob(f"{FILE_ID_PREFIX}*.json"):
        file_id = sidecar.name[: -len(".json")]
        record = load_record(file_id)
        if record is None:
            continue
        try:
            expired_at = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
        except ValueError:
            expired_at = datetime.min.replace(tzinfo=timezone.utc)
        if expired_at <= now:
            remove(file_id)
            cleaned += 1
    return cleaned
