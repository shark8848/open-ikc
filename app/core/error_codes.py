from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorCode:
    code: str
    message: str
    level: str = "business"
    description: str = ""

    def to_response(self, data: Any | None = None, message: str | None = None) -> dict[str, Any]:
        return {
            "errCode": self.code,
            "errMsg": self.message if message is None else message,
            "data": {} if data is None else data,
        }

    def as_exception(self, data: Any | None = None, message: str | None = None) -> "AppException":
        return AppException(self, data=data, message=message)

    def to_dict(self) -> dict[str, str]:
        return {
            "errCode": self.code,
            "errMsg": self.message,
            "level": self.level,
            "description": self.description,
        }


class AppException(Exception):
    def __init__(self, error: ErrorCode, data: Any | None = None, message: str | None = None) -> None:
        super().__init__(error.message if message is None else message)
        self.error = error
        self.data = {} if data is None else data
        self.message = error.message if message is None else message

    def to_response(self) -> dict[str, Any]:
        return self.error.to_response(self.data, self.message)


class CommonException(AppException):
    pass


class KnowledgeBaseException(AppException):
    pass


class DocumentException(AppException):
    pass


class ParseException(AppException):
    pass


class SearchException(AppException):
    pass


class BaseErrorCodes:
    SUCCESS = ErrorCode("000000", "success", level="success", description="请求处理成功")
    INVALID_PARAMS = ErrorCode("100001", "参数校验失败", level="parameter", description="请求参数缺失、类型错误或校验失败")
    UNAUTHORIZED = ErrorCode("100401", "未认证或认证失败", level="auth", description="调用方未通过认证")
    FORBIDDEN = ErrorCode("100403", "无权限访问", level="authz", description="调用方无权限或发生越权访问")
    NOT_FOUND = ErrorCode("100404", "资源不存在", level="resource", description="目标资源不存在或已被删除")
    METHOD_NOT_ALLOWED = ErrorCode("100405", "请求方法不允许", level="framework", description="请求路径存在但 HTTP 方法不被支持")
    CONFLICT = ErrorCode("100409", "资源冲突", level="resource", description="资源重复创建或状态冲突")
    NOT_IMPLEMENTED = ErrorCode("501001", "接口已预占位，待实现", level="placeholder", description="当前仅提供框架占位")
    INTERNAL_ERROR = ErrorCode("999999", "系统内部错误", level="system", description="不可预期的系统异常")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return [
            cls.SUCCESS,
            cls.INVALID_PARAMS,
            cls.UNAUTHORIZED,
            cls.FORBIDDEN,
            cls.NOT_FOUND,
            cls.METHOD_NOT_ALLOWED,
            cls.CONFLICT,
            cls.NOT_IMPLEMENTED,
            cls.INTERNAL_ERROR,
        ]

    @classmethod
    def get_by_code(cls, code: str) -> ErrorCode | None:
        for error_code in cls.registry():
            if error_code.code == code:
                return error_code
        return None


class CommonErrorCodes(BaseErrorCodes):
    pass


class AdminErrorCodes(BaseErrorCodes):
    """管理面（/admin/*）专属错误码，见 AGENTS.md §4.3。"""

    ADMIN_DISABLED = ErrorCode("503001", "管理面未启用", level="admin", description="未配置 OPEN_PLATFORM_ADMIN_TOKEN，管理面默认关闭")
    TEST_FAILED = ErrorCode("200020", "在线测试执行失败", level="admin", description="MCP / CLI 在线测试执行未通过")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.ADMIN_DISABLED, cls.TEST_FAILED]


class KnowledgeBaseErrorCodes(BaseErrorCodes):
    CREATE_FAILED = ErrorCode("200001", "创建知识库失败", level="business", description="知识库创建业务处理失败")
    UPDATE_FAILED = ErrorCode("200002", "修改知识库失败", level="business", description="知识库更新业务处理失败")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.CREATE_FAILED, cls.UPDATE_FAILED]


class DocumentErrorCodes(BaseErrorCodes):
    INGEST_FAILED = ErrorCode("200010", "接入知识源失败", level="business", description="文档接入知识源业务处理失败")
    UPLOAD_FAILED = ErrorCode("200012", "文档上传失败", level="business", description="文档暂存上传业务处理失败（落盘失败等）")
    STAGED_FILE_EXPIRED = ErrorCode("200013", "暂存文件不存在或已过期", level="business", description="暂存文件不存在、已过期或已被清理")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.INGEST_FAILED, cls.UPLOAD_FAILED, cls.STAGED_FILE_EXPIRED]


class ParseErrorCodes(BaseErrorCodes):
    RESULT_NOT_READY = ErrorCode("200003", "解析结果尚未就绪", level="business", description="文档尚未完成解析或不存在解析产物")
    TICKET_INVALID = ErrorCode("200004", "下载凭证无效或已过期", level="business", description="下载凭证不存在、无效或已过期")
    PARSE_FAILED = ErrorCode("200011", "解析失败", level="business", description="文档解析业务处理失败")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.RESULT_NOT_READY, cls.TICKET_INVALID, cls.PARSE_FAILED]


class SearchErrorCodes(BaseErrorCodes):
    SEARCH_FAILED = ErrorCode("300001", "检索执行失败", level="business", description="下游检索引擎执行失败（超时/连接失败/返回非成功状态）")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.SEARCH_FAILED]


def error_response(error: ErrorCode, data: Any | None = None, message: str | None = None) -> dict[str, Any]:
    return error.to_response(data, message)


def raise_not_implemented(category: str, action: str, path: str) -> AppException:
    return AppException(
        BaseErrorCodes.NOT_IMPLEMENTED,
        {"category": category, "action": action, "path": path},
        message=f"{category} / {action} 接口已预占位，待实现",
    )


def exception_from_code(error: ErrorCode, data: Any | None = None, message: str | None = None) -> AppException:
    return error.as_exception(data=data, message=message)


def error_code_catalog() -> list[dict[str, str]]:
    seen: set[str] = set()
    catalog: list[dict[str, str]] = []
    for error_code in (
        BaseErrorCodes.registry()
        + KnowledgeBaseErrorCodes.registry()
        + DocumentErrorCodes.registry()
        + ParseErrorCodes.registry()
        + SearchErrorCodes.registry()
        + AdminErrorCodes.registry()
    ):
        if error_code.code in seen:
            continue
        seen.add(error_code.code)
        catalog.append(error_code.to_dict())
    return catalog


def get_error_code(code: str) -> ErrorCode | None:
    for error_code in error_code_catalog():
        if error_code["errCode"] == code:
            return ErrorCode(
                error_code["errCode"],
                error_code["errMsg"],
                level=error_code["level"],
                description=error_code["description"],
            )
    return None
