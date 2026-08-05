from __future__ import annotations

from typing import Any


class OpenIKCError(Exception):
    """SDK 所有异常基类。"""


class OpenIKCTransportError(OpenIKCError):
    """传输层异常：连接、超时、非预期 HTTP 状态。"""

    def __init__(self, message: str, *, trace_id: str = "") -> None:
        super().__init__(message)
        self.trace_id = trace_id


class OpenIKCConnectionError(OpenIKCTransportError):
    """无法建立连接。"""


class OpenIKCTimeoutError(OpenIKCTransportError):
    """请求超时。"""


class OpenIKCProtocolError(OpenIKCTransportError):
    """响应不符合统一响应壳协议。"""


class OpenIKCHTTPStatusError(OpenIKCTransportError):
    """非 2xx 且无法解析统一响应壳。"""

    def __init__(self, message: str, *, status_code: int, body: str = "", trace_id: str = "") -> None:
        super().__init__(message, trace_id=trace_id)
        self.status_code = status_code
        self.body = body


class OpenIKCAPIError(OpenIKCError):
    """平台返回统一响应壳但 errCode != 000000。"""

    def __init__(self, message: str, *, err_code: str, err_msg: str, trace_id: str = "") -> None:
        super().__init__(message)
        self.err_code = err_code
        self.err_msg = err_msg
        self.trace_id = trace_id


class OpenIKCValidationError(OpenIKCAPIError):
    """参数校验失败（100001）。"""


class OpenIKCUnauthorizedError(OpenIKCAPIError):
    """未认证或认证失败（100401）。"""


class OpenIKCForbiddenError(OpenIKCAPIError):
    """无权限访问（100403）。"""


class OpenIKCNotFoundError(OpenIKCAPIError):
    """资源不存在（100404）。"""


class OpenIKCMethodNotAllowedError(OpenIKCAPIError):
    """请求方法不允许（100405）。"""


class OpenIKCConflictError(OpenIKCAPIError):
    """资源冲突（100409）。"""


class OpenIKCNotImplementedError(OpenIKCAPIError):
    """平台接口占位未实现（501001）。"""


class OpenIKCSystemError(OpenIKCAPIError):
    """平台系统内部错误（999999）。"""


class OpenIKCBusinessError(OpenIKCAPIError):
    """2xxxxx 业务错误或未知错误码。"""


_ERROR_CODE_CLASSES: dict[str, type[OpenIKCAPIError]] = {
    "100001": OpenIKCValidationError,
    "100401": OpenIKCUnauthorizedError,
    "100403": OpenIKCForbiddenError,
    "100404": OpenIKCNotFoundError,
    "100405": OpenIKCMethodNotAllowedError,
    "100409": OpenIKCConflictError,
    "501001": OpenIKCNotImplementedError,
    "999999": OpenIKCSystemError,
}


def exception_from_code(err_code: str, err_msg: str, trace_id: str = "") -> OpenIKCAPIError:
    """按错误码生成对应异常；未知错误码映射为 OpenIKCBusinessError。"""
    error_class = _ERROR_CODE_CLASSES.get(err_code, OpenIKCBusinessError)
    return error_class(f"{err_code} {err_msg}".strip(), err_code=err_code, err_msg=err_msg, trace_id=trace_id)
