#!/usr/bin/env python3
"""
单段配音（a2 方案）：

  一次生成整段（保持语调连贯）
    → 裁掉段首/段尾静音
    → 把段内「已有的自然停顿」按标点类型延长到目标时长
    → 响度归一化后导出 wav / mp3

为什么不切分：切分会让 Voicebox 多次独立推理，切口处语调断裂（不够自然）。
延长停顿是在模型自己"想停"的位置上做文章，既保留自然语气，又让停顿长度可控。

用法：
  python narrate_chunk.py --text chunks/chunk_01.txt --outdir out/ --tag part_01
选项：
  --comma-ms   逗号/顿号/分号处停顿目标（默认 350）
  --period-ms  句号/问号/感叹号处停顿目标（默认 600）
  --para-ms    段落之间的停顿目标（默认 800）
  --seed      固定随机种子，跨段一致可压住音色漂移（默认 20260919）
"""
import argparse, json, re, subprocess, sys, time, pathlib, urllib.request
import numpy as np

BASE = "http://127.0.0.1:17493"
PROFILE = "316c2df3-04c7-4a53-89a2-0230f5a11f7c"   # 电台情感故事犀利01-03
SR = 48000
DIG = "零一二三四五六七八九"


# ---------- 文本预处理 ----------
def normalize_numbers(t):
    """阿拉伯数字转中文读法：1982 年 -> 一九八二年（同时去掉数字与单位之间的空格）"""
    t = re.sub(r'(\d{4})\s*(?=年)', lambda m: "".join(DIG[int(c)] for c in m.group(1)), t)
    t = re.sub(r'(\d+)\s*(?=[年月日点%％])', lambda m: "".join(DIG[int(c)] for c in m.group(1)), t)
    t = re.sub(r'\d+', lambda m: "".join(DIG[int(c)] for c in m.group(0)), t)
    return t.strip()


def pause_points(text):
    """按顺序返回 [(标点, 该标点前的累计字数, 类型)]"""
    pts, n = [], 0
    for ch in text:
        if not ch.isspace():
            n += 1
        if ch in "。！？":
            pts.append((ch, n, "period"))
        elif ch in "，、；：":
            pts.append((ch, n, "comma"))
        elif ch == "—":                       # 破折号按逗号级处理
            if not (pts and pts[-1][0] == "—" and pts[-1][1] == n):
                pts.append((ch, n, "comma"))
    # 段落边界（\n\n）也算一个停顿点
    for m in re.finditer(r'\n\s*\n', text):
        before = len(re.sub(r'\s', '', text[:m.start()]))
        pts.append(("¶", before, "para"))
    pts.sort(key=lambda x: x[1])
    return pts


def align(pauses, pts, total, nchar, window=1.2, min_gate=0.04):
    """把音频停顿与文本标点做「单调一对一」匹配。

    返回与 pauses 等长的列表，元素为标点下标或 None（未匹配）。
    只允许按顺序匹配，且时间距离不超过 window 秒；短于 min_gate 的气口直接忽略。
    """
    est = [(pos / nchar * total) for _, pos, _ in pts]
    out, pi = [], 0
    for s, e in pauses:
        if (e - s) < min_gate:
            out.append(None); continue
        mid = (s + e) / 2
        best, bestd = None, window
        for j in range(pi, len(pts)):
            d = abs(est[j] - mid)
            if d < bestd:
                best, bestd = j, d
            if est[j] > mid + window:
                break
        if best is None:
            out.append(None)
        else:
            out.append(best); pi = best + 1
    return out


# ---------- 音频工具 ----------
def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def encode(x, path):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1",
                    "-i", "-", "-c:a", "pcm_s16le", str(path)], input=pcm, check=True)


def detect_pauses(x, thr_db=-45, min_dur=0.03):
    """返回 [(起秒, 止秒)]，含首尾（用于判断裁剪边界）"""
    p = "/tmp/_pd.wav"; encode(x, p)
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af",
                          f"silencedetect=noise={thr_db}dB:d={min_dur}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    total = len(x) / SR
    segs, s0 = [], None
    for ln in err.splitlines():
        if "silence_start:" in ln:
            s0 = float(ln.split("silence_start:")[1].strip())
        elif "silence_end:" in ln and s0 is not None:
            e = float(ln.split("silence_end:")[1].split("|")[0].strip())
            segs.append((s0, e)); s0 = None
    if s0 is not None:
        segs.append((s0, total))
    return segs, total


