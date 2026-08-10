from __future__ import annotations

"""CLI 终端输出渲染：模型 → JSON / 简洁表格。"""

import dataclasses
import json
from typing import Any, Iterable


def _as_dict(obj: Any) -> dict[str, Any]:
    """模型序列化；dict 原样返回，否则优先 to_dict()，兜底 dataclasses.asdict。"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"无法序列化: {type(obj).__name__}")


def render_json(data: Any) -> str:
    """紧凑 JSON 输出（ensure_ascii=False）。"""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def render_table(items: Iterable[dict[str, Any]], columns: list[str]) -> str:
    """将 dict 列表渲染为对齐的文本表格；空表返回 '(empty)'。"""
    rows = [dict(item) for item in items]
    if not rows:
        return "(empty)"
    lines: list[str] = []
    widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            value = str(row.get(col, ""))
            if len(value) > widths[col]:
                widths[col] = len(value)
    header_line = "  ".join(str(col).ljust(widths[col]) for col in columns)
    lines.append(header_line)
    lines.append("  ".join("-" * widths[col] for col in columns))
    for row in rows:
        lines.append("  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))
    return "\n".join(lines)
