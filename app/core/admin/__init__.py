from __future__ import annotations

"""管理面核心模块（token 管理 / 监控统计 / 在线测试）。

管理面（admin）是平台的运维管理通道，独立于四类业务能力（知识库 / 文档 / 解析 / 检索），
使用独立管理鉴权（OPEN_PLATFORM_ADMIN_TOKEN），不进入 catalog 业务目录。
"""
