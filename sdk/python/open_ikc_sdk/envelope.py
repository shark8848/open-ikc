from __future__ import annotations

import json
from dataclasses import dataclass, field

from .errors import OpenIKCProtocolError

SUCCESS_CODE = "000000"


@dataclass
class Envelope:
    """统一响应壳：errCode / errMsg / data / traceId。"""

    err_code: str
    err_msg: str
    data: dict = field(default_factory=dict)
    trace_id: str = ""

    @property
    def ok(self) -> bool:
        return self.err_code == SUCCESS_CODE


def parse_envelope(text: str) -> Envelope:
    """解析统一响应壳；不符合协议时抛 OpenIKCProtocolError。"""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenIKCProtocolError("响应不是合法 JSON，不符合统一响应壳协议") from exc
    if not isinstance(payload, dict) or "errCode" not in payload:
        raise OpenIKCProtocolError("响应缺少 errCode，不符合统一响应壳协议")
    data = payload.get("data")
    return Envelope(
        err_code=str(payload.get("errCode", "")),
        err_msg=str(payload.get("errMsg", "")),
        data=data if isinstance(data, dict) else {},
        trace_id=str(payload.get("traceId", "")),
    )
