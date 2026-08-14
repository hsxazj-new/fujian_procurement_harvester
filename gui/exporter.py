# -*- coding: utf-8 -*-
"""CSV 导出（UTF-8 with BOM，Excel 直接打开不乱码）。"""
from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["关键词", "发布时间", "区划", "采购单位", "公告标题",
          "代理机构", "项目编号", "预算(元)", "公告链接"]


def export_records_csv(records: list[dict], out_path: str | Path) -> Path:
    """把公告记录列表写入 CSV。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return out_path


def default_filename(prefix: str = "公告结果") -> str:
    from datetime import datetime
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
