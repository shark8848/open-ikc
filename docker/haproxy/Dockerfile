#
# HAProxy 代理层组件镜像：官方 haproxy:3.0-alpine + envsubst 入口。
# HAProxy 配置文件本身不支持环境变量展开，因此容器启动时先用 envsubst
# 将模板（/etc/haproxy/haproxy.cfg.tmpl）中的 ${HAPROXY_STATS_USER} /
# ${HAPROXY_STATS_PASSWORD} 替换为 compose 注入的值，再启动 haproxy。
# 注意：基础镜像以非 root 的 haproxy 用户运行（USER 会延续到后续指令），
# 安装阶段需切回 root；渲染产物写到 /tmp（haproxy 用户可写）。

FROM haproxy:3.0-alpine

USER root
# envsubst（gettext 包）用于启动时渲染 stats 账号/密码到配置文件
RUN apk add --no-cache gettext
COPY haproxy-entrypoint.sh /usr/local/bin/haproxy-entrypoint.sh
RUN chmod +x /usr/local/bin/haproxy-entrypoint.sh
USER haproxy

ENTRYPOINT ["/usr/local/bin/haproxy-entrypoint.sh"]
