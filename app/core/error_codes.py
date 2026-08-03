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
            "code": self.code,
            "message": self.message,
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


class KnowledgeBaseErrorCodes(BaseErrorCodes):
    CREATE_FAILED = ErrorCode("200001", "创建知识库失败", level="business", description="知识库创建业务处理失败")
    UPDATE_FAILED = ErrorCode("200002", "修改知识库失败", level="business", description="知识库更新业务处理失败")

    @classmethod
    def registry(cls) -> list[ErrorCode]:
        return super().registry() + [cls.CREATE_FAILED, cls.UPDATE_FAILED]


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
    for error_code in BaseErrorCodes.registry() + KnowledgeBaseErrorCodes.registry():
        if error_code.code in seen:
            continue
        seen.add(error_code.code)
        catalog.append(error_code.to_dict())
    return catalog


def get_error_code(code: str) -> ErrorCode | None:
    for error_code in error_code_catalog():
        if error_code["code"] == code:
            return ErrorCode(
                error_code["code"],
                error_code["message"],
                level=error_code["level"],
                description=error_code["description"],
            )
    return None

