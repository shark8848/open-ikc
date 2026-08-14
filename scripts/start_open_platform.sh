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

# 管理面（/admin/*）独立鉴权：未显式配置 OPEN_PLATFORM_ADMIN_TOKEN 时自动生成随机 token 并打印，
# 用于本地启用管理 Portal（登录时输入该 token）；生产环境务必通过环境变量显式配置强 token。
if [[ -z "${OPEN_PLATFORM_ADMIN_TOKEN:-}" ]]; then
  OPEN_PLATFORM_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
  echo "[admin] 管理面已启用，本次 OPEN_PLATFORM_ADMIN_TOKEN=$OPEN_PLATFORM_ADMIN_TOKEN"
fi
export OPEN_PLATFORM_ADMIN_TOKEN

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
