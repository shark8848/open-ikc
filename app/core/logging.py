from __future__ import annotations

import logging

from log_center_sdk import configure as sdk_configure
from log_center_sdk import get_logger as sdk_get_logger

# 本模块是对 ikc-log-center SDK（pip 安装模式接入）的轻量封装：
# - 统一入口 configure_logging() / get_logger()，业务代码不直接依赖 SDK 细节；
# - 实际装配由 app_factory 直接调用 sdk.configure()，此处封装供需要独立初始化日志的场景复用。


def configure_logging() -> None:
    # attach_remote=None：远程投递遵循环境变量（LOG_CENTER_ENABLE，默认 false）；
    # 部署时设置 LOG_CENTER_ENABLE=true 与 LOG_CENTER_URL 即可启用（见 scripts/start_open_platform.sh）。
    sdk_configure(module_name="open_ikc_api", attach_remote=None)


def get_logger(name: str, *, level: str | None = None) -> logging.Logger:
    return sdk_get_logger(name, level=level)
