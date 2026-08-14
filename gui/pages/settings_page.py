# -*- coding: utf-8 -*-
"""设置页：公告类型、重试次数、导出目录、窗口特效、主题。"""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout,
                               QVBoxLayout, QWidget)

from fujian_zfcg_search import DEFAULT_NOTICE_TYPE
from gui.config import DATA_DIR, load_config, save_config
from gui.log_bridge import LOG_DIR
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            FluentIcon, InfoBar, LineEdit, PrimaryPushButton,
                            PushButton, ScrollArea, SpinBox, StrongBodyLabel,
                            SwitchButton, TextEdit, Theme, ToolButton,
                            setTheme)

_THEME_OPTIONS = [("跟随系统", "auto"), ("浅色", "light"), ("深色", "dark")]


class SettingsPage(QWidget):
    """设置界面。"""

    saved = Signal()  # 保存设置后触发（主窗口据此重应用特效/主题）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 24, 40, 20)
        outer.setSpacing(12)

        title = StrongBodyLabel("设置", self)
        outer.addWidget(title)

        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.enableTransparentBackground()
        card_host = QWidget(scroll)
        card_host_layout = QVBoxLayout(card_host)
        card_host_layout.setContentsMargins(0, 0, 12, 0)

        card = CardWidget(card_host)
        grid = QGridLayout(card)
        grid.setContentsMargins(28, 24, 28, 24)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        # 公告类型
        grid.addWidget(BodyLabel("公告类型编码", card), 0, 0)
        self.notice_type_edit = TextEdit(card)
        self.notice_type_edit.setFixedHeight(90)
        grid.addWidget(self.notice_type_edit, 0, 1)
        hint1 = CaptionLabel(
            "逗号分隔的公告类型编码；留空 = 全部公告。"
            "采购公告=00101；结果公告=001021,001022,…", card)
        grid.addWidget(hint1, 1, 1)

        # 重试次数
        grid.addWidget(BodyLabel("验证码重试次数", card), 2, 0)
        self.retry_spin = SpinBox(card)
        self.retry_spin.setRange(1, 20)
        grid.addWidget(self.retry_spin, 2, 1)

        # 导出目录
        grid.addWidget(BodyLabel("默认导出目录", card), 3, 0)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.export_dir_edit = LineEdit(card)
        self.export_dir_btn = ToolButton(FluentIcon.FOLDER, card)
        dir_row.addWidget(self.export_dir_edit, 1)
        dir_row.addWidget(self.export_dir_btn)
        grid.addLayout(dir_row, 3, 1)

        # 窗口特效
        grid.addWidget(BodyLabel("窗口背景特效", card), 4, 0)
        self.effect_switch = SwitchButton("启用（Win11 使用 Mica，Win10 使用亚克力）", card)
        grid.addWidget(self.effect_switch, 4, 1)

        # 主题
        grid.addWidget(BodyLabel("主题", card), 5, 0)
        self.theme_combo = ComboBox(card)
        for text, data in _THEME_OPTIONS:
            self.theme_combo.addItem(text, userData=data)
        grid.addWidget(self.theme_combo, 5, 1)

        card_host_layout.addWidget(card)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.save_btn = PrimaryPushButton(FluentIcon.SAVE, "保存设置", self)
        self.open_data_btn = PushButton(FluentIcon.FOLDER, "打开数据目录", self)
        self.open_log_btn = PushButton(FluentIcon.DOCUMENT, "打开日志目录", self)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.open_data_btn)
        btn_row.addWidget(self.open_log_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        scroll.setWidget(card_host)
        outer.addWidget(scroll, 1)

        self.save_btn.clicked.connect(self._on_save)
        self.export_dir_btn.clicked.connect(self._on_browse_dir)
        self.open_data_btn.clicked.connect(
            lambda: self._open_dir(DATA_DIR))
        self.open_log_btn.clicked.connect(
            lambda: self._open_dir(LOG_DIR))

    # ---------- 数据 ----------

    def _load_values(self) -> None:
        cfg = load_config()
        self.notice_type_edit.setPlainText(cfg["notice_type"])
        self.retry_spin.setValue(int(cfg["retry"]))
        self.export_dir_edit.setText(cfg["export_dir"])
        self.effect_switch.setChecked(bool(cfg["window_effect"]))
        idx = self.theme_combo.findData(cfg["theme"])
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_browse_dir(self) -> None:
        start = self.export_dir_edit.text() or str(DATA_DIR)
        chosen = QFileDialog.getExistingDirectory(self, "选择默认导出目录", start)
        if chosen:
            self.export_dir_edit.setText(chosen)

    def _on_save(self) -> None:
        notice_type = self.notice_type_edit.toPlainText().strip()
        if not notice_type:
            notice_type = DEFAULT_NOTICE_TYPE
        export_dir = self.export_dir_edit.text().strip() or str(DATA_DIR / "exports")
        cfg = load_config()
        cfg.update({
            "notice_type": notice_type,
            "retry": int(self.retry_spin.value()),
            "export_dir": export_dir,
            "window_effect": self.effect_switch.isChecked(),
            "theme": self.theme_combo.currentData(),
        })
        save_config(cfg)
        # 立即应用主题与特效
        self._apply_theme(cfg["theme"])
        self.saved.emit()
        InfoBar.success("设置已保存", "下次检索将使用新配置", parent=self.window())
        logger.info("设置已保存：theme={t}, effect={e}",
                    t=cfg["theme"], e=cfg["window_effect"])

    @staticmethod
    def _apply_theme(mode: str) -> None:
        mapping = {"light": Theme.LIGHT, "dark": Theme.DARK}
        setTheme(mapping.get(mode, Theme.AUTO))

    @staticmethod
    def _open_dir(path: Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
