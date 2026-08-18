from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentSource(BaseModel):
    """统一来源对象：接入（ingest）与免库独立解析（parse-direct）共用。"""

    type: Literal["url", "file", "directory", "archive"] = Field(
        "file",
        description="来源类型：url 链接抓取、file 文件对象、directory 目录对象、archive 压缩包对象。",
    )
    url: str = Field("", description="来源 URL；当 type=url 时必填。")
    objectKey: str = Field("", description="文件/目录/压缩包对象标识，如 OSS 对象路径。")
    fileToken: str = Field("", description="文件上传凭证或临时对象标识；与 objectKey 二选一。")
    archive: dict = Field(
        default_factory=dict,
        description="压缩包配置：format（zip/7z/tar/tar.gz）、passwordRef、includePattern、excludePattern，透传。",
    )
    directory: dict = Field(
        default_factory=dict,
        description="目录配置：recursive（是否递归目录）等，透传。",
    )
    metadata: dict = Field(default_factory=dict, description="来源元信息，如来源系统、上传人、原始文件名等。")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "url",
                "url": "https://example.com/files/spec.pdf",
                "objectKey": "",
                "fileToken": "",
                "archive": {},
                "directory": {},
                "metadata": {},
            }
        }
    )
