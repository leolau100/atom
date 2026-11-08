#!/usr/bin/env python3
"""
Voicebox 文本转语音（支持用 [[p=毫秒]] 标记插入精确停顿）

用法：
  python voicebox_gen.py --text "他等了五十一年九月零四天。" --out a.wav
  python voicebox_gen.py --text "他等了五十一年[[p=400]]九月零四天。" --out c.wav --mp3

说明：
  - 文本里的 [[p=400]] 不会送进 TTS，而是把文本切成多段分别生成，
    再在拼接时插入精确的 400ms 静音（停顿长度完全可控）。
  - 逐段串行生成（避免多个任务抢 CPU），每段带进度与超时。
  - 默认 profile 为「电台情感故事犀利01-03」。
"""
import argparse, json, subprocess, sys, time, urllib.request, urllib.error, pathlib

BASE = "http://127.0.0.1:17493"
DEFAULT_PROFILE = "316c2df3-04c7-4a53-89a2-0230f5a11f7c"   # 电台情感故事犀利01-03
JOB_TIMEOUT = 420          # 单段生成超时（秒）
POLL_INTERVAL = 2.0


def api_json(path, payload=None, method=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def api_bytes(path, timeout=120):
    return urllib.request.urlopen(BASE + path, timeout=timeout).read()


def split_by_pause(text):
    """把文本按 [[p=ms]] 切成 [(片段, 片段后停顿秒数)]"""
    import re
    parts, pos = [], 0
    for m in re.finditer(r'\[\[\s*p\s*=\s*(\d+)\s*\]\]', text):
        seg = text[pos:m.start()].strip()
        if seg:
            parts.append([seg, int(m.group(1)) / 1000.0])
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        parts.append([tail, 0.0])
    return parts or [[text.strip(), 0.0]]


def generate(text, profile, language):
    r = api_json("/speak", {"text": text, "profile": profile, "language": language})
    gid = r["id"]
    t0 = time.time()
    while time.time() - t0 < JOB_TIMEOUT:
        try:
            h = api_json(f"/history/{gid}", timeout=15)
        except Exception:
            time.sleep(POLL_INTERVAL); continue
        st = (h.get("status") or "").lower()
        if st == "completed":
            return gid, h
        if st in ("failed", "cancelled", "error"):
            raise RuntimeError(f"生成失败 status={st} error={h.get('error')}")
        el = time.time() - t0
        print(f"      …{st or 'running'} {el:5.1f}s", flush=True)
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"生成超时（{JOB_TIMEOUT}s）id={gid}")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def speech_bounds(path, thr_db=-45):
    """返回 (首个非静音时刻, 最后一个非静音时刻)，用于裁掉段首/段尾自带静音"""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path),
                          "-af", f"silencedetect=noise={thr_db}dB:d=0.04",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    dur = probe(str(path))
    sil = []
    s0 = None
    for ln in err.splitlines():
        if "silence_start:" in ln:
            s0 = float(ln.split("silence_start:")[1].strip())
        elif "silence_end:" in ln and s0 is not None:
            e = float(ln.split("silence_end:")[1].split("|")[0].strip())
            sil.append((s0, e)); s0 = None
    start = 0.0
    if sil and sil[0][0] <= 0.02:          # 开头就是静音
        start = sil[0][1]
    end = dur
    if s0 is not None and dur - s0 < 0.5:  # 结尾是静音（未闭合）
        end = s0
    elif sil and sil[-1][1] >= dur - 0.02:
        end = sil[-1][0]
    return start, end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="文本，可含 [[p=毫秒]] 标记")
    ap.add_argument("--out", required=True, help="输出 wav 路径")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--language", default="zh")
    ap.add_argument("--mp3", action="store_true", help="同时导出 mp3")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--keep-ms", type=float, default=30,
                    help="裁剪段首/段尾静音时保留的余量毫秒数（默认 30）")
    ap.add_argument("--no-trim", dest="trim", action="store_false",
                    help="不裁剪每段自带的段首/段尾静音（默认裁剪，否则停顿会叠加变长）")
    ap.set_defaults(trim=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "_tmp"; tmp.mkdir(exist_ok=True)

    parts = split_by_pause(args.text)
    print(f"分成 {len(parts)} 段：")
    for i, (seg, gap) in enumerate(parts, 1):
        print(f"  [{i}] {len(seg)} 字 | 段后停顿 {gap*1000:.0f}ms | {seg[:26]}…")

    wavs = []
    t_all = time.time()
    for i, (seg, gap) in enumerate(parts, 1):
        print(f"  → 生成第 {i}/{len(parts)} 段：", flush=True)
        t0 = time.time()
        gid, h = generate(seg, args.profile, args.language)
        p = tmp / f"part_{i:02d}.wav"
        p.write_bytes(api_bytes(f"/audio/{gid}"))
        dur = probe(str(p))
        print(f"      完成 id={gid[:8]} 音频 {dur:.2f}s（用时 {time.time()-t0:.1f}s）", flush=True)
        wavs.append((p, gap))

    # 拼接（段间插入精确静音）
    if len(wavs) == 1:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wavs[0][0]),
                        "-ar", "48000", "-ac", "1", str(out)], check=True)
    else:
        inputs, filters, labels = [], [], []
        for i, (p, gap) in enumerate(wavs):
            # 先裁掉模型每段自带的段首/段尾静音，否则会和插入的静音叠加
            a, b = speech_bounds(p)
            pad = args.keep_ms / 1000.0
            a = max(0.0, a - pad)
            b = min(probe(str(p)), b + pad)
            if args.trim:
                print(f"      第{i+1}段裁静音: {a:.2f}s ~ {b:.2f}s（原长 {probe(str(p)):.2f}s）")
            else:
                a, b = 0.0, probe(str(p))
            inputs += ["-i", str(p)]
            filters.append(f"[{i}:a]atrim=start={a:.4f}:end={b:.4f},"
                           f"asetpts=PTS-STARTPTS,aresample=48000,"
                           f"aformat=channel_layouts=mono[a{i}]")
            labels.append(f"[a{i}]")
            if gap > 0:
                filters.append(f"[a{i}]apad=pad_dur={gap}[a{i}p]")
                labels[-1] = f"[a{i}p]"
        filter_complex = ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs,
                        "-filter_complex", filter_complex, "-map", "[out]", str(out)], check=True)

    total = probe(str(out))
    print(f"\n输出：{out}  时长 {total:.2f}s  总用时 {time.time()-t_all:.1f}s")
    if args.mp3:
        mp3 = out.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out),
                        "-c:a", "libmp3lame", "-b:a", args.bitrate, str(mp3)], check=True)
        print(f"输出：{mp3}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
