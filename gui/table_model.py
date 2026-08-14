# -*- coding: utf-8 -*-
"""公告结果表格模型（QAbstractTableModel）。"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

HEADERS = ["发布时间", "区划", "采购单位", "公告标题", "代理机构",
           "项目编号", "预算(元)", "关键词", "链接"]
# 列顺序与记录字段的映射
COL_FIELDS = ["notice_time", "region", "purchaser", "title", "agency",
              "open_tender_code", "budget", "keyword", "url"]
# 建议列宽
COL_WIDTHS = [120, 80, 150, 320, 130, 150, 90, 90, 140]


class NoticeTableModel(QAbstractTableModel):
    """把公告记录（dict 列表）映射为表格。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[dict] = []
        self._rows: list[list] = []

    def set_records(self, records: list[dict]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self._rows = [[r.get(f, "") for f in COL_FIELDS] for r in self._records]
        self.endResetModel()

    def records(self) -> list[dict]:
        return self._records

    # ---------- Qt 模型接口 ----------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._rows[index.row()][index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            if index.column() == len(HEADERS) - 1 and value:
                return "打开公告 ↗" if role == Qt.ItemDataRole.DisplayRole else value
            return str(value) if value else ""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in (0, 5, 6):
                return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return HEADERS[section]
        return section + 1

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.SortOrder.DescendingOrder
        field = COL_FIELDS[column]
        if field == "budget":
            def key(r):
                try:
                    return float(str(r.get(field, "")).replace(",", ""))
                except ValueError:
                    return -1.0
        else:
            def key(r):
                return str(r.get(field, ""))
        self._records.sort(key=key, reverse=reverse)
        self._rows = [[r.get(f, "") for f in COL_FIELDS] for r in self._records]
        self.layoutChanged.emit()
