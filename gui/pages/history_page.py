# -*- coding: utf-8 -*-
"""历史记录页：检索任务列表 + 选中任务的公告明细。"""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QSplitter,
                               QVBoxLayout, QWidget)

from gui.config import get as cfg_get
from gui.db import STATUS_RUNNING
from gui.exporter import default_filename, export_records_csv
from gui.table_model import NoticeTableModel
from qfluentwidgets import (BodyLabel, FluentIcon, InfoBar, MessageBox,
                            PrimaryPushButton, PushButton, TableView)

_TASK_HEADERS = ["ID", "创建时间", "状态", "关键词", "命中", "入库", "错误"]
_STATUS_TEXT = {
    "running": "运行中", "success": "成功", "failed": "失败", "stopped": "已停止",
}
_STATUS_COLOR = {
    "running": "#ff9f0a", "success": "#34c759", "failed": "#ff3b30",
    "stopped": "#8e8e93",
}


class TasksTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[dict] = []

    def set_tasks(self, tasks: list[dict]) -> None:
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def task_at(self, row: int) -> dict | None:
        return self._tasks[row] if 0 <= row < len(self._tasks) else None

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_TASK_HEADERS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None
        task = self._tasks[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return task["id"]
            if col == 1:
                return task["created_at"]
            if col == 2:
                return _STATUS_TEXT.get(task["status"], task["status"])
            if col == 3:
                kws = (task["keywords"] or "").replace("\n", "、")
                return kws if len(kws) <= 60 else kws[:60] + "…"
            if col == 4:
                return task["total_found"]
            if col == 5:
                return task["saved_count"]
            if col == 6:
                return task.get("error") or ""
        if role == Qt.ItemDataRole.ForegroundRole and col == 2:
            from PySide6.QtGui import QColor
            return QColor(_STATUS_COLOR.get(task["status"], "#8e8e93"))
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (0, 4, 5):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return _TASK_HEADERS[section]
            return section + 1
        return None

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.SortOrder.DescendingOrder
        keys = ["id", "created_at", "status", "keywords", "total_found",
                "saved_count", "error"]
        self._tasks.sort(key=lambda t: str(t.get(keys[column], "")), reverse=reverse)
        self.layoutChanged.emit()


class HistoryPage(QWidget):
    """历史记录界面。"""

    rerun_requested = Signal(int)  # 重新检索某任务

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.addWidget(BodyLabel("检索任务历史（SQLite 持久化）", self))
        title_row.addStretch(1)
        self.refresh_btn = PushButton(FluentIcon.SYNC, "刷新", self)
        self.rerun_btn = PrimaryPushButton(FluentIcon.PLAY, "重新检索", self)
        self.export_btn = PushButton(FluentIcon.SAVE, "导出 CSV", self)
        self.delete_btn = PushButton(FluentIcon.DELETE, "删除", self)
        for b in (self.refresh_btn, self.rerun_btn, self.export_btn, self.delete_btn):
            title_row.addWidget(b)
        layout.addLayout(title_row)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # ---- 任务列表 ----
        self.tasks_table = TableView(self)
        self.tasks_table.setBorderVisible(True)
        self.tasks_table.setBorderRadius(8)
        self.tasks_table.setWordWrap(False)
        self.tasks_table.setSortingEnabled(True)
        self.tasks_table.verticalHeader().hide()
        th = self.tasks_table.horizontalHeader()
        th.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate([60, 150, 70, 320, 60, 60, 160]):
            self.tasks_table.setColumnWidth(col, width)
        th.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tasks_model = TasksTableModel(self.tasks_table)
        self.tasks_table.setModel(self.tasks_model)
        self.tasks_table.selectionModel().selectionChanged.connect(
            self._on_selection_changed)
        splitter.addWidget(self.tasks_table)

        # ---- 明细表 ----
        self.detail_table = TableView(self)
        self.detail_table.setBorderVisible(True)
        self.detail_table.setBorderRadius(8)
        self.detail_table.setWordWrap(False)
        self.detail_table.setSortingEnabled(True)
        self.detail_table.verticalHeader().hide()
        dh = self.detail_table.horizontalHeader()
        dh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        from gui.table_model import COL_WIDTHS
        for col, width in enumerate(COL_WIDTHS):
            self.detail_table.setColumnWidth(col, width)
        dh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.detail_model = NoticeTableModel(self.detail_table)
        self.detail_table.setModel(self.detail_model)
        splitter.addWidget(self.detail_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.refresh_btn.clicked.connect(self.refresh)
        self.rerun_btn.clicked.connect(self._on_rerun)
        self.export_btn.clicked.connect(self._on_export)
        self.delete_btn.clicked.connect(self._on_delete)

    # ---------- 交互 ----------

    def refresh(self) -> None:
        tasks = self.db.list_tasks(limit=200)
        self.tasks_model.set_tasks(tasks)
        self.tasks_table.clearSelection()
        self.detail_model.set_records([])

    def _selected_task(self) -> dict | None:
        indexes = self.tasks_table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.tasks_model.task_at(indexes[0].row())

    def _on_selection_changed(self) -> None:
        task = self._selected_task()
        self.detail_model.set_records(
            self.db.list_notices(task["id"]) if task else [])

    def _on_rerun(self) -> None:
        task = self._selected_task()
        if not task:
            InfoBar.info("请先选择任务", "在列表中选择一个历史任务", parent=self.window())
            return
        self.rerun_requested.emit(task["id"])

    def _on_export(self) -> None:
        task = self._selected_task()
        if not task:
            InfoBar.info("请先选择任务", "在列表中选择一个历史任务", parent=self.window())
            return
        records = self.db.list_notices(task["id"])
        if not records:
            InfoBar.warning("暂无可导出的数据", "该任务没有入库结果", parent=self.window())
            return
        out_dir = Path(cfg_get("export_dir"))
        out_path = export_records_csv(
            records, out_dir / default_filename(f"任务{task['id']}"))
        InfoBar.success("导出成功", f"{len(records)} 条 → {out_path}",
                        duration=5000, parent=self.window())
        logger.info("已导出任务 #{id} 的 {n} 条记录到 {p}",
                    id=task["id"], n=len(records), p=out_path)

    def _on_delete(self) -> None:
        task = self._selected_task()
        if not task:
            InfoBar.info("请先选择任务", "在列表中选择一个历史任务", parent=self.window())
            return
        if task["status"] == STATUS_RUNNING:
            InfoBar.warning("无法删除", "该任务正在运行中", parent=self.window())
            return
        box = MessageBox("删除任务",
                         f"确定删除任务 #{task['id']} 及其 {task['saved_count']} 条结果吗？此操作不可恢复。",
                         self.window())
        box.yesButton.setText("删除")
        box.cancelButton.setText("取消")
        if box.exec():
            self.db.delete_task(task["id"])
            self.refresh()
            logger.info("已删除任务 #{id}", id=task["id"])
            InfoBar.success("已删除", f"任务 #{task['id']} 已删除", parent=self.window())
