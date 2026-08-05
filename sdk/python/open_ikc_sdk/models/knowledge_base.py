from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeMetadataField:
    """元数据字段定义（对应平台 metadataSchema[]）。"""

    name: str
    type: str
    required: bool = False
    description: str = ""
    defaultValue: Any = None
    enum: list[str] = field(default_factory=list)
    pattern: str = ""
    minLength: int | None = None
    maxLength: int | None = None
    example: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeMetadataField":
        return cls(
            name=str(data.get("name", "")),
            type=str(data.get("type", "")),
            required=bool(data.get("required", False)),
            description=str(data.get("description", "")),
            defaultValue=data.get("defaultValue"),
            enum=list(data.get("enum") or []),
            pattern=str(data.get("pattern", "")),
            minLength=data.get("minLength"),
            maxLength=data.get("maxLength"),
            example=data.get("example"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "defaultValue": self.defaultValue,
            "enum": list(self.enum),
            "pattern": self.pattern,
            "minLength": self.minLength,
            "maxLength": self.maxLength,
            "example": self.example,
        }


_KNOWLEDGE_BASE_FIELDS = {
    "kbId",
    "kbName",
    "kbType",
    "teamId",
    "orgId",
    "kbDesc",
    "bizDomain",
    "visibility",
    "metadataSchema",
    "createTime",
    "updateTime",
}


@dataclass
class KnowledgeBase:
    """知识库信息（对应平台 KnowledgeBaseDataResponse）。"""

    kbId: str
    kbName: str
    kbType: str = "personal"
    teamId: str = ""
    orgId: str = ""
    kbDesc: str = ""
    bizDomain: str = "general"
    visibility: str = "private"
    metadataSchema: list[KnowledgeMetadataField] = field(default_factory=list)
    createTime: str | None = None
    updateTime: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeBase":
        schema_items = [
            KnowledgeMetadataField.from_dict(item)
            for item in (data.get("metadataSchema") or [])
            if isinstance(item, dict)
        ]
        return cls(
            kbId=str(data.get("kbId", "")),
            kbName=str(data.get("kbName", "")),
            kbType=str(data.get("kbType", "personal")),
            teamId=str(data.get("teamId", "")),
            orgId=str(data.get("orgId", "")),
            kbDesc=str(data.get("kbDesc", "")),
            bizDomain=str(data.get("bizDomain", "general")),
            visibility=str(data.get("visibility", "private")),
            metadataSchema=schema_items,
            createTime=data.get("createTime"),
            updateTime=data.get("updateTime"),
            extra={key: value for key, value in data.items() if key not in _KNOWLEDGE_BASE_FIELDS},
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kbId": self.kbId,
            "kbName": self.kbName,
            "kbType": self.kbType,
            "teamId": self.teamId,
            "orgId": self.orgId,
            "kbDesc": self.kbDesc,
            "bizDomain": self.bizDomain,
            "visibility": self.visibility,
            "metadataSchema": [item.to_dict() for item in self.metadataSchema],
            "createTime": self.createTime,
            "updateTime": self.updateTime,
        }
        result.update(self.extra)
        return result


@dataclass
class KnowledgeBasePage:
    """知识库分页查询结果（对应平台 KnowledgeBaseQueryData）。"""

    total: int
    page: int
    pageSize: int
    items: list[KnowledgeBase] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeBasePage":
        return cls(
            total=int(data.get("total") or 0),
            page=int(data.get("page") or 1),
            pageSize=int(data.get("pageSize") or 20),
            items=[
                KnowledgeBase.from_dict(item)
                for item in (data.get("items") or [])
                if isinstance(item, dict)
            ],
        )
