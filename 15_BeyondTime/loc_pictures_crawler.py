#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loc_pictures_crawler.py
=======================
爬取 Library of Congress 图片搜索结果（默认 q=mrg，gallery 排序）。

关键说明
--------
- www.loc.gov 与图片域名 tile.loc.gov 都前置了 Cloudflare 机器人校验。
  普通请求会被拦截（返回 "Just a moment..."）。本脚本使用纯 requests 实现，
  **Cloudflare 绕过由你手动完成**：在浏览器里通过一次人机验证后，从开发者工具
  复制 cookie（至少包含 cf_clearance），通过下面任一方式提供给脚本即可：
      * --cookies cookies.json   （浏览器导出的 JSON，含 name/value/domain）
      * --cookie  "cf_clearance=xxxx; other=yyy"   （直接粘 header 字符串）
      * 环境变量 LOC_COOKIES="cf_clearance=xxxx"
  如果你在本机普通网络环境下运行，Cloudflare 可能根本不拦，可不加 cookie 直接跑。

- 搜索结果 JSON 中没有独立的「描述」字段，因此「说明信息」由
  标题 + 主题词 + 载体 + 日期 组合而成，并翻译为中文。

输出结构
--------
  <output>/
    001-010/
      0001.jpg            （图片本体，来自 tile.loc.gov）
      0001_说明.txt       （英文原文 + 中文翻译，一张图对应一份说明）
      0001_meta.json      （完整元数据）
    011-020/
      ...

依赖
----
    pip install requests deep-translator

用法
----
    # 先爬 2 页看看效果（推荐）
    python loc_pictures_crawler.py --pages 2 --cookies cookies.json

    # 爬全部（脚本会自动检测真实总页数，当前约 469 页）
    python loc_pictures_crawler.py --cookies cookies.json

    # 只抓元数据、不下载图片（快速验证结构）
    python loc_pictures_crawler.py --pages 2 --no-download
