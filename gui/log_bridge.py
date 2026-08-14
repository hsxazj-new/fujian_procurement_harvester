# -*- coding: utf-8 -*-
"""loguru 日志桥接：同时写入文件、控制台，并转发到 Qt 信号供界面展示。

用法：
    setup_logging()          # 初始化（文件 + 控制台 + UI 信号）
    get_emitter().message.connect(ui_slot)   # 界面订阅日志
    logger.info("xxx")       # 各处照常用 loguru
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal

from gui.frozen import app_root

APP_DIR = app_root()
LOG_DIR = APP_DIR / "logs"

_FILE_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
_UI_FMT = "{time:HH:mm:ss} | {level: <8} | {message}"
_CONSOLE_FMT = ("<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


class LogEmitter(QObject):
    """将 loguru 记录转发为 Qt 信号（跨线程安全）。

    注意：必须显式定义 emit()，否则会解析到 PySide6 的 QObject.emit
    （PyQt 风格旧接口），被 loguru 当作 sink 调用时会报错。
    """

    message = Signal(str)

    def emit(self, text: str) -> None:
        self.message.emit(text)


_emitter = LogEmitter()


def get_emitter() -> LogEmitter:
    return _emitter


def setup_logging(console: bool = True, ui_level: str = "INFO") -> int:
    """初始化 loguru；返回 UI 处理器 id（可用于 logger.remove(id) 关闭界面日志）。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    # 文件：按天滚动，保留 7 天
    logger.add(
        LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        rotation="10 MB", retention="7 days", encoding="utf-8",
        level="DEBUG", format=_FILE_FMT, enqueue=True, backtrace=True,
        diagnose=False,
    )
    if console:
        logger.add(sys.stderr, level="INFO", format=_CONSOLE_FMT)
    # UI 信号（enqueue=True 保证从工作线程发日志也安全）
    return logger.add(_emitter.emit, level=ui_level, format=_UI_FMT, enqueue=True)
