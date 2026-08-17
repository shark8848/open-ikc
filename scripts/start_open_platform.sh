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

# 检索下游（knowledge_transformer）：默认进程内占位；生产切 ur / openai 时按需导出
# - OPEN_PLATFORM_SEARCH_BACKEND=in_process|ur|openai（ur=普通检索走 universal_retriever；openai=普通+深度走 openai_search_service）
# - OPEN_PLATFORM_UR_BASE_URL / OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL 指向下游服务
# - OPEN_PLATFORM_KB_INDEX_MAP 为 JSON 对象，显式映射 kb_id -> index
: "${OPEN_PLATFORM_SEARCH_BACKEND:=in_process}"
: "${OPEN_PLATFORM_UR_BASE_URL:=http://127.0.0.1:8096}"
: "${OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL:=http://127.0.0.1:8088/km/search-api/aiTools/openai/bsapi}"
: "${OPEN_PLATFORM_SEARCH_TIMEOUT_SECONDS:=10}"
: "${OPEN_PLATFORM_DEEP_SEARCH_TIMEOUT_SECONDS:=60}"
export OPEN_PLATFORM_SEARCH_BACKEND OPEN_PLATFORM_UR_BASE_URL OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL
export OPEN_PLATFORM_SEARCH_TIMEOUT_SECONDS OPEN_PLATFORM_DEEP_SEARCH_TIMEOUT_SECONDS

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
