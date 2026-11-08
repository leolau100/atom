#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_one.py — 单段 TTS 生成（独立子进程，规避 TTS-Offline worker 的 MLX 二次推理死锁）。

每段都起一个全新 python 进程：load_model → generate_custom_voice → 存 wav。
进程退出即释放显存/模型，绝不会踩「同一进程第二次 generate 卡死」的坑。

用法：
  python gen_one.py --text "..." --out seg.wav --voice sohee --speed 0.9 \
        --instruct "温和、沉稳、自然的有声书旁白；语速适中，吐字清晰。"

依赖：TTS-Offline 的 .venv（含 mlx_audio）；模型需已缓存到本地 HF 目录。
"""
import argparse
import os
import sys
import time

# 离线模式：禁止任何 HuggingFace 网络请求（模型须已本地缓存）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="sohee")
    ap.add_argument("--speed", type=float, default=0.9)
    ap.add_argument("--instruct", default="平静自然地朗读输入文本；严格只朗读 text 原文，不添加任何额外内容。")
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()

    t0 = time.time()
    from mlx_audio.tts.utils import load_model
    import mlx.core as mx
    from mlx_audio.audio_io import write as audio_write

    model = load_model(args.repo)
    sr = getattr(model, "sample_rate", 24000)
    print(f"[gen_one] model loaded in {time.time()-t0:.1f}s sr={sr}", flush=True)

    def is_chinese(t):
        return any('\u4e00' <= c <= '\u9fff' for c in t)

    lang = "Chinese" if is_chinese(args.text) else "English"
    sampling = {"temperature": 0.2, "top_p": 0.85, "top_k": 20} if is_chinese(args.text) \
        else {"temperature": 0.18, "top_p": 0.78, "top_k": 12}

    t1 = time.time()
    # 注意：本版本 mlx_audio 的 generate_custom_voice 不接受 speed 参数，
    # 0.9x 语速由 ffmpeg atempo 在生成后实现（见下方）。
    results = list(model.generate_custom_voice(
        text=args.text, speaker=args.voice, language=lang,
        instruct=args.instruct, **sampling))
    print(f"[gen_one] generate done in {time.time()-t1:.1f}s results={len(results)}",
          flush=True)

    segs = []
    for r in results:
        a = r.audio if hasattr(r, "audio") else r
        if hasattr(a, "flatten"):
            a = a.flatten()
        segs.append(a)
    if not segs:
        print("[gen_one] ERROR: no audio produced", flush=True)
        sys.exit(2)
    audio = mx.concatenate(segs, axis=0)

    import tempfile, subprocess
    raw = args.out + ".raw.wav"
    audio_write(raw, audio, sr)
    # 0.9x 语速：ffmpeg atempo（pitch 不变）。生成速度=1.0，变速在生成后做。
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", raw,
         "-af", f"atempo={args.speed}", "-c:a", "pcm_s16le", args.out],
        check=True)
    os.remove(raw)
    dur = audio.shape[0] / sr / max(args.speed, 1e-3)
    print(f"[gen_one] saved {args.out} dur~{dur:.2f}s total={time.time()-t0:.1f}s",
          flush=True)


if __name__ == "__main__":
    main()
