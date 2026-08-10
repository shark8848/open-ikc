#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

# 日志中心远程投递（ikc-log-center SDK）：开启后日志异步送达日志中心服务端，否则仅本地输出
# - LOG_CENTER_ENABLE=true 启用远程 handler；LOG_CENTER_URL 指向日志中心 HTTP 地址（SDK 自动 POST {url}/ingest）
# - 若日志中心服务端开启了 Bearer 认证，需额外导出 LOG_CENTER_TOKEN 环境变量
: "${LOG_CENTER_ENABLE:=true}"
: "${LOG_CENTER_URL:=http://127.0.0.1:9315}"
export LOG_CENTER_ENABLE LOG_CENTER_URL

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
