#!/bin/sh
set -eu

# 用 compose 注入的 HAPROXY_STATS_USER / HAPROXY_STATS_PASSWORD 渲染配置模板
# 到 /tmp（haproxy 用户可写），再以官方镜像默认用户启动 haproxy
envsubst '${HAPROXY_STATS_USER} ${HAPROXY_STATS_PASSWORD}' \
  < /etc/haproxy/haproxy.cfg.tmpl \
  > /tmp/haproxy.cfg

exec haproxy -f /tmp/haproxy.cfg "$@"
