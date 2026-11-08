#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拉取 X(Twitter) 视频页面里的「视频文件 + 描述信息」。

用法:
  # 从文件读取（每行一个 URL，默认 urls.txt）
  python3 pull_x_videos.py
  python3 pull_x_videos.py urls.txt

  # 直接传 URL
  python3 pull_x_videos.py https://x.com/xxx/status/123/video/1 https://x.com/yyy/status/456

  # 从管道/剪贴板读取
  cat urls.txt | python3 pull_x_videos.py

  # 遇到需要登录才能看的内容时，带上浏览器 cookie
  python3 pull_x_videos.py --cookies-from-browser chrome

依赖:
  - yt-dlp   (系统已装: /opt/homebrew/bin/yt-dlp)
  - ffmpeg   (合成音视频用，系统已装)

输出:
  downloads/<上传者>_<视频ID>.mp4        视频文件
  downloads/metadata.json                全部元数据的机器可读汇总
  downloads/描述汇总.md                  可读的描述信息汇总
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


def collect_urls(args):
    """按优先级收集 URL：命令行参数 > 输入文件 > 标准输入（互斥，命令行优先）"""
    if args.urls:
        return list(args.urls)
    if args.input and os.path.exists(args.input):
        urls = []
        with open(args.input, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        if urls:
            return urls
    # 最后尝试从 stdin 读取（支持管道）
    if not sys.stdin.isatty():
        urls = []
        for line in sys.stdin:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
        if urls:
            return urls
    return []


def build_cmd(url, out_dir, cookies_browser):
    # 下载并把完整元数据写入 <文件名>.info.json（本机 yt-dlp 的 -J 不落盘视频，故用此方式）
    cmd = [
        "yt-dlp",
        "-f", "bv*+ba/best",                     # 最佳视频+音频；失败回退 best
        "--no-overwrites",                       # 已存在则跳过
        "-o", os.path.join(out_dir, "%(uploader_id)s_%(id)s.%(ext)s"),
        "--restrict-filenames",                  # 文件名去掉空格/特殊字符
        "--write-info-json",                     # 落盘元数据，便于读取描述等信息
        "--sleep-interval", "1",                 # 礼貌限速，降低被限流概率
        "--max-sleep-interval", "3",
    ]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd.append(url)
    return cmd


def final_filename(out_dir, info):
    """从 info.json 中尽量准确地拿到最终视频文件名"""
    for key in ("filepath",):
        fp = info.get(key)
        if fp:
            return os.path.basename(fp)
    for rd in (info.get("requested_downloads") or []):
        fp = rd.get("filepath") or rd.get("filename")
        if fp:
            return os.path.basename(fp)
    # 兜底：按 id 在目录里找非 info 文件
    vid = info.get("id", "")
    if os.path.isdir(out_dir) and vid:
        for fn in sorted(os.listdir(out_dir)):
            if vid in fn and not fn.endswith(".info.json"):
                return fn
    return ""


def pull_one(url, out_dir, cookies_browser, index, total):
    print(f"[{index}/{total}] 处理: {url}")
    cmd = build_cmd(url, out_dir, cookies_browser)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"    ✗ 超时: {url}")
        return None

    if res.returncode != 0:
        tail = "\n".join(res.stderr.strip().splitlines()[-8:])
        print(f"    ✗ 失败 (code {res.returncode}): {url}\n{tail}")
        return None

    # 定位本视频的 info.json：取输出目录里最近修改的那个
    candidates = []
    if os.path.isdir(out_dir):
        candidates = [f for f in os.listdir(out_dir) if f.endswith(".info.json")]
    if not candidates:
        print("    ✗ 未生成 info.json")
        return None
    # 取最新修改的 info.json
    info_path = os.path.join(out_dir, max(candidates, key=lambda f: os.path.getmtime(os.path.join(out_dir, f))))
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"    ✗ 无法解析 {os.path.basename(info_path)}")
        return None

    vid = info.get("id", "")
    title = info.get("title", "")
    uploader = info.get("uploader", "")
    uploader_id = info.get("uploader_id", "")
    upload_date = info.get("upload_date", "")
    description = (info.get("description") or "").strip()
    webpage_url = info.get("webpage_url") or url
    filename = final_filename(out_dir, info)

    print(f"    ✓ 已保存: {filename}")
    if description:
        print(f"    描述: {description[:60]}{'…' if len(description) > 60 else ''}")
    else:
        print("    描述: (空)")

    return {
        "id": vid,
        "url": webpage_url,
        "title": title,
        "uploader": uploader,
        "uploader_id": uploader_id,
        "upload_date": upload_date,
        "description": description,
        "filename": filename,
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
    }


def write_outputs(out_dir, records):
    meta_path = os.path.join(out_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(out_dir, "描述汇总.md")
    lines = ["# X 视频描述信息汇总", "", f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"> 共 {len(records)} 条", ""]
    for i, r in enumerate(records, 1):
        lines.append(f"## {i}. {r['title']}  ")
        lines.append("")
        lines.append(f"- **作者**: {r['uploader']} (@{r['uploader_id']})")
        lines.append(f"- **发布日期**: {r['upload_date']}")
        lines.append(f"- **视频文件**: {r['filename']}")
        lines.append(f"- **原链接**: {r['url']}")
        if r.get("view_count") is not None:
            lines.append(f"- **播放量**: {r['view_count']}")
        if r.get("like_count") is not None:
            lines.append(f"- **点赞**: {r['like_count']}")
        lines.append("")
        lines.append("**描述:**")
        lines.append("")
        lines.append(r["description"] if r["description"] else "_(无描述)_")
        lines.append("")
        lines.append("---")
        lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n汇总已写入:\n  {meta_path}\n  {md_path}")


def main():
    parser = argparse.ArgumentParser(description="拉取 X 视频页面里的视频与描述信息")
    parser.add_argument("urls", nargs="*", help="一个或多个 X 视频页 URL")
    parser.add_argument("-i", "--input", default=os.path.join(HERE, "urls.txt"),
                        help="包含 URL 列表的文件（每行一个），默认 urls.txt")
    parser.add_argument("-o", "--out", default=os.path.join(HERE, "downloads"),
                        help="输出目录，默认 downloads/")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER",
                        help="需要登录时指定浏览器，如 chrome / firefox")
    args = parser.parse_args()

    if shutil.which("yt-dlp") is None:
        print("✗ 未找到 yt-dlp，请先安装: brew install yt-dlp")
        sys.exit(1)

    urls = collect_urls(args)
    if not urls:
        print("✗ 没有读到任何 URL。请传入参数、提供 urls.txt，或通过管道输入。")
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    print(f"共 {len(urls)} 个视频，输出目录: {args.out}\n")

    records = []
    for i, url in enumerate(urls, 1):
        rec = pull_one(url, args.out, args.cookies_from_browser, i, len(urls))
        if rec:
            records.append(rec)

    print(f"\n成功 {len(records)} / {len(urls)}")
    if records:
        write_outputs(args.out, records)


if __name__ == "__main__":
    main()
