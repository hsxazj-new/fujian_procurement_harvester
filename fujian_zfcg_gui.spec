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
#
# 体积优化（实测验证）：本程序调用 DdddOcr(show_ad=False)（ocr=True, det=False, old=False），
# 经在 build_env 中跟踪 onnxruntime.InferenceSession 的实际加载路径确认，
# 运行时只会加载 common_old.onnx（约 13MB）。
# common.onnx（约 52MB，beta 模型）与 common_det.onnx（约 19MB，目标检测）从未被加载，
# 用 exclude_datas 剔除，共省约 70MB 原始体积（压缩进单文件 exe 后约 40MB+）。
d, b, h = collect_all(
    "ddddocr",
    filter_submodules=lambda name: not name.startswith("ddddocr.api"),
    exclude_datas=["*common.onnx", "*common_det.onnx"],
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

# 常规瘦身排除项：标准库 / 科学计算里本程序用不到的模块。
# 已核实对本程序运行时依赖链无影响：
#   - PIL.ImageQt 只在 PIL.Image 的 TYPE_CHECKING 块里引用，运行时不导入；
#   - unittest 仅被 onnxruntime.backend（sklearn 后端，本程序不导入）引用；
#   - onnxruntime 顶层只 import capi 子包，不含 backend。
_COMMON_EXCLUDES = [
    "tkinter",      # GUI 用 PySide6，不碰 Tk
    "test",         # 顶层 test 包（excludes 为精确匹配，只顶掉同名包）
    "tests",
    "unittest",
    "pydoc",
    "doctest",
    "matplotlib",
    "scipy",
    "PIL.ImageQt",  # PIL↔Qt 桥接模块，本程序未使用
]
# 注意：numpy 不能排除！ddddocr/onnxruntime 运行时硬依赖（onnxruntime 元数据要求
# numpy>=1.21.6，ddddocr 的 ocr_engine/preprocessing/utils 均 import numpy），
# 排除会导致验证码识别直接崩溃（这点已验证：exe 里 numpy 约 30MB，属于必要体积）。
# 注意：excludes 是精确字符串匹配，不支持 "PySide6.Qt3D*" 通配符写法；
# Qt3D 系列模块已在 _HEAVY_QT 中逐个列出排除。

# ddddocr 的 HTTP API 子包依赖 fastapi，本程序不使用；兜底排除，防止被隐式收集
excludes = _HEAVY_QT + _COMMON_EXCLUDES + ["ddddocr.api"]

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

# PySide6 翻译瘦身：PyInstaller 的 Qt hook 按实际导入的模块自动收集翻译文件，
# QtCore 会连带 qtbase_*.qm + qt_*.qm 全套约 50 种语言（合计约 9.4MB）。
# 本程序是中文界面（qfluentwidgets 走自己的 :/qfluentwidgets/i18n 资源，GUI 代码不用 QTranslator），
# 只需保留 zh_CN（Qt 内置对话框/标准按钮的中文显示）+ en（兜底），其余语言全部剔除。
# QML 样例无需处理：QtQml/QtQuick 已在 _HEAVY_QT 中排除，对应 hook 不会收集 QML 目录。
_KEEP_QT_TRANSLATIONS = {"qtbase_zh_CN.qm", "qtbase_en.qm", "qt_zh_CN.qm", "qt_en.qm"}
a.datas = [
    entry
    for entry in a.datas
    if not (
        entry[0].replace("\\", "/").startswith("PySide6/translations/")
        and entry[0].replace("\\", "/").rsplit("/", 1)[-1] not in _KEEP_QT_TRANSLATIONS
    )
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="福建省政府采购网招投标公告采集器",
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
