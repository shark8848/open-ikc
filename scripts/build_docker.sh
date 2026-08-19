#!/usr/bin/env bash
set -euo pipefail

# 构建 open-ikc 平台 Docker 镜像（后端 FastAPI + Portal 前端多阶段构建）。
#
# 私有依赖 ikc-log-center（PyPI 不可得，AGENTS.md §4.4 固定 ==1.4.9）自动准备：
#   1) 优先使用 docker/wheels/ 下已存在的 ikc_log_center-<版本>-py3-none-any.whl；
#   2) 缺失时从 $IKC_LOG_CENTER_REPO（默认 /home/ikc-log-center）源码
#      对应 git tag（v<版本>）现场构建 wheel（UI 产物 web/dist 取该仓库当前工作树）。
#
# 用法：
#   bash scripts/build_docker.sh                # 准备 wheel 并 docker build
#   bash scripts/build_docker.sh --wheel-only   # 仅准备 wheel，不执行 docker build
#   bash scripts/build_docker.sh --no-cache     # docker build --no-cache
#
# 环境变量：
#   IKC_LOG_CENTER_REPO   log-center 源码仓库路径（默认 /home/ikc-log-center）
#   IMAGE_TAG             镜像名:标签（默认 open-ikc-api:1.0.0）

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WHEELS_DIR="docker/wheels"
LOG_CENTER_REPO="${IKC_LOG_CENTER_REPO:-/home/ikc-log-center}"
WHEEL_ONLY=0
NO_CACHE=0
for arg in "$@"; do
  case "$arg" in
    --wheel-only) WHEEL_ONLY=1 ;;
    --no-cache) NO_CACHE=1 ;;
    *)
      echo "[usage] 未知参数: $arg（支持 --wheel-only / --no-cache）" >&2
      exit 1
      ;;
  esac
done

# 从 pyproject.toml 解析 ikc-log-center 固定版本（如 1.4.9）
VERSION="$(sed -n 's/.*"ikc-log-center==\([0-9][0-9.]*\)".*/\1/p' pyproject.toml | head -1)"
if [[ -z "$VERSION" ]]; then
  echo "[wheel] 无法从 pyproject.toml 解析 ikc-log-center 版本" >&2
  exit 1
fi
PINNED_WHEEL="ikc_log_center-${VERSION}-py3-none-any.whl"
IMAGE_TAG="${IMAGE_TAG:-open-ikc-api:1.0.0}"

mkdir -p "$WHEELS_DIR"

if [[ -f "$WHEELS_DIR/$PINNED_WHEEL" ]]; then
  echo "[wheel] 使用已有 wheel: $WHEELS_DIR/$PINNED_WHEEL"
else
  echo "[wheel] 缺少 $WHEELS_DIR/$PINNED_WHEEL，从 $LOG_CENTER_REPO 源码构建..."
  if [[ ! -d "$LOG_CENTER_REPO/.git" ]]; then
    echo "[wheel] $LOG_CENTER_REPO 不是 git 仓库；请手动放置 $PINNED_WHEEL 到 $WHEELS_DIR/ 后重试" >&2
    exit 1
  fi
  if [[ ! -d "$LOG_CENTER_REPO/web/dist" ]]; then
    echo "[wheel] $LOG_CENTER_REPO/web/dist 缺失（log-center UI 产物未构建），无法现场构建 wheel" >&2
    exit 1
  fi
  if ! git -C "$LOG_CENTER_REPO" rev-parse --verify --quiet "v${VERSION}" >/dev/null; then
    echo "[wheel] $LOG_CENTER_REPO 缺少 tag v${VERSION}，无法现场构建；请放置 $PINNED_WHEEL 到 $WHEELS_DIR/ 后重试" >&2
    exit 1
  fi
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git -C "$LOG_CENTER_REPO" archive "v${VERSION}" | tar -x -C "$tmp"
  # web/dist 为 UI 产物（tag 源码强制 include），取该仓库当前工作树（含未提交产物）
  cp -r "$LOG_CENTER_REPO/web/dist" "$tmp/web/dist"
  (cd "$tmp" && python3 -m pip wheel --no-deps --no-build-isolation . -w "$ROOT_DIR/$WHEELS_DIR")
  echo "[wheel] 构建完成: $WHEELS_DIR/$PINNED_WHEEL"
fi

if [[ "$WHEEL_ONLY" == "1" ]]; then
  echo "[wheel] --wheel-only 已指定，跳过 docker build"
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[docker] 未找到 docker 命令，请先安装 Docker" >&2
  exit 1
fi

build_args=(--build-arg "IKC_LOG_CENTER_VERSION=${VERSION}")
if [[ "$NO_CACHE" == "1" ]]; then
  build_args+=(--no-cache)
fi

echo "[docker] 构建镜像 $IMAGE_TAG（平台 + HAProxy 代理层同镜像）..."
docker build "${build_args[@]}" -t "$IMAGE_TAG" .

echo "[docker] 构建完成: $IMAGE_TAG"
echo "[docker] 启动（HAProxy 入口 http://127.0.0.1:18080）：docker compose up -d"
