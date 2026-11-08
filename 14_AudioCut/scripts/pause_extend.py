#!/usr/bin/env python3
"""
把音频里「已有的自然停顿」延长到指定时长（保持整句一次生成的自然语调）

思路：不切分文本重新生成，而是在单次生成的音频上找内部的自然停顿点，
直接在该处插入静音把它拉长。这样既保留 a 版的连贯语调，又拿到可控的停顿长度。

用法：
  # 把所有 >=120ms 的内部停顿拉到 400ms（不足的才延长，超过的不动）
  python pause_extend.py --in a.wav --out a2.wav --target 400 --min-gap 120

  # 只延长第 1 个内部停顿到 500ms
  python pause_extend.py --in a.wav --out a2.wav --index 1 --target 500

  # 列出检测到的停顿点（不修改）
  python pause_extend.py --in a.wav --list
"""
import argparse, json, subprocess, sys, pathlib
import numpy as np

SR = 48000


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def encode(samples, path):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1",
                    "-i", "-", "-c:a", "pcm_s16le", str(path)], input=pcm, check=True)


def find_pauses(path, thr_db=-45, min_dur=0.03):
    """返回内部停顿 [(起,止)]，剔除首尾静音"""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path),
                          "-af", f"silencedetect=noise={thr_db}dB:d={min_dur}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    total = len(decode(path)) / SR
    segs, s0 = [], None
    for ln in err.splitlines():
        if "silence_start:" in ln:
            s0 = float(ln.split("silence_start:")[1].strip())
        elif "silence_end:" in ln and s0 is not None:
            e = float(ln.split("silence_end:")[1].split("|")[0].strip())
            segs.append((s0, e)); s0 = None
    if s0 is not None:
        segs.append((s0, total))
    # 去掉贴着头尾的
    return [(s, e) for s, e in segs if s > 0.03 and e < total - 0.03]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst")
    ap.add_argument("--target", type=float, default=400, help="目标停顿毫秒数")
    ap.add_argument("--min-gap", type=float, default=0.0,
                    help="只处理不短于该毫秒数的停顿（默认 0 = 全部内部停顿）")
    ap.add_argument("--index", type=int, help="只处理第 N 个内部停顿（1 起）")
    ap.add_argument("--thr", type=float, default=-45, help="静音判定阈值 dB")
    ap.add_argument("--list", action="store_true", help="只列出现有停顿点")
    args = ap.parse_args()

    pauses = find_pauses(args.src, thr_db=args.thr)
    total = len(decode(args.src)) / SR
    print(f"{pathlib.Path(args.src).name}  时长 {total:.2f}s  检测到内部停顿 {len(pauses)} 个：")
    for i, (s, e) in enumerate(pauses, 1):
        print(f"  #{i}  {s:.3f}s ~ {e:.3f}s  ({(e-s)*1000:.0f}ms)")
    if args.list:
        return
    if not args.dst:
        print("需要 --out", file=sys.stderr); sys.exit(1)

    x = decode(args.src)
    tgt = args.target / 1000.0
    chosen = []
    for i, (s, e) in enumerate(pauses, 1):
        if args.index and i != args.index:
            continue
        if (e - s) * 1000 < args.min_gap:
            continue
        if e - s >= tgt:                     # 已经够长就不动
            continue
        chosen.append((s, e))
    if not chosen:
        print("没有需要延长的停顿点（可能目标值比现有停顿都短）")
        return

    # 从后往前插入，避免位置偏移
    added = 0
    for s, e in reversed(chosen):
        need = int(round((tgt - (e - s)) * SR))
        pos = int(round(((s + e) / 2) * SR))
        x = np.concatenate([x[:pos], np.zeros(need, dtype=np.float32), x[pos:]])
        added += need
    encode(x, args.dst)
    print(f"\n已延长 {len(chosen)} 处停顿到 {args.target:.0f}ms，插入静音 {added/SR:.2f}s")
    print(f"输出：{args.dst}  新时长 {len(x)/SR:.2f}s")


if __name__ == "__main__":
    main()