"""

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

# 全局 socket 超时（秒）：防止个别请求无限挂起（翻译/下载网络异常时快速失败）
socket.setdefaulttimeout(20)

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


# ----------------------------- 配置 ---------------------------------------
BASE_URL = "https://www.loc.gov/pictures/search/"
QUERY = "mrg"
SORT = "gallery"            # st=gallery：按画廊排序
PER_PAGE_DEFAULT = 25       # 站点默认每页 25 条
IMG_HOST = "tile.loc.gov"   # 图片实际托管域名

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA}


# ----------------------------- Cookie -------------------------------------
def load_cookies(args) -> "requests.cookies.RequestsCookieJar":
    """从 --cookies / --cookie / 环境变量 载入 cookie 到 Jar 中。"""
    jar = requests.cookies.RequestsCookieJar()
    raw = None
    if args.cookies and os.path.isfile(args.cookies):
        try:
            data = json.load(open(args.cookies, encoding="utf-8"))
            # 浏览器导出格式：[{name,value,domain,path} ...]
            if isinstance(data, list):
                for c in data:
                    name = c.get("name")
                    value = c.get("value")
                    domain = (c.get("domain") or "").lstrip(".")
                    if name:
                        jar.set(name, value, domain=domain or None,
                                path=c.get("path", "/"))
                print(f"已从 {args.cookies} 载入 {len(data)} 条 cookie")
                return jar
            # 也可能是 {name: value} 字典
            if isinstance(data, dict):
                for k, v in data.items():
                    jar.set(k, v)
                return jar
        except Exception as e:
            print(f"[警告] 解析 cookies.json 失败: {e}")
    # 直接字符串形式：--cookie "a=1; b=2" 或 环境变量
    raw = args.cookie or os.environ.get("LOC_COOKIES")
    if raw:
        for pair in raw.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                jar.set(k.strip(), v.strip())
    return jar


# ----------------------------- 翻译 ---------------------------------------
_translators = None
_trans_cache = {}
_PREF = "auto"  # 翻译器偏好：auto / google / mymemory


def get_translators(pref: str = "auto"):
    """构造翻译器列表：Google 优先，MyMemory 兜底（无需 key）。"""
    global _translators
    if _translators is not None:
        return _translators
    _translators = []
    want = []
    if pref == "auto":
        want = ["google", "mymemory"]
    elif pref == "google":
        want = ["google"]
    elif pref == "mymemory":
        want = ["mymemory"]
    for name in want:
        try:
            if name == "google" and GoogleTranslator is not None:
                _translators.append(GoogleTranslator(source="en", target="zh-CN"))
            elif name == "mymemory":
                from deep_translator import MyMemoryTranslator
                _translators.append(MyMemoryTranslator(source="en-US", target="zh-CN"))
        except Exception as e:
            print(f"[警告] 初始化翻译器 {name} 失败: {e}")
    if not _translators:
        print("[警告] 未配置任何可用翻译器，说明将仅保留英文原文。")
    return _translators


def translate(text: str, pref: str = None) -> str:
    """英文 -> 中文；失败返回空串（保留原文）。带缓存以复用重复文本。"""
    pref = pref or _PREF
    if not text or not text.strip():
        return ""
    if text in _trans_cache:
        return _trans_cache[text]
    out = ""
    for tr in get_translators(pref):
        try:
            out = tr.translate(text[:4500]) or ""
            if out:
                break
        except Exception:
            out = ""
    _trans_cache[text] = out
    return out


# ----------------------------- 字段提取 -----------------------------------
def _as_str(v):
    if isinstance(v, list):
        return v[0] if v else ""
    return v if v else ""


def extract_item(item: dict) -> dict:
    """从单条搜索结果中提取基本信息（已按真实 JSON 结构调整）。"""
    title = _as_str(item.get("title"))

    subjects = item.get("subjects") or []
    if not isinstance(subjects, list):
        subjects = [subjects]
    subjects = [str(s) for s in subjects if s]

    medium = _as_str(item.get("medium"))
    date = item.get("created_published_date") or item.get("created_pub_date") or ""

    creator = item.get("creator") or ""
    if isinstance(creator, dict):
        creator = creator.get("name") or creator.get("value") or ""
    elif isinstance(creator, list):
        creator = ", ".join(str(c) for c in creator)

    image = item.get("image") or {}
    image_url = image.get("full") or image.get("thumb") or ""
    links = item.get("links") or {}
    item_url = links.get("item") or links.get("resource") or ""

    return {
        "title": title,
        "subjects": subjects,
        "medium": medium,
        "date": date,
        "creator": creator,
        "image_url": image_url,
        "url": item_url,
    }


def build_desc_en(m: dict) -> str:
    parts = []
    if m["title"]:
        parts.append(m["title"])
    if m["subjects"]:
        parts.append("Subjects: " + "; ".join(m["subjects"]))
    if m["medium"]:
        parts.append("Medium: " + m["medium"])
    if m["date"]:
        parts.append("Date: " + str(m["date"]))
    return ". ".join(parts)


def build_desc_zh(m: dict) -> str:
    parts = []
    zh_title = translate(m["title"])
    if zh_title:
        parts.append(zh_title)
    zh_subj = translate("; ".join(m["subjects"])) if m["subjects"] else ""
    if zh_subj:
        parts.append("主题：" + zh_subj)
    zh_med = translate(m["medium"]) if m["medium"] else ""
    if zh_med:
        parts.append("载体：" + zh_med)
    if m["date"]:
        parts.append("日期：" + str(m["date"]))
    return "。".join(parts)


# --------------------------- 请求与下载 -----------------------------------
def fetch_json(session: requests.Session, url: str, max_retry: int = 4) -> dict:
    for attempt in range(1, max_retry + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=60)
        except Exception as e:
            print(f"  [retry {attempt}] 请求异常: {e}")
            time.sleep(3)
            continue
        body = r.text.strip()
        if r.status_code == 200 and (body.startswith("{") or body.startswith("[")):
            return json.loads(body)
        if "Just a moment" in body or "challenges.cloudflare.com" in body:
            print(f"  [retry {attempt}] 被 Cloudflare 拦截，请检查 cookie 是否有效")
        else:
            print(f"  [retry {attempt}] HTTP {r.status_code}，非预期响应")
        time.sleep(3 + attempt * 2)
    raise RuntimeError("无法获取 JSON（持续被 Cloudflare 拦截或请求失败）")


# 图片下载专用请求头：tile.loc.gov 需带 Referer 才放行
IMG_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.loc.gov/",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


def download_image(session: requests.Session, url: str, path: Path, timeout: int = 40) -> bool:
    try:
        r = session.get(url, headers=IMG_HEADERS, timeout=timeout, stream=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        else:
            print(f"    [下载异常] HTTP {r.status_code} / {r.headers.get('content-type')}")
    except Exception as e:
        print(f"    [下载失败] {e}")
    return False


def safe_name(s: str, max_len: int = 50) -> str:
    s = s.strip().replace("\n", " ").replace("\r", " ")
    s = "".join(c for c in s if c not in r'\\/:*?"<>|')
    return s[:max_len] or "untitled"


def get_total_pages(data: dict) -> int:
    pages = data.get("pages") or {}
    last_url = pages.get("last") or ""
    m = re.search(r"[?&]sp=(\d+)", last_url)
    return int(m.group(1)) if m else 0


# ------------------------------ 主流程 ------------------------------------
def main():
    ap = argparse.ArgumentParser(description="LOC 图片爬虫（每10张一文件夹，说明中英对照）")
    ap.add_argument("--pages", type=int, default=0,
                    help="要爬取的页数（默认 0 = 自动检测并爬全部）")
    ap.add_argument("--start-page", type=int, default=1, help="起始页码（默认 1）")
    ap.add_argument("--per-page", type=int, default=PER_PAGE_DEFAULT,
                    help=f"每页条数（默认 {PER_PAGE_DEFAULT}）")
    ap.add_argument("--output", default="loc_pictures_output", help="输出根目录")
    ap.add_argument("--delay", type=float, default=2.0, help="页面间请求间隔（秒）")
    ap.add_argument("--img-delay", type=float, default=0.5, help="图片间下载间隔（秒）")
    ap.add_argument("--no-download", action="store_true", help="只抓元数据、不下载图片")
    ap.add_argument("--cookies", default=None, help="cookie JSON 文件路径（浏览器导出）")
    ap.add_argument("--cookie", default=None, help='cookie 字符串，如 "cf_clearance=xxx"')
    ap.add_argument("--from-json", default=None,
                    help="本地已保存的搜索页 JSON 文件或目录（离线处理，配合手动绕过 Cloudflare 使用）")
    ap.add_argument("--translator", default="auto", choices=["auto", "google", "mymemory"],
                    help="翻译器：auto=Google优先/MyMemory兜底; 受限网络可用 mymemory")
    args = ap.parse_args()

    global _PREF
    _PREF = args.translator
    get_translators(args.translator)  # 提前初始化并输出可用翻译器

    jar = load_cookies(args)
    session = requests.Session()
    session.cookies = jar
    session.headers.update(HEADERS)

    out_root = Path(args.output)
    out_root.mkdir(parents=True, exist_ok=True)

    per_page = args.per_page

    # ---- 准备页面数据：本地离线 或 网络实时 ----
    first_data = None
    if args.from_json:
        src = Path(args.from_json)
        files = sorted(src.glob("*.json")) if src.is_dir() else [src]
        pages_data = []
        for f in files:
            try:
                d = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[警告] 读取 {f} 失败: {e}")
                continue
            if not isinstance(d, dict):
                print(f"[警告] {f} 不是有效的搜索页 JSON（顶层应为对象），跳过")
                continue
            pages_data.append(d)
        if not pages_data:
            print("未读取到任何 JSON 页面数据，退出。"); sys.exit(1)
        target_pages = args.pages if args.pages > 0 else len(pages_data)
        pages_data = pages_data[:target_pages]
        print(f"离线模式：载入 {len(pages_data)} 个本地页面")
    else:
        first_url = BASE_URL + f"?q={QUERY}&st={SORT}&sp={args.start_page}&c={per_page}&fo=json"
        print(f"抓取首页: {first_url}")
        first_data = fetch_json(session, first_url)
        total_pages = get_total_pages(first_data)
        if total_pages:
            print(f"检测到真实总页数：{total_pages} 页（约 {total_pages*per_page} 条）")
        target_pages = args.pages if args.pages > 0 else (total_pages or 1)

    img_index = (args.start_page - 1) * per_page
    done = 0

    for idx in range(target_pages):
        if args.from_json:
            data = pages_data[idx]
            print(f"\n[本地页 {idx + 1}] 处理")
        else:
            if idx == 0:
                data = first_data
                sp = args.start_page
            else:
                sp = args.start_page + idx
                url = BASE_URL + f"?q={QUERY}&st={SORT}&sp={sp}&c={per_page}&fo=json"
                print(f"\n[{sp}] 抓取: {url}")
                data = fetch_json(session, url)

        results = data.get("results") or []
        if not results:
            print("  本页无结果，结束。")
            break

        for item in results:
            m = extract_item(item)
            folder_no = img_index // 10
            fstart = folder_no * 10 + 1
            fend = fstart + 9
            folder = out_root / f"{fstart:03d}-{fend:03d}"
            folder.mkdir(parents=True, exist_ok=True)

            seq = f"{img_index + 1:04d}"
            desc_en = build_desc_en(m)
            desc_zh = build_desc_zh(m)

            # 说明信息文件（一张图对应一份，含中文翻译）
            desc_file = folder / f"{seq}_说明.txt"
            with open(desc_file, "w", encoding="utf-8") as f:
                f.write("【标题】\n" + (m["title"] or "（无）") + "\n")
                f.write("【标题·中文】\n" + (translate(m["title"]) or "（无）") + "\n\n")
                f.write("【主题词】\n" + ("; ".join(m["subjects"]) or "（无）") + "\n")
                f.write("【主题词·中文】\n"
                        + ((translate("; ".join(m["subjects"])) if m["subjects"] else "") or "（无）") + "\n\n")
                f.write("【创作者】 " + (m["creator"] or "（未知）") + "\n")
                f.write("【日期】 " + (str(m["date"]) or "（未知）") + "\n")
                f.write("【载体】 " + (m["medium"] or "（未知）") + "\n")
                f.write("【图片直链】 " + (m["image_url"] or "（无）") + "\n")
                f.write("【来源页面】 " + (m["url"] or "（无）") + "\n\n")
                f.write("【说明（英文）】\n" + (desc_en or "（无）") + "\n\n")
                f.write("【说明（中文）】\n" + (desc_zh or "（翻译不可用，见英文原文）") + "\n")

            # 完整元数据
            with open(folder / f"{seq}_meta.json", "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)

            # 下载图片
            if not args.no_download and m["image_url"]:
                ext = os.path.splitext(urlparse(m["image_url"]).path)[1] or ".jpg"
                img_path = folder / f"{seq}{ext}"
                if not img_path.exists():
                    ok = download_image(session, m["image_url"], img_path)
                    print(f"    {seq} {'(OK)' if ok else '(FAIL)'} {safe_name(m['title'], 36)}")
                    time.sleep(args.img_delay)
                else:
                    print(f"    {seq} (已存在，跳过)")
            else:
                print(f"    {seq} {safe_name(m['title'], 36)}")

            img_index += 1

        done += 1
        if not args.from_json and idx < target_pages - 1 and not args.no_download:
            time.sleep(args.delay)

    print(f"\n完成：共处理 {img_index - (args.start_page - 1) * per_page} 张图片，"
          f"{done} 页。输出目录：{out_root}")


if __name__ == "__main__":
    main()
