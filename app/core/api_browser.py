from __future__ import annotations

from app.core.catalog import API_CATALOG


def render_api_browser_html() -> str:
    sections = []
    for group in API_CATALOG:
        items = "".join(
            f"<li><code>{route['method']}</code> <a href='{route['path']}'>{route['path']}</a> - {route['summary']}</li>"
            for route in group["routes"]
        )
        sections.append(f"<section><h2>{group['category']}</h2><ul>{items}</ul></section>")

    return f"""
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>开放平台 API 浏览服务</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b1020; color: #e8eefc; }}
          .wrap {{ max-width: 1080px; margin: 0 auto; padding: 40px 20px 64px; }}
          .hero {{ background: linear-gradient(135deg, #182548, #0f1b34); border: 1px solid #263457; border-radius: 20px; padding: 28px; }}
          a {{ color: #8dc1ff; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
          code {{ background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 6px; }}
          section {{ margin-top: 24px; padding: 20px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; }}
          ul {{ line-height: 1.9; }}
          .links a {{ display: inline-block; margin-right: 16px; }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="hero">
            <h1>开放平台 API 浏览服务</h1>
            <p>当前仅保留四大类：知识库、文档、解析、检索。</p>
            <div class="links">
              <a href="/docs">Swagger UI</a>
              <a href="/redoc">ReDoc</a>
              <a href="/openapi.json">OpenAPI JSON</a>
              <a href="/health">Health</a>
            </div>
          </div>
          {''.join(sections)}
        </div>
      </body>
    </html>
    """
