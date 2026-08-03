from __future__ import annotations

import logging

from log_center_sdk import configure as sdk_configure
from log_center_sdk import get_logger as sdk_get_logger


def configure_logging() -> None:
    sdk_configure(module_name="open_ikc_api", attach_remote=None)


def get_logger(name: str, *, level: str | None = None) -> logging.Logger:
    return sdk_get_logger(name, level=level)
