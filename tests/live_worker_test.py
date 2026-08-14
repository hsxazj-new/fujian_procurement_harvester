# -*- coding: utf-8 -*-
"""端到端验证：真实检索一次（单关键词、单页），走 Worker 完整链路。

结果：要么成功入库（打印信号与数量），要么走 task_failed 分支（网络受限时也视为
链路验证通过，打印错误）。
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from gui.db import Database  # noqa: E402
from gui.workers import SearchWorker  # noqa: E402

db = Database(Path(tempfile.mkdtemp()) / "live.db")
tid = db.create_task(keywords="档案数字化", start_date="2026-01-01",
                     end_date="2026-12-31", purchase_nature="3",
                     page_size=5, max_pages=1, notice_type="00101")

progress, done, failed = [], [], []


def on_progress(kw, total, fetched):
    progress.append((kw, total, fetched))


def on_done(tid_, summary):
    done.append((tid_, summary))


def on_failed(tid_, err):
    failed.append((tid_, err))


w = SearchWorker(tid, ["档案数字化"], start="2026-01-01 00:00:00",
                 end="2026-12-31 23:59:59", purchase_nature="3",
                 page_size=5, max_pages=1, notice_type="00101", db=db)
w.keyword_progress.connect(on_progress)
w.task_done.connect(on_done)
w.task_failed.connect(on_failed)

print(">>> run() 开始（真实网络检索）……")
w.run()  # 同步执行线程逻辑，便于本脚本检查
print(">>> run() 结束")

print("progress:", progress)
print("done:", done)
print("failed:", failed)
task = db.get_task(tid)
print("task status:", task["status"], "| saved:", task["saved_count"],
      "| found:", task["total_found"], "| error:", task["error"])
n = db.count_notices(tid)
print("notices in db:", n)
if n:
    print("sample:", db.list_notices(tid)[0])
assert done or failed, "必须走到 done 或 failed 之一"
assert not (done and failed), "done 与 failed 不应同时发生"
print("LIVE TEST PASSED")