def api(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=timeout)
    return r.read() if path.startswith("/audio/") else json.loads(r.read())


def generate(text, seed, timeout=900, max_chunk_chars=0, crossfade_ms=50,
             personality=False, instruct=""):
    chunks_setting = max_chunk_chars if max_chunk_chars > 0 else max(1000, len(text) + 100)
    body = {"profile_id": PROFILE, "text": text, "language": "zh",
            "seed": seed, "model_size": "1.7B", "engine": "qwen",
            "max_chunk_chars": chunks_setting,
            "crossfade_ms": crossfade_ms, "normalize": True,
            "personality": bool(personality)}
    if instruct:
        body["instruct"] = instruct[:500]
    r = api("/generate", body)
    gid = r["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            h = api(f"/history/{gid}", timeout=20)
        except Exception:
            time.sleep(2); continue
        st = (h.get("status") or "").lower()
        if st == "completed":
            return gid, h
        if st in ("failed", "cancelled", "error"):
            raise RuntimeError(f"生成失败 status={st} err={h.get('error')}")
        if int(time.time() - t0) % 15 < 3:
            print(f"      …{st} {time.time()-t0:.0f}s", flush=True)
        time.sleep(3)
    raise RuntimeError("生成超时")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="段落文本文件")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--tag", default="part_01")
    ap.add_argument("--comma-ms", type=float, default=350)
    ap.add_argument("--period-ms", type=float, default=600)
    ap.add_argument("--para-ms", type=float, default=800)
    ap.add_argument("--keep-ms", type=float, default=60, help="首尾保留的静音余量")
    ap.add_argument("--min-gap-ms", type=float, default=40,
                    help="只有现有停顿不短于该值才延长（默认 40ms，调大则只处理明显的停顿）")
    ap.add_argument("--max-chunk-chars", type=int, default=0,
                    help="交给 Voicebox 内部长文本分段：每段字符数（0=关闭，整段一次生成）。"
                         "配合 --crossfade-ms 使用")
    ap.add_argument("--crossfade-ms", type=int, default=50,
                    help="长文本模式下段间交叉淡入毫秒数（默认 50）")
    ap.add_argument("--personality", action="store_true",
                    help="Voicebox 的「人物设定朗读」：注意它会把输入文本当指令、交由 LLM 演绎，"
                         "不保证逐字朗读，配固定稿件时不要用")
    ap.add_argument("--instruct", default="",
                    help="风格指令（不改动文本内容），如「语速平缓、停顿自然、安静柔和」")
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--no-extend", action="store_true", help="只生成+裁首尾，不延长停顿")
    ap.add_argument("--reuse-raw", action="store_true",
                    help="复用已有的 raw/<tag>_raw.wav，不重新调 Voicebox（调参时用）")
    ap.add_argument("--out-suffix", default="", help="给最终文件名加后缀，如 v2")
    args = ap.parse_args()

    od = pathlib.Path(args.outdir)
    for sub in ("raw", "prep", "out"):
        (od / sub).mkdir(parents=True, exist_ok=True)

    raw_text = pathlib.Path(args.text).read_text(encoding="utf-8").strip()
    # 允许文本为了阅读而换行：单个换行不当作断句（只有空行才是段落分隔），
    # 这样你在编辑器里怎么折行都不会影响音频。
    raw_text = re.sub(r'(?<!\n)\n(?!\n)', '', raw_text)
    text = normalize_numbers(raw_text)
    (od / "prep" / f"{args.tag}_text.txt").write_text(text + "\n", encoding="utf-8")
    print(f"文本 {len(re.sub(chr(92)+'s', '', text))} 字（已存 prep/{args.tag}_text.txt）")
    if text != raw_text:
        print(f"  数字已转中文读法：{len(raw_text)} -> {len(text)} 字符")

    raw = od / "raw" / f"{args.tag}_raw.wav"
    if args.reuse_raw and raw.exists():
        gid = "(复用)"
        print(f"[1/5] 复用已生成的原始音频 {raw}")
    else:
        print(f"[1/5] 生成（seed={args.seed}, 一次成段"
              f"{', 人物设定朗读' if args.personality else ''}）…")
        if args.max_chunk_chars > 0:
            print(f"      启用 Voicebox 长文本：每 {args.max_chunk_chars} 字一段，"
                  f"交叉淡入 {args.crossfade_ms}ms")
        gid, h = generate(text, args.seed, max_chunk_chars=args.max_chunk_chars,
                          crossfade_ms=args.crossfade_ms, personality=args.personality,
                          instruct=args.instruct)
        raw.write_bytes(api(f"/audio/{gid}"))
        print(f"      id={gid[:8]}  时长 {h.get('duration'):.2f}s  → {raw}")

    x = decode(raw)
    segs, total = detect_pauses(x)
    # 裁首尾静音
    keep = args.keep_ms / 1000
    lead = segs[0][1] if segs and segs[0][0] <= 0.02 else 0.0
    tail = segs[-1][0] if segs and segs[-1][1] >= total - 0.02 else total
    a = max(0.0, lead - keep); b = min(total, tail + keep)
    x = x[int(a * SR):int(b * SR)]
    print(f"[2/5] 裁首尾静音：{a:.2f}s ~ {b:.2f}s（原 {total:.2f}s → {len(x)/SR:.2f}s）")

    segs, total = detect_pauses(x)
    inner = [(s, e) for s, e in segs if s > 0.03 and e < total - 0.03]
    pts = pause_points(text)
    nchar = len(re.sub(r'\s', '', text)) or 1
    targets = {"comma": args.comma_ms, "period": args.period_ms, "para": args.para_ms}

    report = [f"tag: {args.tag}", f"生成 id: {gid}", f"seed: {args.seed}",
              f"原时长 {total:.2f}s，检测到内部停顿 {len(inner)} 个，"
              f"文本标点 {len(pts)} 个", ""]
    print(f"[3/5] 停顿配方（检测 {len(inner)} 个停顿 / 文本 {len(pts)} 个标点）：")

    match = align(inner, pts, total, nchar, min_gate=args.min_gap_ms / 1000)
    rows = []
    for i, ((s, e), mi) in enumerate(zip(inner, match), 1):
        cur = (e - s) * 1000
        if mi is None:
            rows.append((i, s, e, "句内气口/未匹配", cur, None))
            continue
        ch, pos, kind = pts[mi]
        tgt = targets[kind]
        rows.append((i, s, e, ch, cur, tgt if not args.no_extend else None))

    for i, s, e, ch, cur, tgt in rows:
        action = f"→ {tgt:.0f}ms" if tgt and tgt > cur else ("保持" if tgt else "不处理")
        print(f"    #{i:<3} @{s:6.2f}s  现有 {cur:5.0f}ms  [{ch}]  {action}")
        report.append(f"#{i} @{s:.3f}s 现有{cur:.0f}ms [{ch}] {action}")

    ext = [r for r in rows if r[5] and r[5] > r[4]]
    print(f"    匹配到标点 {sum(1 for r in rows if r[3] not in ('句内气口/未匹配',))} 处，"
          f"其中需延长 {len(ext)} 处，句内气口保持原样 "
          f"{sum(1 for r in rows if r[3] == '句内气口/未匹配')} 处")

    if not args.no_extend:
        add = 0
        for i, s, e, ch, cur, tgt in reversed(rows):
            if not tgt or tgt <= cur:
                continue
            need = int(round((tgt / 1000 - (e - s)) * SR))
            if need <= 0:
                continue
            pos = int(round((s + e) / 2 * SR))
            x = np.concatenate([x[:pos], np.zeros(need, dtype=np.float32), x[pos:]])
            add += need
        print(f"[4/5] 共延长 {add/SR:.2f}s 静音 → 新时长 {len(x)/SR:.2f}s")
    else:
        print("[4/5] 跳过延长停顿")
    encode(x, od / "prep" / f"{args.tag}{args.out_suffix}_extended.wav")

    final = od / "out" / f"{args.tag}{args.out_suffix}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(od / "prep" / f"{args.tag}{args.out_suffix}_extended.wav"),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                           "aformat=channel_layouts=mono,alimiter=limit=0.95:level=0",
                    "-c:a", "pcm_s16le", str(final)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(final),
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    str(final.with_suffix(".mp3"))], check=True)
    print(f"[5/5] 完成：{final}（{len(decode(final))/SR:.2f}s）+ {final.with_suffix('.mp3').name}")
    (od / "prep" / f"{args.tag}{args.out_suffix}_pauses.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"      停顿配方报告：prep/{args.tag}{args.out_suffix}_pauses.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr); sys.exit(1)
