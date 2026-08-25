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

# 日志中心预检：LOG_CENTER_ENABLE=true 时必须可达，不可达则 fail-fast，
# 避免平台静默降级为本地文件日志（用户无感知）
if [ "${LOG_CENTER_ENABLE:-false}" = "true" ]; then
  LC_URL="${LOG_CENTER_URL:-http://127.0.0.1:9315}"
  if python -c "import urllib.request;urllib.request.urlopen('${LC_URL}/health', timeout=3)" >/dev/null 2>&1; then
    echo "[info] 日志中心可达: ${LC_URL}"
  else
    echo "[error] 日志中心不可达: LOG_CENTER_ENABLE=true 但 ${LC_URL}/health 请求失败" >&2
    echo "[error] 请确认日志中心已部署，且 LOG_CENTER_URL 指向容器可达地址（宿主机 host 网络部署时用 http://172.17.0.1:9315；Docker Desktop 用 http://host.docker.internal:9315）" >&2
    echo "[error] 如无需远程日志投递，请设 LOG_CENTER_ENABLE=false 后重启" >&2
    exit 1
  fi
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
