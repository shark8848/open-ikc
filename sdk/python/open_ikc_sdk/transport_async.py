from __future__ import annotations

import json
from typing import Any

import httpx

from .envelope import Envelope
from .errors import (
    OpenIKCConnectionError,
    OpenIKCHTTPStatusError,
    OpenIKCTimeoutError,
)
from .headers import CallerIdentity, build_headers
from .trace import ensure_trace_id
from .transport import (
    DownloadPayload,
    _RETRYABLE_STATUS_CODES,
    _download_payload,
    build_url,
    can_retry,
    handle_response,
    backoff_delay,
    resolve_timeout,
)


class AsyncTransport:
    """异步 HTTP 传输：与同步 Transport 共享超时、重试、统一壳解析与异常映射。"""

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        timeout: tuple[float, float] | float | None = None,
        max_retries: int = 2,
        identity: CallerIdentity | None = None,
        extra_headers: dict[str, str] | None = None,
        trace_id: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = resolve_timeout(timeout)
        self._max_retries = max(0, max_retries)
        self._identity = identity
        self._extra_headers = dict(extra_headers or {})
        self._fixed_trace_id = trace_id
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=self._timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        raise_for_error: bool = True,
    ) -> Envelope:
        url = build_url(self._base_url, path, path_params)
        trace_id = ensure_trace_id(self._fixed_trace_id)
        headers = build_headers(
            token=self._token,
            trace_id=trace_id,
            identity=self._identity,
            extra_headers=self._extra_headers,
        )
        response = await self._send(method, url, params=params, body=body, headers=headers, trace_id=trace_id)
        return handle_response(response, trace_id=trace_id, raise_for_error=raise_for_error)

    async def get_json(self, path: str) -> Any:
        url = self._base_url + path
        trace_id = ensure_trace_id(self._fixed_trace_id)
        headers = build_headers(
            token=self._token,
            trace_id=trace_id,
            identity=self._identity,
            extra_headers=self._extra_headers,
        )
        response = await self._send("GET", url, params=None, body=None, headers=headers, trace_id=trace_id)
        if response.status_code >= 400:
            raise OpenIKCHTTPStatusError(
                f"HTTP {response.status_code}: GET {url}",
                status_code=response.status_code,
                body=response.text,
                trace_id=trace_id,
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise OpenIKCHTTPStatusError(
                f"HTTP {response.status_code} 响应不是合法 JSON",
                status_code=response.status_code,
                body=response.text,
                trace_id=trace_id,
            ) from exc

    async def download(self, path: str, *, params: dict[str, Any] | None = None) -> DownloadPayload:
        url = self._base_url + path
        trace_id = ensure_trace_id(self._fixed_trace_id)
        headers = build_headers(
            token=self._token,
            trace_id=trace_id,
            identity=self._identity,
            extra_headers=self._extra_headers,
        )
        headers["Accept"] = "*/*"
        response = await self._send("GET", url, params=params, body=None, headers=headers, trace_id=trace_id)
        return _download_payload(response, trace_id=trace_id)

    async def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        headers: dict[str, str],
        trace_id: str,
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, url, params=params, json=body, headers=headers)
            except httpx.TimeoutException as exc:
                if not can_retry(method, body) or attempt >= self._max_retries:
                    raise OpenIKCTimeoutError(f"请求超时: {method} {url}", trace_id=trace_id) from exc
                await _sleep_async(attempt)
                continue
            except httpx.ConnectError as exc:
                if not can_retry(method, body) or attempt >= self._max_retries:
                    raise OpenIKCConnectionError(f"连接失败: {method} {url}", trace_id=trace_id) from exc
                await _sleep_async(attempt)
                continue
            except httpx.HTTPError as exc:
                raise OpenIKCConnectionError(f"传输失败: {method} {url}: {exc}", trace_id=trace_id) from exc
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries and can_retry(method, body):
                await _sleep_async(attempt)
                continue
            return response
        raise OpenIKCConnectionError(f"重试耗尽: {method} {url}", trace_id=trace_id)


async def _sleep_async(attempt: int) -> None:
    import asyncio

    await asyncio.sleep(backoff_delay(attempt))
