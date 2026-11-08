#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
csv_tts.py — 读取「十分钟读完一本书」类 CSV，逐段调用本地 TTS-Offline 服务生成语音，再合并成一条完整音频。

适用服务端：TTS-Offline（基于 MLX Qwen3-TTS，本机已运行在 http://127.0.0.1:17435）
接口：POST /api/synthesize → 轮询 /api/status 到 done → GET /api/download?path= 取回音频

CSV 列约定：Voice, Emotion, Text
  - Voice  : 音色名（如 Sohee）→ 映射到服务端 voice_id（大小写不敏感）
  - Emotion: 风格指令（style_instruct），直接作为 Qwen3-TTS 的 instruct 风格提示
  - Text   : 本段正文

速度与超时（按需求）：
  - 语速 = --speed（默认 0.9），由 TTS 模型原生支持（无需 ffmpeg 变速，不降调）。
  - 单段生成的「耐心」预算 = --timeout（默认 90s = 1.5 分钟）。
    若 1.5 分钟内仍未取到音频，判定超时：先 POST /api/stop 中止可能卡死的 worker，
    等模型重新就绪后，重新发起一次全新的合成请求（新 output_path），最多重试 --max-retries 次。

产物（保存在 CSV 同名目录下）：
  tts_seg_001.wav, tts_seg_002.wav, ...   （单段，已含 0.9x 原生变速 + Emotion 风格）
  <csv主名>_full.wav  +  .mp3               （合并成品，段间插入静音、响度归一）

用法：
  # 默认：处理 csv，速度 0.9、超时 90s、重试 5
  .venv/bin/python csv_tts.py --csv "2026/10/10-31 遥远的救世主/遥远的救世主_十分钟读完一本书.csv"

  # 调试：只跑前 3 段
  .venv/bin/python csv_tts.py --csv <path> --limit 3

  # 仅重新合并已生成的段落（不调用 TTS）
  .venv/bin/python csv_tts.py --csv <path> --merge-only

  # 强行重跑全部（覆盖已有段）
  .venv/bin/python csv_tts.py --csv <path> --force
"""

import argparse
import csv
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ── 配置 ──────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:17435"   # TTS-Offline 服务
VOICE_ALIAS = {                        # CSV 里的 Voice 名 → 服务端 voice_id
    "sohee": "sohee", "serena": "serena", "vivian": "vivian",
    "ono_anna": "ono_anna", "ryan": "ryan", "aiden": "aiden",
    "eric": "eric", "dylan": "dylan", "uncle_fu": "uncle_fu",
}
DEFAULT_VOICE = "sohee"
SAMPLE_RATE = 24000                   # Qwen3-TTS 输出采样率
SOCKET_TIMEOUT = 60                    # 单次 HTTP 请求 socket 超时（秒）


# ── HTTP 封装 ─────────────────────────────────────────
def api_post(path, body, timeout=SOCKET_TIMEOUT):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api_get(path, timeout=SOCKET_TIMEOUT):
    with urllib.request.urlopen(BASE_URL + path, timeout=timeout) as r:
        return json.loads(r.read())


def api_get_bytes(path, timeout=SOCKET_TIMEOUT):
    with urllib.request.urlopen(BASE_URL + path, timeout=timeout) as r:
        return r.read()


# ── 服务端状态 ───────────────────────────────────────
def get_status():
    return api_get("/api/status", timeout=15)


def wait_worker_ready(timeout=300):
    """等待模型 worker 就绪（首次加载或 /api/stop 之后）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st = get_status()
            if st.get("worker_ready"):
                return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


