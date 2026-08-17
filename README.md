# 福建政府采购网招投标信息采集（fujian_zfcg）

检索福建省政府采购网「公告信息」频道的招投标公告，主要能力：

- 按关键词（标题匹配）检索，也可**按采购单位名称筛选**，默认筛选 **采购品目 = 服务**；
- 自动处理接口签名（RSA + MD5/SHA1）与验证码识别（ddddocr）；
- 支持导出 CSV

## 一、环境准备（首次使用）

```bash
python -m pip install -r requirements.txt
```

## 二、检索并导出 CSV

### 快速示例

```bash
# 检索 4 类档案关键词（默认 2026 年全年、采购品目=服务，取前 10 条）
python fujian_zfcg_search.py --keywords 档案数字化 病案数字化 档案电子化 档案整理

# 自定义时间范围与输出文件
python fujian_zfcg_search.py --keywords 档案整理 --start 2026-07-01 --end 2026-12-31 --out 档案整理.csv

# 翻页取更多结果
python fujian_zfcg_search.py --keywords 档案数字化 --page-size 10 --max-pages 2

# 改采购品目（1=货物 2=工程 3=服务）
python fujian_zfcg_search.py --keywords 档案数字化 --purchase-nature 1

# 按采购单位筛选（可只填单位、不填关键词）
python fujian_zfcg_search.py --unit 福建医科大学附属第一医院 --keywords 病案翻拍 病历

# 只看某单位 2023 年以来的全部公告
python fujian_zfcg_search.py --unit 福建医科大学附属第一医院 --start 2023-01-01 --end 2026-12-31
```

### 参数说明

| 参数                  | 说明                             | 默认                      |
| ------------------- | ------------------------------ | ----------------------- |
| `--keywords`        | 标题关键词（可多个，空格分隔）                | —                       |
| `--unit`            | 采购单位名称筛选（与 `--keywords` 至少填一个） | —                       |
| `--start` / `--end` | 发布时间起止（YYYY-MM-DD）             | 2026-01-01 / 2026-12-31 |
| `--purchase-nature` | 采购品目：1=货物 2=工程 3=服务            | 3                       |
| `--page-size`       | 每页条数                           | 10                      |
| `--max-pages`       | 最多翻页数                          | 1                       |
| `--out`             | 输出 CSV 路径                      | `结果.csv`                |

### 输出说明

- CSV 为 UTF-8 with BOM，Excel 直接打开不乱码；
- 字段：关键词、发布时间、区划、采购单位、公告标题、代理机构、项目编号、预算（元）、公告链接；
- 多个关键词的结果按发布时间倒序合并并去重；
- 同时填写关键词与采购单位时，条件叠加生效（标题含关键词 **且** 单位匹配）。

## 三、数据来源与说明

- 数据来源：`/gpcms/rest/web/v2/info/selectInfoForIndex`，即页面「查询」按钮实际调用的接口；
- 检索逻辑与页面一致：关键词匹配公告标题，叠加采购品目、发布时间过滤；
- 验证码识别失败会自动刷新重试（最多 8 次）。

## 四、GUI 界面（PySide6 + QFluentWidgets）

提供桌面图形界面，功能与 CLI 一致，并增加了历史记录持久化：

```bash
python -m gui.main
```

### 界面组成

| 页面   | 功能                                                                  |
| ---- | ------------------------------------------------------------------- |
| 检索   | 填写关键词（每行一个）与采购单位（可选，可只填单位）、时间范围、采购品目、分页参数，一键检索；实时进度条 + 日志面板；可导出 CSV |
| 历史记录 | SQLite 持久化的检索任务列表（含采购单位）与公告明细，支持重新检索、导出、删除                          |
| 设置   | 公告类型编码、验证码重试次数、默认导出目录、窗口背景特效（Mica/亚克力）、主题                           |

### 技术要点

- **PySide6 + qfluentwidgets**：Fluent Design 风格的界面组件；
- **Acrylic**：Windows 11 自动使用 Mica 背景，Windows 10 1809+ 使用亚克力（可在设置页关闭）；
- **SQLite**：任务与公告结果保存在 `data/app.db`，跨次启动保留历史；
- **QThread**：检索（签名 + 验证码识别 + 翻页）在后台线程执行，界面不卡顿，支持中途停止；
- **loguru**：日志写入 `logs/` 目录并按天滚动，同时实时显示在界面日志面板。

### 目录结构

```
gui/
├── main.py            # 入口（python -m gui.main）
├── main_window.py     # 主窗口（FluentWindow + Mica/亚克力 + 导航）
├── config.py          # 应用设置（data/settings.json）
├── db.py              # SQLite 数据层（任务 / 公告结果）
├── log_bridge.py      # loguru → Qt 信号桥接
├── workers.py         # QThread 后台检索线程
├── exporter.py        # CSV 导出
├── table_model.py     # 公告结果表格模型
└── pages/             # 检索页 / 历史页 / 设置页
```

> 提示：核心检索逻辑仍复用 `fujian_zfcg_search.py`，CLI 用法不变；
> GUI 版为其新增了 `should_stop` 回调参数以支持界面上的「停止」按钮。

## 五、打包为免安装 exe（Windows）

用 PyInstaller 将 GUI 打包为单文件 exe，目标机器无需安装 Python：

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean fujian_zfcg_gui.spec
```

产物为 `dist/福建政府采购公告采集器.exe`（双击即用），旁边附 `使用说明.txt`。

要点：

- **单文件 + 无控制台**：`console=False` 的 onefile 构建；
- **验证码模型**：通过 `collect_all('ddddocr')` 把 `common*.onnx` 模型打进 exe；
- **Fluent 控件**：通过 `collect_all('qfluentwidgets')` 收集图标/主题资源；
- **数据目录**：打包后 `data/`、`logs/` 自动生成在 exe 旁边
  （`gui/frozen.py` 统一解析根目录，避免写入临时解压目录导致丢失）；
- **体积控制**：排除未用到的 Qt 重型模块（WebEngine / Quick / Multimedia 等）。

> 首次启动需解压内置运行库（约 10~30 秒），属正常现象。
