# -*- coding: utf-8 -*-
"""福建省政府采购网招投标公告采集器 - GUI 入口。

用法（在项目根目录）：
    python -m gui.main
或：
    python gui/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 兼容直接 `python gui/main.py` 的运行方式
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.log_bridge import setup_logging


def main() -> int:
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:  # noqa: BLE001  # 旧版 Qt 无此 API
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("福建省政府采购网招投标公告采集器")
    app.setApplicationDisplayName("福建省政府采购网招投标公告采集器")
    app.setOrganizationName("fujian_zfcg")

    setup_logging(console=False)

    # 延迟导入：确保 QApplication 已创建
    from gui.main_window import MainWindow

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