# ── 单段合成（含超时重发）─────────────────────────────
def synthesize_segment(text, voice_id, style, speed, timeout, max_retries):
    """合成单段语音并返回音频字节。

    流程：POST /api/synthesize → 轮询 /api/status 到 done → /api/download 取回。
    若 1.5 分钟（timeout）内未取到音频，则中止 worker 并重新发起请求，最多 max_retries 次。
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        deadline = t0 + timeout
        try:
            # 1) 发起合成（模型未就绪会返回 503，等待后重试）
            try:
                r = api_post("/api/synthesize", {
                    "voice_id": voice_id,
                    "speed": speed,
                    "text": text,
                    "advanced": {"style_instruct": style} if style else {},
                }, timeout=30)
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    print(f"        · 模型加载中(503)，等待就绪后重试…", flush=True)
                    if not wait_worker_ready():
                        raise RuntimeError("等待模型就绪超时")
                    continue
                raise

            op = r.get("output_path")
            if not op:
                if not wait_worker_ready():
                    raise RuntimeError("未返回 output_path 且模型未就绪")
                continue

            # 2) 轮询状态直到 done
            while True:
                if time.time() > deadline:
                    raise TimeoutError(f"轮询超时（{timeout:.0f}s 未出声），准备重发")
                try:
                    st = get_status()
                except Exception:
                    if time.time() > deadline:
                        raise TimeoutError("轮询连接中断且超时")
                    time.sleep(2.0)
                    continue
                if st.get("status") == "done" and st.get("output_path"):
                    op = st["output_path"]
                    break
                if st.get("status") == "error":
                    raise RuntimeError(f"合成失败：{st}")
                time.sleep(1.0)

            # 3) 下载音频
            data = api_get_bytes(
                "/api/download?path=" + urllib.parse.quote(op, safe=""),
                timeout=max(30, int(deadline - time.time())))
            if len(data) < 44:
                raise RuntimeError("下载音频过小，疑似空文件")
            print(f"        ✓ 完成（本次尝试 {time.time()-t0:.1f}s，第{attempt}次）"
                  f" {len(data)/1024:.0f}KB", flush=True)
            return data

        except Exception as e:
            last_err = e
            print(f"        ✗ 第{attempt}次失败：{e}"
                  + ("（已达最大重试）" if attempt == max_retries else "，中止 worker 并重发…"),
                  flush=True)
            if attempt < max_retries:
                try:
                    api_post("/api/stop", {}, timeout=15)
                except Exception:
                    pass
                if not wait_worker_ready():
                    print("        ⚠ 模型未能重新就绪，继续尝试…", flush=True)
                time.sleep(2.0)
    raise RuntimeError(f"单段合成在 {max_retries} 次重试后仍失败：{last_err}")


# ── 合并（ffmpeg）────────────────────────────────────
def merge_segments(seg_paths, out_wav, gap_ms):
    """多段 wav 顺序拼接，段间插入 gap_ms 静音，响度归一后导出 wav + mp3。"""
    if not seg_paths:
        raise RuntimeError("没有任何分段可合并")
    inputs, filters, labels = [], [], []
    for i, p in enumerate(seg_paths):
        inputs += ["-i", str(p)]
        filters.append(f"[{i}:a]aformat=channel_layouts=mono,aresample={SAMPLE_RATE}[a{i}]")
        labels.append(f"[a{i}]")
        if i < len(seg_paths) - 1:
            filters.append(f"[a{i}]apad=pad_dur={gap_ms/1000:.4f}[a{i}p]")
            labels[-1] = f"[a{i}p]"
    fc = ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"
    fc += ",loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95:level=0"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
         "-map", "[out]", "-c:a", "pcm_s16le", str(out_wav)],
        check=True)
    mp3 = out_wav.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
         "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)],
        check=True)
    return out_wav, mp3


# ── 读取 CSV ─────────────────────────────────────────
def read_rows(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            text = (row.get("Text") or "").strip()
            if not text:
                continue
            rows.append({
                "idx": i,
                "voice": (row.get("Voice") or "").strip(),
                "emotion": (row.get("Emotion") or "").strip(),
                "text": text,
            })
    return rows


def resolve_voice(name):
    key = (name or "").strip().lower()
    return VOICE_ALIAS.get(key, key if key in VOICE_ALIAS else DEFAULT_VOICE)


def estimate_dur(p):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)], capture_output=True, text=True)
        return float(out.stdout.strip() or 0)
    except Exception:
        return 0.0


# ── 主流程 ───────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="CSV → TTS-Offline → 合并音频")
    ap.add_argument("--csv", required=True, help="CSV 文件路径")
    ap.add_argument("--speed", type=float, default=0.9, help="语速倍率（TTS 原生支持，<1 变慢）")
    ap.add_argument("--timeout", type=float, default=90,
                    help="单段生成耐心预算（秒），默认 90=1.5 分钟；超时则重发")
    ap.add_argument("--max-retries", type=int, default=5, help="单段超时/失败后重发次数")
    ap.add_argument("--gap-ms", type=int, default=600, help="段间静音毫秒")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 段（调试）")
    ap.add_argument("--skip", type=int, default=0, help="跳过前 N 段（调试）")
    ap.add_argument("--force", action="store_true", help="覆盖已生成的段，全部重跑")
    ap.add_argument("--merge-only", action="store_true", help="仅重新合并已生成的段")
    args = ap.parse_args()

    csv_path = pathlib.Path(args.csv)
    out_dir = csv_path.parent
    rows = read_rows(csv_path)
    print(f"读取 CSV：{csv_path}")
    print(f"  共 {len(rows)} 段正文，输出目录：{out_dir}")
    print(f"  音色=Sohee  速度={args.speed}x（TTS 原生）  超时={args.timeout:.0f}s  重试={args.max_retries}")

    def seg_path(idx):
        return out_dir / f"tts_seg_{idx:03d}.wav"

    # ── 仅合并 ──
    if args.merge_only:
        segs = sorted([seg_path(r["idx"]) for r in rows if seg_path(r["idx"]).exists()],
                      key=lambda p: int(p.stem.split("_")[-1]))
        if not segs:
            print("没有可合并的 tts_seg_*.wav")
            return
        full = out_dir / (csv_path.stem + "_full")
        w, m = merge_segments(segs, full.with_suffix(".wav"), args.gap_ms)
        total = sum(estimate_dur(p) for p in segs)
        print(f"合并完成：{w}\n          + {m}\n共 {len(segs)} 段，时长约 {total:.0f}s")
        return

    # ── 逐段合成 ──
    todo = [r for r in rows if r["idx"] > args.skip]
    if args.limit:
        todo = todo[:args.limit]

    if not wait_worker_ready():
        print("⚠ 服务端模型未就绪，请确认 TTS-Offline 已启动（http://127.0.0.1:17435）",
              file=sys.stderr)
        sys.exit(1)

    for r in todo:
        sp = seg_path(r["idx"])
        if sp.exists() and not args.force:
            print(f"[跳过] 第{r['idx']:>2}段（已存在 {sp.name}）", flush=True)
            continue
        voice_id = resolve_voice(r["voice"])
        print(f"[生成] 第{r['idx']:>2}段（{len(r['text'])}字）"
              f" 音色={voice_id} 风格={r['emotion'][:24]}…", flush=True)
        audio = synthesize_segment(
            r["text"], voice_id, r["emotion"], args.speed,
            args.timeout, args.max_retries)
        sp.write_bytes(audio)
        print(f"        已存 {sp}", flush=True)
        # 该服务端 worker 在连续第二次推理时会挂死（MLX 二次调用死锁），
        # 因此每段生成后主动重启 worker，让下一段跑在全新进程上，避免卡死。
        try:
            api_post("/api/stop", {}, timeout=15)
        except Exception:
            pass

    # ── 合并 ──
    segs = sorted([seg_path(r["idx"]) for r in rows if seg_path(r["idx"]).exists()],
                  key=lambda p: int(p.stem.split("_")[-1]))
    if not segs:
        print("没有可用的分段，跳过合并")
        return
    full = out_dir / (csv_path.stem + "_full")
    w, m = merge_segments(segs, full.with_suffix(".wav"), args.gap_ms)
    total = sum(estimate_dur(p) for p in segs)
    print(f"\n合并完成：{w}\n          + {m}\n共 {len(segs)} 段，时长约 {total:.0f}s")


if __name__ == "__main__":
    main()
