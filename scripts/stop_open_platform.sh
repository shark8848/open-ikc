#!/usr/bin/env bash
set -euo pipefail

# 停止 Open IKC 平台服务（与 scripts/start_open_platform.sh 配套）。
# - 仅匹配进程名为 python 系列、命令行含 "uvicorn app.main:app" 的服务进程
#   （--reload 模式会同时匹配 reloader 与 worker），避免误杀调用链自身
# - 先发 SIGTERM 优雅停止，最多等待 10 秒；仍有残留时提示手动处理并退出 1

PATTERN="uvicorn app.main:app"

pids="$(ps -eo pid=,comm=,args= | awk -v pat="$PATTERN" 'tolower($2) ~ /^python/ && $0 ~ pat {print $1}' | tr -d ' ')"
if [[ -z "$pids" ]]; then
  echo "[stop] 未发现运行中的 Open IKC 服务（匹配: $PATTERN）"
  exit 0
fi

echo "[stop] 发送 SIGTERM 停止进程: $pids"
kill -TERM $pids

# 等待优雅退出，最多 10 秒
for _ in $(seq 1 10); do
  if ! ps -eo comm=,args= | awk -v pat="$PATTERN" 'tolower($1) ~ /^python/ && $0 ~ pat {found=1} END {exit !found}' >/dev/null 2>&1; then
    echo "[stop] Open IKC 服务已停止"
    exit 0
  fi
  sleep 1
done

echo "[stop] 进程未在 10 秒内退出，请手动处理: $pids"
exit 1
