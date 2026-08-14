# -*- coding: utf-8 -*-
"""检索页：检索条件表单 + 结果表格 + 进度 + 日志面板。"""
from __future__ import annotations

# 本文件是应用模块，不能单独运行；直接运行给出友好提示而不是报错堆栈
if __name__ == "__main__":
    raise SystemExit(
        "search_page.py 是 GUI 应用的一个页面模块，不能直接运行。\n"
        "请在项目根目录运行：\n"
        "    python -m gui.main\n"
        "（Windows 也可以直接双击「启动GUI.bat」）"
    )

import re
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QHeaderView,
                               QVBoxLayout, QWidget)

from fujian_zfcg_search import DEFAULT_NOTICE_TYPE
from gui.config import get as cfg_get
from gui.exporter import default_filename, export_records_csv
from gui.log_bridge import get_emitter
from gui.table_model import COL_WIDTHS, NoticeTableModel
from gui.workers import SearchWorker
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            FastCalendarPicker, FluentIcon, InfoBar,
                            InfoBarPosition, PrimaryPushButton, ProgressBar,
                            PushButton, SpinBox, StateToolTip,
                            StrongBodyLabel, TableView, TextBrowser, TextEdit)

# 公告类型预设：text -> codes；None 表示取设置页里的自定义编码
NOTICE_TYPE_PRESETS = [
    ("全部公告", DEFAULT_NOTICE_TYPE),
    ("采购公告", "00101"),
    ("结果公告", "001021,001022,001023,001024,001025,001026,001029,001004,001006"),
    ("自定义（在设置页编辑）", None),
]
_PURCHASE_NATURES = [("服务", "3"), ("货物", "1"), ("工程", "2")]
_LOG_MAX_BLOCKS = 2000


def parse_keywords(text: str) -> list[str]:
    """把输入解析为关键词列表：支持换行、中英文逗号、顿号、分号分隔。"""
    parts = re.split(r"[\n\r，,、;；]+", text)
    return [p.strip() for p in parts if p and p.strip()]


