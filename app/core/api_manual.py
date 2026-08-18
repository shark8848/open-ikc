from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

_MANUAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "API开发手册.md"

_MD = MarkdownIt("commonmark", {"html": False}).enable("table")


def _heading_plain_text(inline: Token) -> str:
    """从标题的 inline token 提取纯文本（去掉反引号/链接等标记）。"""
    if not inline.children:
        return inline.content
    return "".join(
        child.content for child in inline.children if child.type in ("text", "code_inline")
    )


def _render_with_toc(markdown_text: str) -> tuple[str, list[dict[str, str]]]:
    """渲染 markdown，并为 h2/h3 标题注入锚点 id；返回 (body_html, 目录项)。"""
    tokens = _MD.parse(markdown_text)
    toc_items: list[dict[str, str]] = []
    seq = 0
    for tok in tokens:
        if tok.type == "heading_open" and tok.tag in ("h2", "h3"):
            seq += 1
            anchor = f"sec-{seq}"
            tok.attrSet("id", anchor)
            toc_items.append({"id": anchor, "tag": tok.tag, "text": ""})
        elif tok.type == "inline" and toc_items and not toc_items[-1]["text"]:
            # heading_open 之后紧跟的 inline token 即标题内容
            toc_items[-1]["text"] = _heading_plain_text(tok)
    body = _MD.renderer.render(tokens, _MD.options, {})
    return body, toc_items


def _render_toc_html(items: list[dict[str, str]]) -> str:
    """生成侧边目录导航（h2 一级、h3 缩进二级）。"""
    if not items:
        return ""
    lis: list[str] = []
    for item in items:
        cls = "toc-h2" if item["tag"] == "h2" else "toc-h3"
        anchor = item["id"]
        text = item["text"]
        lis.append(f'<li class="{cls}"><a href="#{anchor}">{text}</a></li>')
    return (
        '<nav class="toc" aria-label="目录">'
        '<div class="toc-title">目录</div>'
        f"<ul>{''.join(lis)}</ul>"
        "</nav>"
    )


@lru_cache(maxsize=1)
def _render_md(mtime_ns: int, size: int) -> tuple[str, list[dict[str, str]]]:
    return _render_with_toc(_MANUAL_PATH.read_text(encoding="utf-8"))


def render_api_manual_html() -> str:
    """将 docs/API开发手册.md 渲染为离线可用的中文文档页（服务端渲染，无外部依赖）。"""
    if not _MANUAL_PATH.exists():
        return "<!doctype html><html lang='zh-CN'><body><h1>开发手册缺失</h1></body></html>"
    stat = _MANUAL_PATH.stat()
    body, toc_items = _render_md(stat.st_mtime_ns, stat.st_size)
    toc_html = _render_toc_html(toc_items)
    return f"""
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>开放平台 API 开发手册</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b1020; color: #e8eefc; line-height: 1.7; }}
          .wrap {{ max-width: 1280px; margin: 0 auto; padding: 40px 20px 80px; display: flex; gap: 32px; align-items: flex-start; }}
          .toc {{ position: sticky; top: 24px; width: 250px; flex-shrink: 0; max-height: calc(100vh - 48px); overflow-y: auto; padding: 16px 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; font-size: 0.85rem; }}
          .toc-title {{ font-weight: 600; color: #f2f6ff; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
          .toc ul {{ list-style: none; margin: 0; padding: 0; }}
          .toc li {{ margin: 2px 0; }}
          .toc a {{ color: #9db4d8; text-decoration: none; display: block; padding: 3px 8px; border-radius: 6px; }}
          .toc a:hover {{ color: #8dc1ff; background: rgba(141,193,255,0.1); }}
          .toc .toc-h3 {{ padding-left: 14px; font-size: 0.8rem; }}
          article {{ flex: 1; min-width: 0; margin-top: 0; padding: 8px 24px 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; }}
          article h2, article h3 {{ scroll-margin-top: 24px; }}
          @media (max-width: 900px) {{
            .wrap {{ flex-direction: column; }}
            .toc {{ position: static; width: auto; max-height: 320px; }}
          }}
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
          {toc_html}
          <article>{body}</article>
        </div>
      </body>
    </html>
    """
