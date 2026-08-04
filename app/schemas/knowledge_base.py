from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeMetadataField(BaseModel):
    name: str = Field(..., description="元数据字段名，建议使用英文或拼音标识，需在同一知识库内唯一。")
    type: Literal["string", "number", "integer", "boolean", "date", "datetime", "enum", "object"] = Field(
        ...,
        description="字段类型，决定前端展示、后端校验和可搜索能力。",
    )
    required: bool = Field(False, description="是否必填。为 true 时，创建/更新知识库后录入文档必须提供该字段。")
    description: str = Field("", description="字段业务含义说明，建议写明用途、取值口径和使用边界。")
    defaultValue: Any = Field(None, description="默认值；当外部未传该字段时可使用此值。")
    enum: list[str] = Field(default_factory=list, description="枚举值集合；当 type=enum 时建议填写。")
    pattern: str = Field("", description="正则约束；适用于字符串类字段的格式校验。")
    minLength: int | None = Field(None, description="字符串最小长度。")
    maxLength: int | None = Field(None, description="字符串最大长度。")
    example: Any = Field(None, description="字段示例值，用于文档展示和联调参考。")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "docType",
                "type": "string",
                "required": False,
                "description": "文档类型，例如合同、制度、白皮书。",
                "defaultValue": "合同",
                "enum": ["合同", "制度", "白皮书"],
                "pattern": "",
                "minLength": 0,
                "maxLength": 32,
                "example": "合同",
            }
        }
    )


class KnowledgeBaseCreateRequest(BaseModel):
    kbName: str = Field(..., description="知识库名称，面向用户展示，需在同一组织/租户内尽量唯一。")
    kbType: Literal["personal", "team", "enterprise"] = Field(
        "personal",
        description="知识库类型：personal 个人库、team 团队库、enterprise 企业库。",
    )
    teamId: str = Field(
        "",
        description="团队知识库标识；当 kbType=team 时必填，用于校验团队归属和权限。",
    )
    orgId: str = Field(
        "",
        description="企业知识库组织标识；当 kbType=enterprise 时建议填写，用于租户与组织隔离。",
    )
    kbDesc: str = Field("", description="知识库描述，用于说明业务场景、适用范围和维护责任。")
    bizDomain: str = Field("general", description="业务域标签，例如 hr、finance、customer_service。")
    visibility: Literal["private", "org"] = Field(
        "private",
        description="可见范围：private 表示仅创建者或授权范围内可见，org 表示组织内共享。",
    )
    metadataSchema: list[KnowledgeMetadataField] = Field(
        default_factory=list,
        description="元数据字段定义列表；用于约束知识库录入、检索过滤和权限标签。",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kbName": "产品知识库",
                "kbType": "team",
                "teamId": "team_01",
                "orgId": "",
                "kbDesc": "用于客服问答与知识检索",
                "bizDomain": "customer_service",
                "visibility": "org",
                "metadataSchema": [
                    {
                        "name": "docType",
                        "type": "string",
                        "required": False,
                        "description": "文档类型",
                        "defaultValue": "合同",
                        "enum": ["合同", "制度", "白皮书"],
                        "pattern": "",
                        "minLength": 0,
                        "maxLength": 32,
                        "example": "合同",
                    },
                    {
                        "name": "effectiveDate",
                        "type": "date",
                        "required": False,
                        "description": "文档生效日期",
                        "defaultValue": "",
                        "enum": [],
                        "pattern": "",
                        "minLength": None,
                        "maxLength": None,
                        "example": "2026-08-03",
                    },
                ],
            }
        }
    )

    @model_validator(mode="after")
    def validate_conditional_required_fields(self) -> "KnowledgeBaseCreateRequest":
        if self.kbType == "team" and not self.teamId.strip():
            raise ValueError("kbType=team 时 teamId 必填")
        return self