class SearchPage(QWidget):
    """检索界面。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.worker: SearchWorker | None = None
        self.current_task_id: int | None = None
        self._state_tooltip: StateToolTip | None = None
        self._done_keywords = 0
        self._total_keywords = 0

        self._build_ui()
        get_emitter().message.connect(self._append_log)
        self._set_running(False)

    # ---------- 界面 ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(12)

        # ---- 检索条件卡片 ----
        form_card = CardWidget(self)
        form_box = QVBoxLayout(form_card)
        form_box.setContentsMargins(24, 20, 24, 20)
        form_box.setSpacing(12)

        title = StrongBodyLabel("检索条件", form_card)
        form_box.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.kw_label = BodyLabel("关键词", form_card)
        self.kw_edit = TextEdit(form_card)
        self.kw_edit.setPlaceholderText(
            "每行一个标题关键词，例如：\n档案数字化\n病案数字化\n档案整理")
        self.kw_edit.setFixedHeight(80)
        kw_cell = QWidget(form_card)
        kw_cell_layout = QVBoxLayout(kw_cell)
        kw_cell_layout.setContentsMargins(0, 0, 0, 0)
        kw_cell_layout.setSpacing(2)
        kw_cell_layout.addWidget(self.kw_edit)
        self.kw_hint = CaptionLabel(
            "已识别 0 个关键词（每行一个，也支持逗号/顿号分隔，逐个检索后合并去重）",
            kw_cell)
        kw_cell_layout.addWidget(self.kw_hint)
        self.kw_edit.textChanged.connect(self._update_kw_hint)

        self.start_label = BodyLabel("发布时间起", form_card)
        self.start_date = FastCalendarPicker(form_card)
        self.start_date.setDateFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate(2026, 1, 1))

        self.end_label = BodyLabel("发布时间止", form_card)
        self.end_date = FastCalendarPicker(form_card)
        self.end_date.setDateFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate(2026, 12, 31))

        self.nature_label = BodyLabel("采购品目", form_card)
        self.nature_combo = ComboBox(form_card)
        for text, data in _PURCHASE_NATURES:
            self.nature_combo.addItem(text, userData=data)

        self.page_size_label = BodyLabel("每页条数", form_card)
        self.page_size_spin = SpinBox(form_card)
        self.page_size_spin.setRange(1, 100)
        self.page_size_spin.setValue(10)

        self.max_pages_label = BodyLabel("最多翻页", form_card)
        self.max_pages_spin = SpinBox(form_card)
        self.max_pages_spin.setRange(1, 50)
        self.max_pages_spin.setValue(1)

        self.notice_type_label = BodyLabel("公告类型", form_card)
        self.notice_type_combo = ComboBox(form_card)
        for text, codes in NOTICE_TYPE_PRESETS:
            self.notice_type_combo.addItem(text, userData=codes)

        grid.addWidget(self.kw_label, 0, 0)
        grid.addWidget(kw_cell, 0, 1, 1, 5)
        grid.addWidget(self.start_label, 1, 0)
        grid.addWidget(self.start_date, 1, 1)
        grid.addWidget(self.end_label, 1, 2)
        grid.addWidget(self.end_date, 1, 3)
        grid.addWidget(self.nature_label, 1, 4)
        grid.addWidget(self.nature_combo, 1, 5)
        grid.addWidget(self.page_size_label, 2, 0)
        grid.addWidget(self.page_size_spin, 2, 1)
        grid.addWidget(self.max_pages_label, 2, 2)
        grid.addWidget(self.max_pages_spin, 2, 3)
        grid.addWidget(self.notice_type_label, 2, 4)
        grid.addWidget(self.notice_type_combo, 2, 5)
        form_box.addLayout(grid)
        layout.addWidget(form_card)

        # ---- 按钮行 ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.run_btn = PrimaryPushButton(FluentIcon.PLAY, "开始检索", self)
        self.stop_btn = PushButton(FluentIcon.CANCEL, "停止", self)
        self.export_btn = PushButton(FluentIcon.SAVE, "导出 CSV", self)
        self.status_label = BodyLabel("未开始", self)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.status_label)
        layout.addLayout(btn_row)

        # ---- 进度条 ----
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_label = BodyLabel("0 / 0 个关键词", self)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.progress_label)
        layout.addLayout(progress_row)

        # ---- 结果表格 ----
        self.table = TableView(self)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate(COL_WIDTHS):
            self.table.setColumnWidth(col, width)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.model = NoticeTableModel(self.table)
        self.table.setModel(self.model)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self._install_copy_shortcut()
        layout.addWidget(self.table, 1)

        # ---- 日志面板 ----
        self.log_browser = TextBrowser(self)
        self.log_browser.setReadOnly(True)
        self.log_browser.setFixedHeight(170)
        self.log_browser.document().setMaximumBlockCount(_LOG_MAX_BLOCKS)
        layout.addWidget(self.log_browser)

        # 事件
        self.run_btn.clicked.connect(self._on_run)
        self.stop_btn.clicked.connect(self._on_stop)
        self.export_btn.clicked.connect(self._on_export)
        self._update_kw_hint()

    def _install_copy_shortcut(self) -> None:
        shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.table)
        shortcut.activated.connect(self._copy_selected)

    # ---------- 交互 ----------

    def _on_run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        keywords = parse_keywords(self.kw_edit.toPlainText())
        if not keywords:
            InfoBar.warning("请先填写关键词", "每行一个关键词", parent=self.window())
            return
        start_date = self.start_date.date
        end_date = self.end_date.date
        if not start_date.isValid() or not end_date.isValid():
            InfoBar.warning("日期未设置", "请通过日历选择起止日期", parent=self.window())
            return
        start = start_date.toString("yyyy-MM-dd")
        end = end_date.toString("yyyy-MM-dd")
        if start > end:
            InfoBar.warning("时间范围有误", "开始日期不能晚于结束日期",
                            parent=self.window())
            return

        task_id = self.db.create_task(
            keywords="\n".join(keywords),
            start_date=start, end_date=end,
            purchase_nature=self.nature_combo.currentData(),
            page_size=self.page_size_spin.value(),
            max_pages=self.max_pages_spin.value(),
            notice_type=self._current_notice_type(),
        )
        self.current_task_id = task_id
        self.model.set_records([])

        worker = SearchWorker(
            task_id, keywords,
            start=f"{start} 00:00:00", end=f"{end} 23:59:59",
            purchase_nature=self.nature_combo.currentData(),
            page_size=self.page_size_spin.value(),
            max_pages=self.max_pages_spin.value(),
            notice_type=self._current_notice_type(),
            db=self.db, parent=self,
        )
        worker.keyword_progress.connect(self._on_keyword_progress)
        worker.task_done.connect(self._on_task_done)
        worker.task_failed.connect(self._on_task_failed)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker

        self._done_keywords = 0
        self._total_keywords = len(keywords)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0 / {self._total_keywords} 个关键词")
        self.status_label.setText(f"任务 #{task_id} 运行中…")
        self._set_running(True)
        self._state_tooltip = StateToolTip("正在检索", "正在请求公告数据……", self.window())
        self._state_tooltip.show()
        logger.info("创建任务 #{id}，关键词 {n} 个：{kws}",
                    id=task_id, n=len(keywords), kws=keywords)
        worker.start()

    def _on_stop(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            logger.info("请求停止任务 #{id}", id=self.current_task_id)
            self.worker.stop()

    def _on_export(self) -> None:
        if self.current_task_id is None:
            InfoBar.info("暂无可导出的数据", "请先执行一次检索", parent=self.window())
            return
        records = self.db.list_notices(self.current_task_id)
        if not records:
            InfoBar.warning("暂无可导出的数据", "当前任务没有入库结果",
                            parent=self.window())
            return
        out_dir = Path(cfg_get("export_dir"))
        out_path = export_records_csv(
            records, out_dir / default_filename(f"任务{self.current_task_id}"))
        InfoBar.success("导出成功", f"{len(records)} 条 → {out_path}",
                        duration=5000, parent=self.window())
        logger.info("已导出 {n} 条到 {p}", n=len(records), p=out_path)

    def _update_kw_hint(self) -> None:
        count = len(parse_keywords(self.kw_edit.toPlainText()))
        self.kw_hint.setText(
            f"已识别 {count} 个关键词（每行一个，也支持逗号/顿号分隔，"
            f"逐个检索后合并去重）")

    def load_task_params(self, task_id: int) -> None:
        """从历史任务回填检索表单（用于「重新检索」）。"""
        task = self.db.get_task(task_id)
        if not task:
            return
        self.kw_edit.setPlainText(task["keywords"])
        if task["start_date"]:
            self.start_date.setDate(
                QDate.fromString(task["start_date"], "yyyy-MM-dd"))
        if task["end_date"]:
            self.end_date.setDate(
                QDate.fromString(task["end_date"], "yyyy-MM-dd"))
        nature = task["purchase_nature"]
        idx = self.nature_combo.findData(nature)
        if idx >= 0:
            self.nature_combo.setCurrentIndex(idx)
        self.page_size_spin.setValue(task["page_size"])
        self.max_pages_spin.setValue(task["max_pages"])
        codes = task["notice_type"]
        idx = self.notice_type_combo.findData(codes)
        if idx >= 0:
            self.notice_type_combo.setCurrentIndex(idx)
        else:
            # 历史任务使用了预设之外的编码：动态加一项并选中
            self.notice_type_combo.addItem(f"自定义（{codes[:18]}…）",
                                           userData=codes)
            self.notice_type_combo.setCurrentIndex(self.notice_type_combo.count() - 1)

    def _current_notice_type(self) -> str:
        data = self.notice_type_combo.currentData()
        if data is None:
            return cfg_get("notice_type") or DEFAULT_NOTICE_TYPE
        return data

    # ---------- Worker 信号槽 ----------

    def _on_keyword_progress(self, keyword: str, total: int, fetched: int) -> None:
        self._done_keywords += 1
        percent = int(self._done_keywords * 100 / max(self._total_keywords, 1))
        self.progress_bar.setValue(percent)
        self.progress_label.setText(
            f"{self._done_keywords} / {self._total_keywords} 个关键词")
        if self._state_tooltip is not None:
            self._state_tooltip.setContent(
                f"「{keyword}」命中 {total} 条，已取 {fetched} 条")
        self._refresh_table()

    def _on_task_done(self, task_id: int, summary: dict) -> None:
        if task_id != self.current_task_id:
            return
        self._refresh_table()
        saved = summary["saved_count"]
        self.status_label.setText(
            f"任务 #{task_id} 完成：命中 {summary['total_found']}，入库 {saved} 条"
            + ("（已停止）" if summary.get("stopped") else ""))
        self.progress_bar.setValue(100)
        if self._state_tooltip is not None:
            self._state_tooltip.setContent(f"完成，共入库 {saved} 条")
            self._state_tooltip.setState(True)
            self._state_tooltip = None
        if summary.get("stopped"):
            InfoBar.warning("已停止", f"任务 #{task_id} 已停止，入库 {saved} 条",
                            parent=self.window())
        else:
            InfoBar.success("检索完成", f"任务 #{task_id}，入库 {saved} 条",
                            parent=self.window())

    def _on_task_failed(self, task_id: int, error: str) -> None:
        if task_id != self.current_task_id:
            return
        self._refresh_table()
        self.status_label.setText(f"任务 #{task_id} 失败")
        if self._state_tooltip is not None:
            self._state_tooltip.setState(False)
            self._state_tooltip.hide()
            self._state_tooltip = None
        InfoBar.error("检索失败", error, duration=6000, parent=self.window())

    def _on_worker_finished(self) -> None:
        self._set_running(False)
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    # ---------- 辅助 ----------

    def _refresh_table(self) -> None:
        if self.current_task_id is None:
            return
        records = self.db.list_notices(self.current_task_id)
        self.model.set_records(records)
        self.table.clearSelection()

    def _set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.export_btn.setEnabled(not running)

    def _on_row_double_clicked(self, index) -> None:
        records = self.model.records()
        if index.row() < 0 or index.row() >= len(records):
            return
        url = records[index.row()].get("url", "")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _copy_selected(self) -> None:
        from PySide6.QtWidgets import QApplication
        selection = self.table.selectionModel()
        if not selection.hasSelection():
            return
        rows = sorted({i.row() for i in selection.selectedIndexes()})
        cols = sorted({i.column() for i in selection.selectedIndexes()})
        lines = []
        for r in rows:
            lines.append("\t".join(
                self.model.index(r, c).data() for c in cols))
        QApplication.clipboard().setText("\n".join(lines))
        logger.info("已复制 {n} 行 × {m} 列到剪贴板", n=len(rows), m=len(cols))

    def _append_log(self, text: str) -> None:
        self.log_browser.append(text)

    def shutdown(self) -> None:
        """关闭窗口前调用：停止并等待后台线程退出。"""
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(8000)
