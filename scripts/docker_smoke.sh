#!/usr/bin/env bash
set -euo pipefail

# Docker 单镜像栈冒烟验证（AGENTS.md §13 / §6 的部署行为验证）：
#   1) 构建镜像（若 IMAGE_TAG 已存在则跳过构建，可用 --force-build 强制）
#   2) 起容器（HAProxy 对外 18080 / stats 8404）
#   3) 断言：/health、/portal、admin 鉴权、业务 create、/api-manual、
#      stats 默认凭据 200 / 错误凭据 401、
#      平台 18000 仅回环（容器 IP 连接被拒）
# 用法：bash scripts/docker_smoke.sh [--force-build]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FORCE_BUILD=0
[[ "${1:-}" == "--force-build" ]] && FORCE_BUILD=1

IMAGE_TAG="${IMAGE_TAG:-open-ikc-api:1.0.0}"
HTTP_PORT="${HAPROXY_HTTP_PORT:-18080}"
STATS_PORT="${HAPROXY_STATS_PORT:-8404}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[smoke] 未找到 docker 命令" >&2
  exit 1
fi

if [[ "$FORCE_BUILD" == "1" ]] || ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo "[smoke] 构建镜像 $IMAGE_TAG ..."
  bash scripts/build_docker.sh
fi

cleanup() {
  docker compose down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[smoke] 启动容器 ..."
docker compose up -d >/dev/null

# 等待 HAProxy 入口就绪（最多 60s）
for _ in $(seq 1 60); do
  if curl -fsS -m 3 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

fail() {
  echo "[smoke] FAIL: $1" >&2
  exit 1
}

echo "[smoke] 1. /health 经 HAProxy"
curl -fsS -m 5 "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null || fail "/health 未就绪"

echo "[smoke] 2. /portal 静态壳"
curl -fsS -m 5 "http://127.0.0.1:${HTTP_PORT}/portal/" | grep -q "Open IKC" || fail "/portal 内容异常"

echo "[smoke] 3. admin 鉴权（无 token 100401 / 带 token 000000）"
A1=$(curl -s -m 5 "http://127.0.0.1:${HTTP_PORT}/admin/overview")
echo "$A1" | grep -q '"errCode":"100401"' || fail "admin 无 token 未返回 100401: $A1"
A2=$(curl -s -m 5 -H "Authorization: Bearer test-admin-token" "http://127.0.0.1:${HTTP_PORT}/admin/overview")
echo "$A2" | grep -q '"errCode":"000000"' || fail "admin 带 token 未返回 000000: $A2"

echo "[smoke] 4. 业务 API（create 知识库）"
KB=$(curl -s -m 15 -X POST "http://127.0.0.1:${HTTP_PORT}/api/v1/knowledge-bases/create" \
  -H "Authorization: Bearer test-token" -H "Content-Type: application/json" \
  -d '{"kbName":"docker-smoke","kbType":"personal"}')
echo "$KB" | grep -q '"errCode":"000000"' || fail "create 失败: $KB"

echo "[smoke] 5. /api-manual（真实手册）"
curl -s -m 15 "http://127.0.0.1:${HTTP_PORT}/api-manual" | grep -q "快速开始" || fail "/api-manual 内容异常"

echo "[smoke] 6. stats 默认凭据 200 / 错误凭据 401"
C1=$(curl -s -m 5 -o /dev/null -w '%{http_code}' -u "admin:change-me" "http://127.0.0.1:${STATS_PORT}/")
[[ "$C1" == "200" ]] || fail "stats 默认凭据应 200，实际 $C1"
C2=$(curl -s -m 5 -o /dev/null -w '%{http_code}' -u "admin:wrong" "http://127.0.0.1:${STATS_PORT}/")
[[ "$C2" == "401" ]] || fail "stats 错误凭据应 401，实际 $C2"

echo "[smoke] 7. 平台 18000 仅回环（容器 IP 连接应被拒）"
CID=$(docker compose ps -q app)
docker exec "$CID" python -c "
import socket, subprocess, sys
ip = subprocess.check_output(['hostname', '-i']).decode().strip()
s = socket.socket()
try:
    s.settimeout(1); s.connect((ip, 18000))
except (ConnectionRefusedError, OSError):
    sys.exit(0)
finally:
    s.close()
sys.exit(1)
" || fail "容器 IP 可连 18000，回环隔离失效"

echo "[smoke] 8. 容器非 root 运行"
docker exec "$CID" sh -c 'test "$(id -u)" = "1000"' || fail "容器应以 uid 1000 运行"

echo "[smoke] PASS：单镜像栈全部冒烟通过（入口 ${HTTP_PORT} / stats ${STATS_PORT}）"
