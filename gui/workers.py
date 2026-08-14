# -*- coding: utf-8 -*-
"""后台检索线程（QThread）。

把耗时的网络检索（签名 + 验证码识别 + 翻页）放到后台线程，
通过信号把进度、日志、结果发回主线程，避免界面卡死。
"""
from __future__ import annotations

import threading

from loguru import logger
from PySide6.QtCore import QThread, Signal

from fujian_zfcg_search import FujianZfcg
from gui.db import Database, now_str, STATUS_SUCCESS, STATUS_FAILED, STATUS_STOPPED


def row_to_record(client: FujianZfcg, keyword: str, row: dict) -> dict:
    """把接口原始行转成统一的公告记录字典。"""
    return {
        "keyword": keyword,
        "notice_time": row.get("noticeTime") or "",
        "region": row.get("regionName") or "",
        "purchaser": row.get("purchaser") or "",
        "title": row.get("title") or "",
        "agency": row.get("agency") or "",
        "open_tender_code": row.get("openTenderCode") or "",
        "budget": row.get("budget") or "",
        "url": client.detail_url(row),
    }


class SearchWorker(QThread):
    """一次检索任务的后台线程。

    所有文本输出统一走 loguru（文件 + 控制台 + 界面日志面板），
    信号只负责驱动界面状态：

        keyword_progress(str, int, int) : 关键词, 命中总数, 本关键词已取条数
        task_done(int, dict)            : task_id, {total_found, saved_count, stopped}
        task_failed(int, str)           : task_id, 错误信息
    """

    keyword_progress = Signal(str, int, int)
    task_done = Signal(int, dict)
    task_failed = Signal(int, str)

    def __init__(self, task_id: int, keywords: list[str], *, start: str, end: str,
                 purchase_nature: str, page_size: int, max_pages: int,
                 notice_type: str, db: Database, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.keywords = [k.strip() for k in keywords if k and k.strip()]
        self.search_kwargs = {
            "start": start, "end": end,
            "purchase_nature": purchase_nature,
            "page_size": page_size, "max_pages": max_pages,
            "notice_type": notice_type,
        }
        self.db = db
        self._stop_flag = threading.Event()

    # ---------- 控制 ----------

    def stop(self) -> None:
        """请求停止：翻页循环与关键词循环都会尽快退出。"""
        self._stop_flag.set()

    def _should_stop(self) -> bool:
        return self._stop_flag.is_set()

    # ---------- 执行 ----------

    def run(self) -> None:  # noqa: D401
        logger.info("后台任务 #{id} 启动：关键词={kw}", id=self.task_id, kw=self.keywords)
        client = FujianZfcg()
        total_found = 0
        total_saved = 0
        stopped = False
        try:
            for kw in self.keywords:
                if self._should_stop():
                    stopped = True
                    logger.warning("任务 #{id} 收到停止请求，提前结束", id=self.task_id)
                    break
                logger.info("▶ [{kw}] 开始检索……", kw=kw)
                result = client.search(kw, should_stop=self._should_stop,
                                       **self.search_kwargs)
                rows = result["rows"]
                total_found += result["total"]
                records = [row_to_record(client, kw, r) for r in rows]

                before = self.db.count_notices(self.task_id)
                self.db.insert_notices(self.task_id, records)
                saved_now = self.db.count_notices(self.task_id) - before
                total_saved += saved_now

                self.db.update_task(self.task_id, total_found=total_found,
                                    saved_count=total_saved)
                self.keyword_progress.emit(kw, result["total"], len(rows))
                logger.info(
                    "✔ [{kw}] 命中 {total} 条，本次入库 {saved} 条"
                    "（累计去重后 {total_saved} 条）",
                    kw=kw, total=result["total"], saved=saved_now,
                    total_saved=total_saved)

            status = STATUS_STOPPED if stopped else STATUS_SUCCESS
            self.db.update_task(self.task_id, status=status,
                                total_found=total_found, saved_count=total_saved,
                                finished_at=now_str())
            if stopped:
                logger.warning("⏹ 任务 #{id} 已停止，共入库 {saved} 条",
                               id=self.task_id, saved=total_saved)
            else:
                logger.info("🎉 任务 #{id} 完成：共入库 {saved} 条",
                            id=self.task_id, saved=total_saved)
            self.task_done.emit(self.task_id, {
                "total_found": total_found, "saved_count": total_saved,
                "stopped": stopped,
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务 #{id} 失败", id=self.task_id)
            self.db.update_task(self.task_id, status=STATUS_FAILED,
                                total_found=total_found, saved_count=total_saved,
                                error=str(exc), finished_at=now_str())
            self.task_failed.emit(self.task_id, str(exc))
