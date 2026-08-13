# 福建政府采购网招投标信息采集（fujian_zfcg）

检索福建省政府采购网「公告信息」频道的招投标公告，主要能力：

- 按关键词（标题匹配）检索，默认筛选 **采购品目 = 服务**；
- 自动处理接口签名（RSA + MD5/SHA1）与验证码识别（ddddocr）；
- 支持导出 CSV，也支持采集候选公告并写入 Excel 数据表 `data .xlsx`。

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
```

### 参数说明

| 参数                  | 说明                  | 默认                      |
| ------------------- | ------------------- | ----------------------- |
| `--keywords`        | 标题关键词（必填，可多个，空格分隔）  | —                       |
| `--start` / `--end` | 发布时间起止（YYYY-MM-DD）  | 2026-01-01 / 2026-12-31 |
| `--purchase-nature` | 采购品目：1=货物 2=工程 3=服务 | 3                       |
| `--page-size`       | 每页条数                | 10                      |
| `--max-pages`       | 最多翻页数               | 1                       |
| `--out`             | 输出 CSV 路径           | `结果.csv`                |

### 输出说明

- CSV 为 UTF-8 with BOM，Excel 直接打开不乱码；
- 字段：关键词、发布时间、区划、采购单位、公告标题、代理机构、项目编号、预算（元）、公告链接；
- 多个关键词的结果按发布时间倒序合并并去重。

## 三、数据来源与说明

- 数据来源：`/gpcms/rest/web/v2/info/selectInfoForIndex`，即页面「查询」按钮实际调用的接口；
- 检索逻辑与页面一致：关键词匹配公告标题，叠加采购品目、发布时间过滤；
- 验证码识别失败会自动刷新重试（最多 8 次）。
