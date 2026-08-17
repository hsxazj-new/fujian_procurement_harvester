# -*- coding: utf-8 -*-
"""SQLite 数据层：持久化检索任务与公告结果。

- search_tasks : 一次检索任务（关键词、采购单位、时间范围、品目、分页、状态）
- notices      : 检索到的公告明细，按 (task_id, notice_time, title) 去重
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from gui.frozen import app_root

APP_DIR = app_root()
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    keywords        TEXT    NOT NULL,
    purchaser       TEXT    NOT NULL DEFAULT '',
    start_date      TEXT    NOT NULL DEFAULT '',
    end_date        TEXT    NOT NULL DEFAULT '',
    purchase_nature TEXT    NOT NULL DEFAULT '3',
    page_size       INTEGER NOT NULL DEFAULT 10,
    max_pages       INTEGER NOT NULL DEFAULT 1,
    notice_type     TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'running',   -- running / success / failed / stopped
    total_found     INTEGER NOT NULL DEFAULT 0,
    saved_count     INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    created_at      TEXT    NOT NULL,
    finished_at     TEXT
);

CREATE TABLE IF NOT EXISTS notices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL,
    keyword         TEXT    NOT NULL DEFAULT '',
    notice_time     TEXT    NOT NULL DEFAULT '',
    region          TEXT    NOT NULL DEFAULT '',
    purchaser       TEXT    NOT NULL DEFAULT '',
    title           TEXT    NOT NULL DEFAULT '',
    agency          TEXT    NOT NULL DEFAULT '',
    open_tender_code TEXT   NOT NULL DEFAULT '',
    budget          TEXT    NOT NULL DEFAULT '',
    url             TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES search_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notices_task ON notices(task_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_notices_task_time_title
    ON notices(task_id, notice_time, title);
"""

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_STOPPED = "stopped"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """线程安全的 SQLite 访问层（单连接 + 全局锁）。"""

    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        """旧库升级：为 search_tasks 补充新增列（ALTER TABLE ADD COLUMN）。"""
        cols = {row["name"] for row in
                self._conn.execute("PRAGMA table_info(search_tasks)").fetchall()}
        if "purchaser" not in cols:
            self._conn.execute(
                "ALTER TABLE search_tasks ADD COLUMN purchaser TEXT NOT NULL DEFAULT ''")

    # ---------- 任务 ----------

    def create_task(self, *, keywords: str, purchaser: str = "",
                    start_date: str, end_date: str,
                    purchase_nature: str, page_size: int, max_pages: int,
                    notice_type: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO search_tasks
                   (keywords, purchaser, start_date, end_date, purchase_nature,
                    page_size, max_pages, notice_type, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (keywords, purchaser, start_date, end_date, purchase_nature,
                 page_size, max_pages, notice_type, STATUS_RUNNING, now_str()),
            )
            self._conn.commit()
            return cur.lastrowid

    def update_task(self, task_id: int, **fields) -> None:
        allowed = {"status", "total_found", "saved_count", "error", "finished_at"}
        cols, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                raise KeyError(f"非法字段: {k}")
            cols.append(f"{k} = ?")
            vals.append(v)
        if not cols:
            return
        vals.append(task_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE search_tasks SET {', '.join(cols)} WHERE id = ?", vals)
            self._conn.commit()

    def get_task(self, task_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM search_tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM search_tasks ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete_task(self, task_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM search_tasks WHERE id = ?", (task_id,))
            self._conn.commit()

    # ---------- 公告 ----------

    def insert_notices(self, task_id: int, records: list[dict]) -> None:
        """批量插入（按 task_id + 时间 + 标题 忽略重复）。"""
        if not records:
            return
        rows = [(
            task_id, r.get("keyword", ""), r.get("notice_time", ""),
            r.get("region", ""), r.get("purchaser", ""), r.get("title", ""),
            r.get("agency", ""), r.get("open_tender_code", ""),
            r.get("budget", ""), r.get("url", ""),
        ) for r in records]
        with self._lock:
            self._conn.executemany(
                """INSERT OR IGNORE INTO notices
                   (task_id, keyword, notice_time, region, purchaser, title,
                    agency, open_tender_code, budget, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)
            self._conn.commit()

    def count_notices(self, task_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM notices WHERE task_id = ?",
                (task_id,)).fetchone()
        return int(row["c"])

    def list_notices(self, task_id: int, limit: int = 5000) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM notices WHERE task_id = ?
                   ORDER BY notice_time DESC, id DESC LIMIT ?""",
                (task_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_db = None


def get_db() -> Database:
    """进程级单例。"""
    global _db
    if _db is None:
        _db = Database()
    return _db
