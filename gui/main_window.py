# -*- coding: utf-8 -*-
"""主窗口：FluentWindow + Mica(Win11)/亚克力(Win10) 背景 + 三页导航。"""
from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent

from gui.config import get as cfg_get
from gui.db import get_db
from gui.pages.history_page import HistoryPage
from gui.pages.search_page import SearchPage
from gui.pages.settings_page import SettingsPage
from qfluentwidgets import (FluentIcon, FluentWindow, NavigationItemPosition,
                            isDarkTheme)


class MainWindow(FluentWindow):
    """应用主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("福建省政府采购网招投标公告采集器")
        self.setMinimumSize(1080, 720)

        self.db = get_db()

        # 三个子页面（addSubInterface 要求 objectName 作为路由键）
        self.search_page = SearchPage(self.db, self)
        self.search_page.setObjectName("searchPage")
        self.history_page = HistoryPage(self.db, self)
        self.history_page.setObjectName("historyPage")
        self.settings_page = SettingsPage(self)
        self.settings_page.setObjectName("settingsPage")

        self.addSubInterface(self.search_page, FluentIcon.SEARCH, "检索")
        self.addSubInterface(self.history_page, FluentIcon.HISTORY, "历史记录")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "设置",
                             NavigationItemPosition.BOTTOM)

        # 跨页联动
        self.history_page.rerun_requested.connect(self._on_rerun_requested)
        self.settings_page.saved.connect(self._apply_window_effect)

        # 窗口背景特效（Win11 Mica / Win10 亚克力）
        self._apply_window_effect()

        self.resize(1180, 780)
        logger.info("主窗口初始化完成，SQLite 数据库：{path}", path=self.db.path)

    # ---------- 窗口特效 ----------

    def _apply_window_effect(self) -> None:
        """按系统版本应用 Mica 或亚克力背景；可在设置页关闭。"""
        if sys.platform != "win32" or not cfg_get("window_effect"):
            return
        try:
            build = sys.getwindowsversion().build
            if build >= 22000:  # Windows 11：Mica
                self.setMicaEffectEnabled(True)
            elif build >= 17763:  # Windows 10 1809+：真亚克力
                gradient = "D9000000" if isDarkTheme() else "D9FFFFFF"
                self.windowEffect.setAcrylicEffect(int(self.winId()),
                                                   gradient, True, 0)
                self.setBackgroundColor(Qt.GlobalColor.transparent)
            logger.info("已启用窗口背景特效（build={build}）", build=build)
        except Exception as exc:  # noqa: BLE001
            logger.warning("窗口背景特效应用失败：{exc}", exc=exc)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 窗口句柄就绪后再应用一次，保证亚克力生效
        self._apply_window_effect()

    # ---------- 跨页联动 ----------

    def _on_rerun_requested(self, task_id: int) -> None:
        self.search_page.load_task_params(task_id)
        self.navigationInterface.setCurrentItem("searchPage")
        self.stackedWidget.setCurrentWidget(self.search_page)
        logger.info("已从历史任务 #{id} 回填检索条件", id=task_id)

    # ---------- 生命周期 ----------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.search_page.shutdown()
        self.db.close()
        super().closeEvent(event)
