from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from markdown_it import MarkdownIt

_MANUAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "API开发手册.md"

_MD = MarkdownIt("commonmark", {"html": False}).enable("table")


@lru_cache(maxsize=1)
def _render_md(mtime_ns: int, size: int) -> str:
    return _MD.render(_MANUAL_PATH.read_text(encoding="utf-8"))


def render_api_manual_html() -> str:
    """将 docs/API开发手册.md 渲染为离线可用的中文文档页（服务端渲染，无外部依赖）。"""
    if not _MANUAL_PATH.exists():
        return "<!doctype html><html lang='zh-CN'><body><h1>开发手册缺失</h1></body></html>"
    stat = _MANUAL_PATH.stat()
    body = _render_md(stat.st_mtime_ns, stat.st_size)
    return f"""
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>开放平台 API 开发手册</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b1020; color: #e8eefc; line-height: 1.7; }}
          .wrap {{ max-width: 1080px; margin: 0 auto; padding: 40px 20px 80px; }}
          .hero {{ background: linear-gradient(135deg, #182548, #0f1b34); border: 1px solid #263457; border-radius: 20px; padding: 28px 32px; }}
          .hero h1 {{ margin: 0 0 8px; }}
          .hero p {{ margin: 0; color: #a8b6d8; }}
          .links {{ margin-top: 16px; }}
          .links a {{ display: inline-block; margin-right: 16px; color: #8dc1ff; text-decoration: none; }}
          .links a:hover {{ text-decoration: underline; }}
          article {{ margin-top: 24px; padding: 8px 24px 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; }}
          h1, h2, h3, h4 {{ color: #f2f6ff; margin-top: 1.6em; }}
          article h1 {{ font-size: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 8px; }}
          article h2 {{ font-size: 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; }}
          a {{ color: #8dc1ff; }}
          code {{ background: rgba(255,255,255,0.09); padding: 2px 6px; border-radius: 6px; font-size: 0.9em; }}
          pre {{ background: #0d1428; border: 1px solid #263457; border-radius: 12px; padding: 14px 16px; overflow-x: auto; }}
          pre code {{ background: none; padding: 0; }}
          table {{ border-collapse: collapse; width: 100%; margin: 14px 0; display: block; overflow-x: auto; }}
          th, td {{ border: 1px solid #2a3552; padding: 8px 12px; text-align: left; vertical-align: top; }}
          th {{ background: rgba(141,193,255,0.1); }}
          blockquote {{ margin: 12px 0; padding: 4px 16px; border-left: 3px solid #8dc1ff; background: rgba(141,193,255,0.06); border-radius: 0 10px 10px 0; }}
          hr {{ border: none; border-top: 1px solid #263457; margin: 28px 0; }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="hero">
            <h1>开放平台 API 开发手册</h1>
            <p>接口定义、鉴权、SDK / MCP / CLI 接入与常见错误排查。</p>
            <div class="links">
              <a href="/portal/">管理 Portal</a>
              <a href="/docs">Swagger UI</a>
              <a href="/redoc">ReDoc</a>
              <a href="/openapi.json">OpenAPI JSON</a>
              <a href="/api-browser">API 浏览</a>
            </div>
          </div>
          <article>{body}</article>
        </div>
      </body>
    </html>
    """
