#!/bin/sh
set -eu

# 单镜像入口：先启动平台 API（仅监听回环 127.0.0.1:18000，不对外），
# 再前台运行 HAProxy 作为唯一对外入口（:80 反代平台，:8404 stats）。

# 用 HAPROXY_STATS_USER / HAPROXY_STATS_PASSWORD 渲染 HAProxy 配置模板
# （写到 /tmp，appuser 可写）
envsubst '${HAPROXY_STATS_USER} ${HAPROXY_STATS_PASSWORD}' \
  < /etc/haproxy/haproxy.cfg.tmpl \
  > /tmp/haproxy.cfg

# 默认 stats 凭据告警（admin/change-me 仅限本地试用，生产必须设置 HAPROXY_STATS_PASSWORD）
if [ "${HAPROXY_STATS_USER:-admin}" = "admin" ] && [ "${HAPROXY_STATS_PASSWORD:-change-me}" = "change-me" ]; then
  echo "[warn] HAProxy stats 使用默认凭据 admin/change-me，生产请设置 HAPROXY_STATS_PASSWORD" >&2
fi

# 平台 API 只监听回环地址，避免绕过 HAProxy 直连
python -m uvicorn app.main:app --host 127.0.0.1 --port 18000 &
APP_PID=$!

# 等待平台 /health 就绪（最多 60 次 × 0.5s），超时或进程退出则 fail-fast
READY=0
for _ in $(seq 1 60); do
  if python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:18000/health', timeout=1)" >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "[error] uvicorn 启动后退出（pid=$APP_PID），容器终止以便重启" >&2
    exit 1
  fi
  sleep 0.5
done
if [ "$READY" != "1" ]; then
  echo "[error] 平台 /health 未在 30s 内就绪，容器终止以便重启" >&2
  kill "$APP_PID" 2>/dev/null || true
  exit 1
fi

# 前台运行 HAProxy（容器退出时同步清理平台进程）
/usr/sbin/haproxy -f /tmp/haproxy.cfg &
HAPROXY_PID=$!

forward() {
  kill -"$1" "$APP_PID" "$HAPROXY_PID" 2>/dev/null || true
}
trap 'forward TERM' TERM
trap 'forward INT' INT

wait "$HAPROXY_PID"
kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
