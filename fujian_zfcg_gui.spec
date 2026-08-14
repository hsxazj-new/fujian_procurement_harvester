# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：福建政府采购公告采集器（GUI，单文件 exe）。

构建命令（在项目根目录）：
    python -m PyInstaller --noconfirm --clean fujian_zfcg_gui.spec

产物：dist/福建政府采购公告采集器.exe（免安装，双击即用）
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)

datas, binaries, hiddenimports = [], [], []

# qfluentwidgets：图标/主题资源编译在 _rc.resource 中，collect_all 兜底子模块与数据
d, b, h = collect_all("qfluentwidgets")
datas += d
binaries += b
hiddenimports += h

# ddddocr：验证码识别模型（common*.onnx）必须随包分发，否则运行时找不到模型。
# 1.6.x 起自带 HTTP API 子包 ddddocr.api（__init__ 顶层导入 fastapi，属可选 extra），
# 本程序只用 DdddOcr 识别验证码，用 filter 排除该子包：既避免打包无用代码，
# 也消除 collect_submodules 因缺少 fastapi 产生的 "Failed to collect submodules" 警告。
d, b, h = collect_all(
    "ddddocr",
    filter_submodules=lambda name: not name.startswith("ddddocr.api"),
)
datas += d
binaries += b
hiddenimports += h

hiddenimports += [
    "qframelesswindow",                 # PySide6-Frameless-Window（qfluentwidgets 依赖）
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtXml",
]

# 用不到的 Qt 重型模块，排除以显著减小体积（各模块 hook 只对本模块 DLL 生效）
_HEAVY_QT = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtDBus",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtAxContainer",
    "PySide6.QtTest", "PySide6.QtSql",
]

# ddddocr 的 HTTP API 子包依赖 fastapi，本程序不使用；兜底排除，防止被隐式收集
excludes = _HEAVY_QT + ["ddddocr.api"]

a = Analysis(
    [str(ROOT / "gui" / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="福建政府采购公告采集器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # 无控制台窗口
    disable_windowed_traceback=False,
    icon=str(ROOT / "build" / "icon" / "app.ico"),
    version=str(ROOT / "build" / "version_info.txt"),
)
