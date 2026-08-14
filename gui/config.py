# -*- coding: utf-8 -*-
"""应用设置（JSON 持久化）。"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from gui.frozen import app_root
from fujian_zfcg_search import DEFAULT_NOTICE_TYPE

APP_DIR = app_root()
DATA_DIR = APP_DIR / "data"
EXPORT_DIR = DATA_DIR / "exports"
CONFIG_PATH = DATA_DIR / "settings.json"

DEFAULTS = {
    "notice_type": DEFAULT_NOTICE_TYPE,
    "retry": 8,
    "export_dir": str(EXPORT_DIR),
    "window_effect": True,          # 启用 Mica(Win11)/亚克力(Win10)
    "theme": "auto",                # auto / light / dark
}

_lock = threading.Lock()
_cached: dict | None = None


def load_config() -> dict:
    global _cached
    with _lock:
        if _cached is not None:
            return dict(_cached)
        cfg = dict(DEFAULTS)
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
        except Exception:  # noqa: BLE001
            pass
        _cached = cfg
        return dict(cfg)


def save_config(cfg: dict) -> None:
    global _cached
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        _cached = dict(cfg)


def get(key: str):
    return load_config().get(key, DEFAULTS.get(key))
