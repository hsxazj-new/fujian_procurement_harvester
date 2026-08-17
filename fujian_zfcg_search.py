# -*- coding: utf-8 -*-
"""
福建省政府采购网 - 公告信息查询工具
==================================
在「公告信息」频道按关键词检索 2026 年（或任意时间范围）招投标公告，
默认使用页面筛选「采购品目 = 服务」。自动处理接口签名与验证码识别。

用法示例：
    python fujian_zfcg_search.py --keywords 档案数字化 病案数字化 档案电子化 档案整理
    python fujian_zfcg_search.py --keywords 档案数字化 --start 2026-01-01 --end 2026-12-31 --out 结果.csv
    python fujian_zfcg_search.py --keywords 档案整理 --page-size 20 --max-pages 2
    python fujian_zfcg_search.py --unit 福建医科大学附属第一医院 --keywords 病案翻拍 病历
    python fujian_zfcg_search.py --unit 福建医科大学附属第一医院 --start 2023-01-01 --end 2026-12-31
"""

import argparse
import base64
import csv
import hashlib
import io
import time

import requests
from PIL import Image

BASE_URL = "https://zfcg.czt.fujian.gov.cn"
# 公告信息频道（与页面 URL 中的 channel 参数一致）
DEFAULT_CHANNEL = "f582600e-065d-4f35-8966-48a33fa93863"
# 公告类型 = 全部（站点字典 xmcg-noticeType 的“全部”项）
DEFAULT_NOTICE_TYPE = (
    "59,001056,00101,001062,001051,001031,001032,"
    "001021,001022,001023,001024,001025,001026,001029,"
    "001004,001006,001054,001033,00105K,001054"
)
# 采购品目字典：1=货物 2=工程 3=服务
PURCHASE_NATURE = {"1": "货物", "2": "工程", "3": "服务"}

# 站点 RSA 公钥（来自页面 config.js 的 RSAPublicKey，以 ASCII 码列表存储）
_RSA_ASCII = (
    "77,73,71,102,77,65,48,71,67,83,113,71,83,73,98,51,68,81,69,66,65,81,85,65,65,52,"
    "71,78,65,68,67,66,105,81,75,66,103,81,67,83,50,84,90,68,115,53,43,111,114,76,89,"
    "67,76,53,83,115,74,53,52,43,98,80,67,86,115,49,90,81,81,119,80,50,82,111,80,107,"
    "70,81,70,50,106,99,84,48,72,110,78,78,84,56,90,111,81,103,74,84,114,71,119,78,105,"
    "53,81,78,84,66,68,111,72,67,52,111,74,101,115,65,86,89,101,54,68,111,120,88,83,57,"
    "78,108,115,56,87,98,71,69,56,90,78,103,79,67,53,116,86,118,49,87,86,106,121,66,119,"
    "55,107,50,120,55,50,67,47,113,106,80,111,121,111,47,107,79,55,84,89,108,54,81,110,"
    "117,52,106,113,87,47,73,109,76,111,117,112,47,110,115,74,112,112,85,122,110,70,48,"
    "89,103,98,121,85,47,100,70,70,78,66,81,73,68,65,81,65,66"
)
_RSA_PUBLIC_KEY = "".join(chr(int(x)) for x in _RSA_ASCII.split(","))

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def sign_request(path: str) -> dict:
    """按前端逻辑生成签名请求头：sign=MD5(SHA1(...))，nsssjss=RSA 加密。"""
    ts = int(time.time() * 1000)
    sha1 = hashlib.sha1(f"{ts}_{path}_bosssoft_platform_095285".encode()).hexdigest()
    sign = hashlib.md5(sha1.encode()).hexdigest()
    nsssjss = base64.b64encode(
        _rsa_encrypt(f"{path}$${ts}")
    ).decode()
    return {"time": str(ts), "url": path, "sign": sign, "nsssjss": nsssjss}


def _rsa_encrypt(plain: str) -> bytes:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    pub = serialization.load_pem_public_key(
        ("-----BEGIN PUBLIC KEY-----\n" + _RSA_PUBLIC_KEY + "\n-----END PUBLIC KEY-----").encode()
    )
    return pub.encrypt(
        plain.encode(),
        padding.PKCS1v15(),
    )


