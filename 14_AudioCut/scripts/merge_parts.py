#!/usr/bin/env python3
"""
把分段音频合并成一条完整音频（段间插入指定静音）

用法：
  python merge_parts.py --dir <项目目录> --parts 7 --gap-ms 600 --name full

输入：<项目目录>/out/part_01.wav ... part_0N.wav
输出：<项目目录>/out/<name>.wav 与 <name>.mp3
"""
import argparse, pathlib, subprocess, sys
import numpy as np

SR = 48000


def decode(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--parts", type=int, required=True)
    ap.add_argument("--gap-ms", type=float, default=600)
    ap.add_argument("--name", default="full")
    ap.add_argument("--suffix", default="", help="分段文件名后缀，如 _C仅明显")
    ap.add_argument("--from", dest="start", type=int, default=1, help="起始段号")
    args = ap.parse_args()

    od = pathlib.Path(args.dir) / "out"
    files = []
    for i in range(args.start, args.parts + 1):
        p = od / f"part_{i:02d}{args.suffix}.wav"
        if not p.exists():
            print(f"缺少 {p}，先跑完所有段落再合并", file=sys.stderr); sys.exit(1)
        files.append(p)

    gap = np.zeros(int(args.gap_ms / 1000 * SR), dtype=np.float32)
    chunks = []
    for i, p in enumerate(files):
        x = decode(p)
        if i:
            chunks.append(gap)
        chunks.append(x)
        print(f"  + {p.name}  {len(x)/SR:.2f}s")
    y = np.concatenate(chunks)

    tmp = od / f".{args.name}_raw.wav"
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1",
                    "-i", "-", "-c:a", "pcm_s16le", str(tmp)], input=pcm, check=True)

    out = od / f"{args.name}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                           "aformat=channel_layouts=mono,alimiter=limit=0.95:level=0",
                    "-c:a", "pcm_s16le", str(out)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out),
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    str(out.with_suffix(".mp3"))], check=True)
    tmp.unlink(missing_ok=True)

    total = len(decode(out)) / SR
    print(f"\n合并完成：{out}（{total/60:.2f} 分钟）+ {out.with_suffix('.mp3').name}")
    print(f"段数 {len(files)}，段间静音 {args.gap_ms:.0f}ms")


if __name__ == "__main__":
    main()
