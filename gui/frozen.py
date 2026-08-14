# -*- coding: utf-8 -*-
"""打包（PyInstaller）与开发模式下应用根目录的统一解析。

- 开发模式：项目根目录（gui/ 的上一级）
- 打包后（frozen）：exe 所在目录，data/、logs/ 会生成在 exe 旁边，便于携带与分发
"""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
