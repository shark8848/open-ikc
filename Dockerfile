#
# open-ikc-api 平台镜像（多阶段）：
#   Stage 1  portal-build —— 构建管理 Portal 前端（Vite 8 + React 18 + TS）到 /portal/dist
#   Stage 2  runtime      —— Python 3.12 + FastAPI 北向平台，静态挂载 portal 产物于 /portal
#
# 私有依赖 ikc-log-center（PyPI 不可得）：
#   wheel 由 scripts/build_docker.sh 预置到 docker/wheels/（缺失时从源码 v1.4.9 现场构建）；
#   直接 docker build 前请先运行 `bash scripts/build_docker.sh --wheel-only`。

# ============ Stage 1: Portal 前端构建 ============
FROM node:22-alpine AS portal-build
WORKDIR /portal
COPY portal/package.json portal/package-lock.json ./
RUN npm ci
COPY portal/ ./
RUN npm run build

# ============ Stage 2: 运行镜像 ============
FROM python:3.12-slim AS runtime

ARG IKC_LOG_CENTER_VERSION=1.4.9

# 先安装 log-center wheel（已安装后 pip 解析 ==1.4.9 不再请求 PyPI），再安装项目依赖
COPY docker/wheels/ /tmp/wheels/
RUN test -n "$(ls -A /tmp/wheels 2>/dev/null)" \
      || (echo "[build] 缺少 ikc-log-center wheel，请先运行 bash scripts/build_docker.sh --wheel-only" && exit 1) \
    && pip install --no-cache-dir "/tmp/wheels/ikc_log_center-${IKC_LOG_CENTER_VERSION}-py3-none-any.whl" \
    && rm -rf /tmp/wheels

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app/ ./app/
# docs/ 为运行时依赖（/api-manual 读取 docs/API开发手册.md），须随镜像打包
COPY docs/ ./docs/
RUN pip install --no-cache-dir .

# Portal 前端构建产物（Stage 1）；app/core/app_factory.py 相对本文件定位 /app/portal/dist
COPY --from=portal-build /portal/dist /app/portal/dist

# 非 root 运行；uid 1000 与常见宿主机用户对齐，便于挂载 data/logs 卷
RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 18000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000"]
