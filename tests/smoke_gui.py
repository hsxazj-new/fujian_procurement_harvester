# -*- coding: utf-8 -*-
"""冒烟测试：离屏构建主窗口 + 数据库读写 + Worker 实例化。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from gui.log_bridge import setup_logging  # noqa: E402
from gui.db import Database  # noqa: E402
from gui.workers import SearchWorker  # noqa: E402
from gui.table_model import NoticeTableModel  # noqa: E402

setup_logging(console=False)

# 1) 数据库读写
import tempfile
tmp = Path(tempfile.mkdtemp()) / "test.db"
db = Database(tmp)
tid = db.create_task(keywords="档案数字化\n档案整理", start_date="2026-01-01",
                     end_date="2026-12-31", purchase_nature="3",
                     page_size=10, max_pages=1, notice_type="x")
assert tid > 0
records = [{"keyword": "档案数字化", "notice_time": "2026-08-01 10:00:00",
            "region": "福州市", "purchaser": "A单位", "title": "档案数字化项目",
            "agency": "B代理", "open_tender_code": "FJ-001",
            "budget": "100000", "url": "https://example.com/1"}]
db.insert_notices(tid, records)
db.insert_notices(tid, records)  # 重复插入应被忽略
assert db.count_notices(tid) == 1, db.count_notices(tid)
db.update_task(tid, status="success", total_found=1, saved_count=1, finished_at="x")
assert db.get_task(tid)["status"] == "success"
assert len(db.list_tasks()) == 1
assert db.list_notices(tid)[0]["title"] == "档案数字化项目"
print("[OK] db")

# 2) 构建主窗口
from gui.main_window import MainWindow  # noqa: E402

win = MainWindow()
win.show()
app.processEvents()
assert win.stackedWidget.count() == 3, win.stackedWidget.count()
print("[OK] MainWindow pages:", win.stackedWidget.count())

# 3) 表格模型
m = NoticeTableModel()
m.set_records(records)
assert m.rowCount() == 1 and m.columnCount() == 9
assert m.data(m.index(0, 3)) == "档案数字化项目"
print("[OK] table model")

# 3.5) 回归：ComboBox 的 userData 必须用关键字传参（addItem 第 2 个位置参数是 icon）
from gui.pages.search_page import SearchPage  # noqa: E402
from gui.pages.settings_page import SettingsPage  # noqa: E402
sp = SearchPage(db)
assert sp.nature_combo.currentData() == "3", sp.nature_combo.currentData()
assert sp.nature_combo.currentText() == "服务"
assert sp.notice_type_combo.currentData(), "公告类型 userData 不应为空"
stp = SettingsPage()
assert stp.theme_combo.currentData() == "auto", stp.theme_combo.currentData()
print("[OK] combo userData")

# 4) Worker 实例化（不启动，避免真实网络请求）
w = SearchWorker(tid, ["档案数字化"], start="2026-01-01 00:00:00",
                 end="2026-12-31 23:59:59", purchase_nature="3",
                 page_size=10, max_pages=1, notice_type="x", db=db)
assert not w.isRunning()
print("[OK] worker ctor")

# 5) 设置页开关 API
from qfluentwidgets import StateToolTip  # noqa: E402
st = StateToolTip("t", "c", win)
st.setState(True)
st.hide()
print("[OK] StateToolTip")

win.close()
app.processEvents()
print("ALL SMOKE TESTS PASSED")
