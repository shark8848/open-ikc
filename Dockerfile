#
# open-ikc-api 平台镜像（多阶段，单镜像内含 HAProxy 代理层）：
#   Stage 1  portal-build —— 构建管理 Portal 前端（Vite 8 + React 18 + TS）到 /portal/dist
#   Stage 2  runtime      —— Python 3.12 + FastAPI 北向平台 + HAProxy 反向代理
#
# 拓扑（容器内）：client -> HAProxy(:80 / :8404) -> uvicorn(127.0.0.1:18000，仅回环)
#   - 平台 API 只监听 127.0.0.1:18000，不直接对外暴露；对外入口只有 HAProxy。
#   - HAProxy 配置模板 /etc/haproxy/haproxy.cfg.tmpl 由入口脚本 envsubst 渲染
#     （stats 账号/密码取自 HAPROXY_STATS_USER / HAPROXY_STATS_PASSWORD）。
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

# HAProxy 反向代理 + envsubst（渲染 stats 账号/密码）
RUN apt-get update \
    && apt-get install -y --no-install-recommends haproxy gettext \
    && rm -rf /var/lib/apt/lists/*

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

# HAProxy 代理层：配置模板 + 入口脚本（渲染配置后同进程启动 uvicorn + haproxy）
COPY docker/haproxy.cfg /etc/haproxy/haproxy.cfg.tmpl
COPY docker/entrypoint.sh /usr/local/bin/open-ikc-entrypoint.sh

# 非 root 运行；uid 1000 与常见宿主机用户对齐，便于挂载 data/logs 卷
RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app \
    && chmod +x /usr/local/bin/open-ikc-entrypoint.sh

USER appuser

# 仅暴露 HAProxy 入口（HTTP + stats）；平台 18000 只在容器回环内
EXPOSE 80 8404

ENTRYPOINT ["/usr/local/bin/open-ikc-entrypoint.sh"]
