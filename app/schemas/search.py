from __future__ import annotations

from pydantic import BaseModel, Field


class SearchQueryRequest(BaseModel):
    query: str = Field("", description="检索问题或关键词。")
    kbId: str = Field("", description="目标知识库 ID。用于数据权限资源匹配。")
    kbIds: list[str] = Field(default_factory=list, description="目标知识库 ID 列表。用于多库联合检索的数据权限判定。")
    ownerId: str = Field("", description="资源所有者 ID。用于 owner_only 场景判定。")
    orgPath: str = Field("", description="组织路径，如 /集团/销售中心/华东。用于组织范围判定。")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "2026 产品白皮书的核心能力是什么？",
                "kbId": "kb_10001",
                "kbIds": ["kb_10001", "kb_10002"],
                "ownerId": "u100",
                "orgPath": "/集团/销售中心/华东",
            }
        }
    }