class FujianZfcg:
    """福建省政府采购网公告查询器（自动处理签名 + 验证码）。"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA, "Referer": BASE_URL + "/maincms-web/xmgg"})
        self.site_id = None
        self._ocr = None

    # ---------- 基础请求 ----------
    def api_get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        params["_t"] = str(int(time.time() * 1000))
        headers = sign_request(path)
        resp = self.session.get(BASE_URL + path, params=params, headers=headers, timeout=30)
        return resp.json()

    # ---------- 站点与字典 ----------
    def get_site_id(self) -> str:
        if self.site_id:
            return self.site_id
        data = self.api_get("/gpcms/rest/web/v2/index/getDeploymentSiteId",
                            {"domain": "zfcg.czt.fujian.gov.cn"})
        self.site_id = data["data"]["id"]
        return self.site_id

    # ---------- 验证码 ----------
    def _fetch_captcha(self) -> bytes:
        path = "/gpcms/rest/web/v2/index/getVerify"
        headers = sign_request(path)
        resp = self.session.get(BASE_URL + path,
                                params={"_t": str(int(time.time() * 1000))},
                                headers=headers, timeout=30)
        return resp.content

    def _captcha_code(self) -> str:
        if self._ocr is None:
            import ddddocr
            self._ocr = ddddocr.DdddOcr(show_ad=False)
        img = self._fetch_captcha()
        # 放大后识别，提升准确率
        im = Image.open(io.BytesIO(img)).convert("RGB")
        im = im.resize((im.width * 6, im.height * 6), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        code = self._ocr.classification(buf.getvalue())
        return "".join(ch for ch in code if ch.isalnum())

    # ---------- 公告检索 ----------
    def search(self, keyword: str = "", *, start: str = "", end: str = "",
               purchase_nature: str = "3", channel: str = DEFAULT_CHANNEL,
               page_size: int = 10, max_pages: int = 1,
               notice_type: str = DEFAULT_NOTICE_TYPE, retry: int = 8,
               purchaser: str = "", should_stop=None) -> dict:
        """按标题关键词/采购单位检索公告，返回 {keyword, purchaser, total, rows}。

        purchaser: 采购单位名称，按单位筛选（如：福建医科大学附属第一医院）。
        should_stop: 可选回调，返回 True 时提前结束翻页（GUI 停止按钮使用）。
        """
        site_id = self.get_site_id()
        params = {
            "channel": channel,
            "currPage": 1,
            "pageSize": page_size,
            "siteId": site_id,
            "noticeType": notice_type,
            "organizationForm": "!4",
            "purchaseNature": purchase_nature,
            "title": keyword,
            "region": "", "regionCode": "", "cityOrArea": "",
            "purchaseManner": "", "openTenderCode": "",
            "purchaser": purchaser, "agency": "",
            "operationStartTime": start, "operationEndTime": end,
            "verifyCode": "", "selectTimeName": "",
        }
        rows, total = [], None
        path = "/gpcms/rest/web/v2/info/selectInfoForIndex"
        for page in range(1, max_pages + 1):
            if should_stop is not None and should_stop():
                break
            params["currPage"] = page
            for attempt in range(1, retry + 1):
                params["verifyCode"] = self._captcha_code()
                data = self.api_get(path, params)
                if data.get("code") == "200":
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError(
                    f"验证码重试 {retry} 次仍失败（关键词：{keyword or '全部'}，"
                    f"单位：{purchaser or '全部'}）")
            total = data["data"]["total"]
            rows.extend(data["data"]["rows"])
            if page >= (total + page_size - 1) // page_size:
                break
        return {"keyword": keyword, "purchaser": purchaser,
                "total": total, "rows": rows}

    @staticmethod
    def detail_url(row: dict) -> str:
        """生成公告详情页链接。"""
        plan_id = row.get("planId") or ""
        return (f"{BASE_URL}/maincms-web/articleDetail?type=notice&id={row['id']}"
                f"&planId={plan_id}&channel={DEFAULT_CHANNEL}&soure=ggxx")


def save_csv(records: list, out_path: str) -> None:
    fields = ["关键词", "发布时间", "区划", "采购单位", "公告标题", "代理机构",
              "项目编号", "预算(元)", "公告链接"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description="福建省政府采购网公告查询（档案/服务类）")
    parser.add_argument("--keywords", nargs="+", default=[],
                        help="标题关键词，如：档案数字化 病案数字化 档案电子化 档案整理（与 --unit 至少填一个）")
    parser.add_argument("--unit", default="",
                        help="采购单位名称，如：福建医科大学附属第一医院（与 --keywords 至少填一个）")
    parser.add_argument("--start", default="2026-01-01", help="发布时间起，如 2026-01-01")
    parser.add_argument("--end", default="2026-12-31", help="发布时间止，如 2026-12-31")
    parser.add_argument("--purchase-nature", default="3", choices=["1", "2", "3"],
                        help="采购品目：1=货物 2=工程 3=服务（默认 3）")
    parser.add_argument("--notice-type", default=DEFAULT_NOTICE_TYPE,
                        help="公告类型编码（逗号分隔）：采购公告=00101；结果公告=001021,001022,001023,001024,001025,001026,001029,001004,001006；默认全部")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数（默认 10）")
    parser.add_argument("--max-pages", type=int, default=1, help="最多翻页数（默认 1）")
    parser.add_argument("--out", default="结果.csv", help="输出 CSV 文件路径")
    args = parser.parse_args()

    if not args.keywords and not args.unit:
        parser.error("--keywords 与 --unit 至少指定一个")

    start_dt = f"{args.start} 00:00:00" if args.start else ""
    end_dt = f"{args.end} 23:59:59" if args.end else ""

    client = FujianZfcg()
    records, seen = [], set()
    queries = args.keywords or [""]
    for kw in queries:
        result = client.search(kw, start=start_dt, end=end_dt,
                               purchase_nature=args.purchase_nature,
                               notice_type=args.notice_type,
                               page_size=args.page_size, max_pages=args.max_pages,
                               purchaser=args.unit)
        print(f"[关键词:{kw or '全部'} | 单位:{args.unit or '全部'}] "
              f"命中 {result['total']} 条，已取 {len(result['rows'])} 条")
        for r in result["rows"]:
            key = (r["noticeTime"], r["title"])
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "关键词": kw,
                "发布时间": r["noticeTime"],
                "区划": r.get("regionName") or "",
                "采购单位": r["purchaser"],
                "公告标题": r["title"],
                "代理机构": r.get("agency") or "",
                "项目编号": r.get("openTenderCode") or "",
                "预算(元)": r.get("budget") or "",
                "公告链接": client.detail_url(r),
            })

    records.sort(key=lambda x: x["发布时间"], reverse=True)
    save_csv(records, args.out)
    print(f"\n共 {len(records)} 条（去重后），已保存：{args.out}")


if __name__ == "__main__":
    main()
