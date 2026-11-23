#!/usr/bin/env python3
"""为 tts_speakers.csv 中的每个音色生成一段约 10 秒的中文试听音频。

文件以音色中文名命名（name_hint），输出 mp3 便于预览。
默认先生成 2 个，确认效果后再用 --limit 0 跑全部。

用法：
    python3 gen_voice_samples.py --limit 2
    python3 gen_voice_samples.py --limit 0            # 全部
    python3 gen_voice_samples.py --limit 0 --offset 2 # 从第 3 个开始
"""
import argparse
import asyncio
import csv
import glob
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from universal_tts import generate_voice_with_meta

CSV_PATH = os.path.join(HERE, "..", "data", "tts_speakers.csv")
DEFAULT_OUT = os.path.join(HERE, "..", "data", "音色试听")
# 书稿库根目录：优先用环境变量，避免绑定具体机器的绝对路径。
# 默认指向常见的「Product/WeChatArticle/十分钟读完一本书」布局，可用 BOOK_ROOT 覆盖。
BOOK_ROOT = os.environ.get("BOOK_ROOT", "").strip() or os.path.join(
    os.path.expanduser("~"), "Product", "WeChatArticle", "十分钟读完一本书"
)

# 备用固定文本（当用户要求统一文案时用），默认走随机书稿摘取
DEMO_TEXT = (
    "大家好呀，欢迎来到音色试听。"
    "今天为你准备了一段简单的话，想请你来听听看，"
    "这个声音是不是你喜欢的样子呀。"
)

_HAN = re.compile(r"[\u4e00-\u9fff]")
# 需要剔除的标点/符号（保留中文逗号句号问号叹号书名号）
_DROP = re.compile(r"[「」『』\"'`“”‘’\(\)（）\[\]【】—…·\-\—\r\n\t ]+")


def _clean_line(line: str) -> str:
    """把一段书稿正文清洗成适合 TTS 朗读的纯中文句子。"""
    line = line.strip()
    # 跳过开场白/结尾固定句/标题/空行/过短行
    if not line or line.startswith("#") or "大家好" in line[:12]:
        return ""
    if "十分钟读完一本书" in line or "今天想跟你聊" in line[:15]:
        return ""
    if len(_HAN.findall(line)) < 60:  # 太短的段落不适合截取
        return ""
    line = _DROP.sub("", line)
    # 只保留 中文/数字/中文标点，去掉英文与残留符号
    line = re.sub(r"[^\u4e00-\u9fff0-9，。！？、；：《》]", "", line)
    return line


def load_book_sentences():
    """从所有书稿正文中抽取句子池，返回 [句子, ...]。"""
    pool = []
    files = glob.glob(os.path.join(BOOK_ROOT, "2026-11", "*", "*_.md"))
    files += glob.glob(os.path.join(BOOK_ROOT, "2026-12", "*", "*_.md"))
    for f in files:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                cleaned = _clean_line(line)
                if not cleaned:
                    continue
                # 按中文句末标点切句
                for sent in re.split(r"(?<=[。！？])", cleaned):
                    n = len(_HAN.findall(sent))
                    if 18 <= n <= 120:  # 单句长度适中
                        pool.append(sent)
    return pool


def build_text(sentences, min_han=50, max_han=62):
    """随机挑连续句子拼出 >=50 字的一段文字稿（尽量控制在 50~70 字）。"""
    for _ in range(200):
        start = random.randrange(len(sentences))
        parts, total = [], 0
        j = start
        while j < len(sentences) and total < max_han:
            s = sentences[j]
            n = len(_HAN.findall(s))
            if total + n > max_han + 14 and parts:  # 不超过 ~76 字
                break
            parts.append(s)
            total += n
            j += 1
        if total >= min_han:
            return "".join(parts)
    # 兜底：循环拼接到够数
    parts, total = [], 0
    while total < min_han:
        s = random.choice(sentences)
        parts.append(s)
        total += len(_HAN.findall(s))
    return "".join(parts)


def load_speakers():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    data = [
        r for r in rows
        if r and not r[0].startswith("#") and r[0].strip().lower() != "speaker_id"
    ]
    return [{"id": r[0], "name": r[1], "cat": r[2] if len(r) > 2 else ""} for r in data]


def duration(path):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path], text=True
        ).strip()
        return float(out)
    except Exception:
        return -1.0


def to_mp3(ogg, mp3):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", ogg,
         "-codec:a", "libmp3lame", "-q:a", "2", mp3],
        check=True,
    )


async def gen_one(sp, outdir, idx, total, text):
    name = sp["name"]
    ogg = os.path.join("/tmp", f"jy_voice_{idx}.ogg")
    mp3 = os.path.join(outdir, f"{name}.mp3")
    han = len(_HAN.findall(text))
    print(f"[{idx}/{total}] {name}  <{sp['id']}>  [{han}字] {text[:24]}…", flush=True)
    try:
        path, backend = await generate_voice_with_meta(
            text, ogg, speaker=sp["id"],
            backend="sami", allow_fallback=False, sami_retries=2,
        )
        if backend != "sami" or not path or not os.path.isfile(path):
            print(f"    ✗ 合成失败: {path}", flush=True)
            return False
        dur = duration(path)
        to_mp3(path, mp3)
        size = os.path.getsize(mp3) // 1024
        print(f"    ✓ {mp3}  ({dur:.2f}s, {size}KB)", flush=True)
        return {"name": name, "speaker": sp["id"], "text": text, "han": han, "dur": dur}
    except Exception as e:
        print(f"    ✗ 异常: {e}", flush=True)
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="生成数量，0=全部")
    ap.add_argument("--offset", type=int, default=0, help="从第几个音色开始")
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--fixed", action="store_true", help="用统一固定文案（默认随机书稿）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子，便于复现")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    speakers = load_speakers()
    subset = speakers[args.offset:]
    if args.limit > 0:
        subset = subset[: args.limit]
    total = len(subset)

    sentences = [] if args.fixed else load_book_sentences()
    if not args.fixed:
        print(f"书稿句子池: {len(sentences)} 句", flush=True)
        if not sentences:
            print("✗ 句子池为空，检查 BOOK_ROOT", flush=True)
            return

    os.makedirs(args.outdir, exist_ok=True)
    print(f"音色库共 {len(speakers)} 个，本次生成 {total} 个 -> {args.outdir}\n", flush=True)

    results = []
    for i, sp in enumerate(subset, 1):
        text = DEMO_TEXT if args.fixed else build_text(sentences)
        r = await gen_one(sp, args.outdir, i, total, text)
        if r:
            results.append(r)

    # 文案落盘备查（合并已有记录，支持分批跑）
    log = os.path.join(args.outdir, "文案对照.csv")
    header = ["音色中文名", "speaker_id", "字数", "时长秒", "文案"]
    merged = {}
    if os.path.exists(log):
        with open(log, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if row and len(row) >= 5 and row[0] != header[0]:
                    merged[row[1]] = row  # 以 speaker_id 去重
    for r in results:
        merged[r["speaker"]] = [r["name"], r["speaker"], r["han"], f"{r['dur']:.2f}", r["text"]]
    with open(log, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in merged.values():
            w.writerow(row)
    print(f"\n完成：本次成功 {len(results)}/{total}，文案对照累计 {len(merged)} 条 -> {log}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
