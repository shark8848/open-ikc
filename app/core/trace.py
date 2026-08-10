from __future__ import annotations

import secrets
import time

# 日志中心 SDK（ikc-log-center，pip 安装模式接入）的 contextvars 承载 traceId/requestId：
# - 请求入口由 TraceMiddleware（app_factory 注册）调用 set_trace_context 绑定；
# - 日志记录的 TraceContextFilter 自动把当前 trace_id 附加到日志中，
#   因此同一 traceId 的日志可在日志中心按链路聚合检索。
from log_center_sdk.core import clear_trace_context, request_id_var, set_trace_context, trace_id_var


def _generate_trace_id() -> str:
    timestamp_ms = str(int(time.time() * 1000))
    random_digits = "".join(str(secrets.randbelow(10)) for _ in range(10))
    return f"{timestamp_ms}{random_digits}"


def normalize_trace_id(candidate: str | None) -> str:
    if candidate is not None:
        cleaned = candidate.strip()
        if cleaned.isdigit() and len(cleaned) == 23:
            return cleaned
    return _generate_trace_id()


def set_trace_id(trace_id: str) -> None:
    set_trace_context(trace_id=trace_id, request_id=trace_id)


def get_trace_id() -> str | None:
    return trace_id_var.get()


def current_trace_id() -> str:
    trace_id = trace_id_var.get()
    return trace_id if trace_id is not None else _generate_trace_id()


def bind_trace_context(trace_id: str) -> None:
    set_trace_context(trace_id=trace_id, request_id=trace_id)


def clear_trace() -> None:
    clear_trace_context()


def current_request_id() -> str | None:
    return request_id_var.get()


def build_trace_headers(trace_id: str | None = None) -> dict[str, str]:
    trace_value = normalize_trace_id(trace_id) if trace_id is not None else current_trace_id()
    return {
        "X-Trace-Id": trace_value,
        "X-Request-Id": trace_value,
    }