class KnowledgeBaseUpdateRequest(BaseModel):
    kbId: str = Field(..., description="知识库 ID，更新操作的唯一定位标识。")
    kbName: str = Field("", description="知识库名称；传空字符串表示不修改。")
    kbType: Literal["personal", "team", "enterprise"] = Field(
        "personal",
        description="知识库类型；如发生变更需同步校验 teamId/orgId 与权限边界。",
    )
    teamId: str = Field(
        "",
        description="团队知识库标识；当 kbType=team 时必填。",
    )
    orgId: str = Field(
        "",
        description="企业知识库组织标识；当 kbType=enterprise 时建议填写。",
    )
    kbDesc: str = Field("", description="知识库描述；传空字符串表示不修改。")
    visibility: Literal["private", "org"] = Field(
        "private",
        description="可见范围；若不修改可保持默认值或沿用现有值。",
    )
    metadataSchema: list[KnowledgeMetadataField] = Field(
        default_factory=list,
        description="元数据字段定义列表；为空时表示保持不变。",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kbId": "kb_10001",
                "kbName": "产品知识库-客服版",
                "kbType": "enterprise",
                "teamId": "",
                "orgId": "org_001",
                "kbDesc": "用于客服场景和销售支持",
                "visibility": "org",
                "metadataSchema": [],
            }
        }
    )

    @model_validator(mode="after")
    def validate_conditional_required_fields(self) -> "KnowledgeBaseUpdateRequest":
        if self.kbType == "team" and not self.teamId.strip():
            raise ValueError("kbType=team 时 teamId 必填")
        return self


class KnowledgeBaseMetadataSchemaResponse(BaseModel):
    name: str = Field(..., description="元数据字段名。")
    type: str = Field(..., description="元数据字段类型。")
    required: bool = Field(..., description="是否必填。")
    description: str = Field(..., description="字段业务含义说明。")
    defaultValue: Any = Field(..., description="默认值。")
    enum: list[str] = Field(default_factory=list, description="枚举值集合。")
    pattern: str = Field("", description="格式约束。")
    minLength: int | None = Field(None, description="字符串最小长度。")
    maxLength: int | None = Field(None, description="字符串最大长度。")
    example: Any = Field(None, description="字段示例值。")


class KnowledgeBaseDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbName: str = Field(..., description="知识库名称。")
    kbType: Literal["personal", "team", "enterprise"] = Field(..., description="知识库类型。")
    teamId: str = Field("", description="团队知识库标识。")
    orgId: str = Field("", description="企业知识库组织标识。")
    kbDesc: str = Field("", description="知识库描述。")
    bizDomain: str = Field("general", description="业务域标签。")
    visibility: Literal["private", "org"] = Field(..., description="可见范围。")
    metadataSchema: list[KnowledgeBaseMetadataSchemaResponse] = Field(
        default_factory=list,
        description="元数据字段定义列表。",
    )
    createTime: str | None = Field(None, description="创建时间。")
    updateTime: str | None = Field(None, description="更新时间。")


class KnowledgeBaseResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: KnowledgeBaseDataResponse = Field(..., description="业务数据。")


class KnowledgeBaseErrorResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: dict[str, str] = Field(default_factory=dict, description="错误扩展信息。")


class KnowledgeBaseQueryRequest(BaseModel):
    kbType: Literal["personal", "team", "enterprise"] | None = Field(
        None,
        description="按知识库类型过滤；不传表示全部类型。",
    )
    teamId: str = Field(
        "",
        description="团队知识库标识；查看 team 库时必填，用于成员范围收敛。",
    )
    orgId: str = Field(
        "",
        description="企业知识库组织标识；查看 enterprise 库时建议填写，为空时使用调用主体租户。",
    )
    ownerId: str = Field(
        "",
        description="个人库创建者过滤；个人库始终按调用方身份收敛，此字段仅作展示语义。",
    )
    keyword: str = Field("", description="按知识库名称或描述关键字过滤。")
    page: int = Field(1, ge=1, description="页码，从 1 开始。")
    pageSize: int = Field(20, ge=1, le=100, description="每页条数，最大 100。")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kbType": "enterprise",
                "teamId": "",
                "orgId": "org_001",
                "ownerId": "",
                "keyword": "客服",
                "page": 1,
                "pageSize": 20,
            }
        }
    )


class KnowledgeBaseQueryData(BaseModel):
    total: int = Field(..., description="命中总数。")
    page: int = Field(..., description="当前页码。")
    pageSize: int = Field(..., description="每页条数。")
    items: list[KnowledgeBaseDataResponse] = Field(default_factory=list, description="知识库列表。")


class KnowledgeBaseQueryResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: KnowledgeBaseQueryData = Field(..., description="业务数据。")
