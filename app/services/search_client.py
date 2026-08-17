from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.core.error_codes import CommonErrorCodes, SearchErrorCodes, SearchException
from app.core.trace import build_trace_headers

UR_SYNC_PATH = "/retrieval/search/sync"
OPENAI_VECTOR_SEARCH_PATH = "/VectorSearchV2"
OPENAI_DEEP_SEARCH_PATH = "/DeepSearch"

_VALID_BACKENDS = {"in_process", "ur", "openai"}
_OPENAI_SEARCH_TYPE = {"fulltext": 0, "vector": 1, "hybrid": 2}


def search_backend() -> str:
    """下游检索后端开关：in_process（占位/测试）/ ur / openai。"""
    return os.getenv("OPEN_PLATFORM_SEARCH_BACKEND", "in_process").strip().lower()


def ur_base_url() -> str:
    return os.getenv("OPEN_PLATFORM_UR_BASE_URL", "http://127.0.0.1:8096").strip().rstrip("/")


def openai_base_url() -> str:
    default = "http://127.0.0.1:8088/km/search-api/aiTools/openai/bsapi"
    return os.getenv("OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL", default).strip().rstrip("/")


def search_timeout_seconds() -> float:
    return _env_float("OPEN_PLATFORM_SEARCH_TIMEOUT_SECONDS", 10.0)


def deep_search_timeout_seconds() -> float:
    return _env_float("OPEN_PLATFORM_DEEP_SEARCH_TIMEOUT_SECONDS", 60.0)


def kb_index_map() -> dict[str, str]:
    """kb_id → index 显式映射（环境变量 OPEN_PLATFORM_KB_INDEX_MAP 为 JSON 对象）。"""
    raw = os.getenv("OPEN_PLATFORM_KB_INDEX_MAP", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {str(key): str(value) for key, value in parsed.items()} if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


def resolve_index(kb_ids: list[str]) -> str | None:
    """按 kb_id 显式映射解析目标索引；多库且映射不一致时交由下游 collocation 解析。"""
    mapping = kb_index_map()
    if not mapping:
        return None
    indexes = {mapping.get(kb_id) for kb_id in kb_ids if mapping.get(kb_id)}
    if len(indexes) == 1:
        return indexes.pop()
    return None


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> httpx.Response:
    return httpx.post(url, json=payload, headers=headers, timeout=timeout)


def _raise_failed(provider: str, detail: str) -> None:
    raise SearchException(
        SearchErrorCodes.SEARCH_FAILED,
        {"field": "downstream", "provider": provider, "reason": detail},
    )


def _check_success(provider: str, status_code: int, body: Any) -> None:
    if status_code >= 400:
        _raise_failed(provider, f"下游返回 HTTP {status_code}")
    if not isinstance(body, dict):
        _raise_failed(provider, "下游返回非 JSON 对象")
    err_code = str(body.get("errCode") or body.get("code") or "000000")
    status = body.get("status", True)
    if err_code not in {"000000", "0"} or status is False or str(status).lower() == "false":
        _raise_failed(provider, f"下游业务失败：{body.get('errMsg') or err_code}")


def ur_search_sync(payload: dict[str, Any], *, trace_id: str, timeout: float | None = None) -> dict[str, Any]:
    """调用 universal_retriever 同步检索，返回 RetrievalResponse（原始 JSON）。"""
    url = f"{ur_base_url()}{UR_SYNC_PATH}"
    headers = {**build_trace_headers(trace_id), "X-Request-Id": trace_id}
    try:
        response = _post_json(url, headers, payload, timeout or search_timeout_seconds())
    except httpx.HTTPError as exc:
        _raise_failed("universal_retriever", f"调用失败：{exc}")
    _check_success("universal_retriever", response.status_code, response.json())
    return response.json()


def openai_vector_search(payload: dict[str, Any], *, trace_id: str, timeout: float | None = None) -> dict[str, Any]:
    """调用 openai_search_service 基础检索（VectorSearchV2），返回 MultiModalRagSearchResponse。"""
    url = f"{openai_base_url()}{OPENAI_VECTOR_SEARCH_PATH}"
    headers = {**build_trace_headers(trace_id), "X-Request-Id": trace_id}
    try:
        response = _post_json(url, headers, payload, timeout or search_timeout_seconds())
    except httpx.HTTPError as exc:
        _raise_failed("openai_search_service", f"调用失败：{exc}")
    _check_success("openai_search_service", response.status_code, response.json())
    return response.json()


def openai_deep_search(payload: dict[str, Any], *, trace_id: str, timeout: float | None = None) -> dict[str, Any]:
    """调用 openai_search_service DeepSearch，返回 DeepSearchResponse。

    下游 DeepSearch 未启用（HTTP 403）映射为 501001，提示能力未启用。
    """
    url = f"{openai_base_url()}{OPENAI_DEEP_SEARCH_PATH}"
    headers = {**build_trace_headers(trace_id), "X-Request-Id": trace_id}
    try:
        response = _post_json(url, headers, payload, timeout or deep_search_timeout_seconds())
    except httpx.HTTPError as exc:
        _raise_failed("openai_search_service.deep_search", f"调用失败：{exc}")
    if response.status_code == 403:
        raise SearchException(
            CommonErrorCodes.NOT_IMPLEMENTED,
            {"field": "deepSearch", "reason": "下游 DeepSearch 未启用，请检查 OPENAI_SEARCH_ENABLE_DEEPSEARCH"},
            message="深度检索未启用：下游 DeepSearch 关闭（OPENAI_SEARCH_ENABLE_DEEPSEARCH）",
        )
    _check_success("openai_search_service.deep_search", response.status_code, response.json())
    return response.json()


def openai_search_type(search_type: str) -> int:
    return _OPENAI_SEARCH_TYPE.get((search_type or "hybrid").strip().lower(), 2)


def validate_backend(backend: str) -> None:
    if backend not in _VALID_BACKENDS:
        raise SearchException(
            CommonErrorCodes.INVALID_PARAMS,
            {"field": "OPEN_PLATFORM_SEARCH_BACKEND", "reason": f"仅支持 {sorted(_VALID_BACKENDS)}"},
        )
