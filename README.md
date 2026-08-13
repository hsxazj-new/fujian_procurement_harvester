# 福建省政府采购网公告查询工具（fujian_zfcg）

> 本工具位于 `pytool\fujian_zfcg\` 子目录，请在子目录内运行命令。

自动检索福建省政府采购网「公告信息」频道的招投标公告，主要能力：

- 按关键词（标题匹配）检索，默认筛选 **采购品目 = 服务**；
- 自动处理接口签名（RSA + MD5/SHA1）与验证码识别（ddddocr）；
- 支持导出 CSV，也支持采集候选公告并写入 Excel 数据表 `data .xlsx`。

## 一、环境准备（首次使用）

```bash
python -m pip install -r requirements.txt
```

> 写入 Excel 的两个脚本（`fill_excel.py`、`delete_row.py`）依赖本机安装的 Excel / WPS（win32com），
> 以保证 `data .xlsx` 中原有的内嵌图片不丢失。

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
```

### 参数说明

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--keywords` | 标题关键词（必填，可多个，空格分隔） | — |
| `--start` / `--end` | 发布时间起止（YYYY-MM-DD） | 2026-01-01 / 2026-12-31 |
| `--purchase-nature` | 采购品目：1=货物 2=工程 3=服务 | 3 |
| `--page-size` | 每页条数 | 10 |
| `--max-pages` | 最多翻页数 | 1 |
| `--out` | 输出 CSV 路径 | `结果.csv` |

### 输出说明

- CSV 为 UTF-8 with BOM，Excel 直接打开不乱码；
- 字段：关键词、发布时间、区划、采购单位、公告标题、代理机构、项目编号、预算（元）、公告链接；
- 多个关键词的结果按发布时间倒序合并并去重。

## 三、写入 Excel 数据表（data .xlsx）

工作流分两步：**采集候选公告** → **填充表格**；发现错误/重复行时用第三步删除并重编号。

### 1. 采集候选公告

```bash
# 检索 2025–2026 年「采购公告 + 结果公告」，输出 collect_out.json 与 collect_raw.json
python collect_for_excel.py --start 2025-01-01 --end 2026-12-31 --limit 20
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--existing` | 已有数据 JSON（用于去重，可省略） |
| `--cache` | 历史缓存路径（默认 `cache/zfcg_cache.json`） |
| `--limit` | 本次采集条数 |

> 结果公告优先：能提取中标单位与中标金额；无结果公告的项目使用采购公告的预算金额，金额标注「（预算）」。

### 2. 填充 Excel

```bash
python fill_excel.py
```

- 把 `collect_out.json` 中的候选写入 `data .xlsx` 的 **A–G 列**（追加，不覆盖已有数据）；
- 使用本机 Excel（win32com）写入，完整保留原文件的单元格图片；
- 保存成功后把已写入公告 id 记录到 `cache/zfcg_cache.json`，下次自动跳过，避免重复。

可选参数：`--xlsx`（目标文件路径）、`--data`（候选 JSON 路径）。

### 3. 删除错误/重复行并重新编号

```bash
# 删除序号 20 那一行，A 列自动重新编号为 1~N
python delete_row.py --seq 20
```

- 使用本机 Excel 删除整行，保留其余行的内容与图片；
- 自动同步更新 `cache/zfcg_cache.json` 中已写入记录的序号。

## 四、缓存与去重

- `cache/zfcg_cache.json` 包含两类记录：
  - `added`：已写入 Excel 的公告 id 及对应序号；
  - `seen`：已检索过的公告 id，避免下次重复抓取。
- 判定重复的标准：单位、项目、中标单位（B/C/D 列）相同，且金额换算后相同。

## 五、数据来源与说明

- 数据来源：`/gpcms/rest/web/v2/info/selectInfoForIndex`，即页面「查询」按钮实际调用的接口；
- 检索逻辑与页面一致：关键词匹配公告标题，叠加采购品目、发布时间过滤；
- 验证码识别失败会自动刷新重试（最多 8 次）。
