#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_book.py — 单进程批量 TTS 生成（直接调用 mlx_audio，绕过会挂死的 TTS-Offline 常驻 worker）。

关键修复（针对 Qwen3-TTS-12Hz 实测踩坑）：
  1. mx.clear_cache() 每次生成前调用 → 避免同一进程第二次 generate 卡死。
  2. 长文本按 ~40 字切片（复刻 TTS-Offline 服务端的 repair 分片策略）→ 避免模型生成长
     文本时不吐 EOS、无限循环（曾出现单段 728s / 182s 卡死）。
  3. 每段生成后做时长校验；若偏长（循环/幻觉续写）则对子句再分片并以更低温度重试。
  4. 0.9x 语速由 ffmpeg atempo 实现（generate_custom_voice 不接受 speed 参数）。

用法：
  python gen_book.py --csv "2026/10/10-31 遥远的救世主/遥远的救世主_十分钟读完一本书.csv"
  python gen_book.py --csv <path> --limit 3          # 调试：只跑前 3 段
  python gen_book.py --csv <path> --merge-only       # 仅重新合并已生成的分段
  python gen_book.py --csv <path> --force            # 强制重跑全部
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

# 离线模式：禁止 HuggingFace 网络请求（模型须已本地缓存）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
SAMPLE_RATE = 24000
VOICE_ALIAS = {"sohee": "sohee", "serena": "serena", "vivian": "vivian",
               "ono_anna": "ono_anna", "ryan": "ryan", "aiden": "aiden",
               "eric": "eric", "dylan": "dylan", "uncle_fu": "uncle_fu"}
DEFAULT_VOICE = "sohee"
CHUNK_MAX_CHARS = 40          # 单块最大字数（复刻服务端 repair 分片上限，避免循环）
CHUNK_GAP_S = 0.08            # 段内分块之间的微小静音间隔，避免爆音


def resolve_voice(name):
    k = (name or "").strip().lower()
    return VOICE_ALIAS.get(k, k if k in VOICE_ALIAS else DEFAULT_VOICE)


def is_chinese(t):
    return any('\u4e00' <= c <= '\u9fff' for c in t)


def expected_duration_s(text):
    """复刻 TTS-Offline 服务端 _expected_duration_s：估算朗读时长（秒）。"""
    import re
    t = str(text or "").strip()
    if not t:
        return 1.0
    zh_ratio = sum(1 for c in t if '\u4e00' <= c <= '\u9fff') / max(len(t), 1)
    if zh_ratio > 0.2:
        return max(1.2, len(t) * 0.40)
    words = re.findall(r"[A-Za-z0-9]+(?:[''][A-Za-z0-9]+)?", t)
    punct = len(re.findall(r"[,.!?;:\u2014-]", t))
    return max(1.2, max(1, len(words)) * 0.50 + punct * 0.12)


def max_tokens_for(text):
    """复刻服务端预算：给 generate_custom_voice 设上限，防止不吐 EOS 时无限循环。
    模型默认上限就是 2048，这里用更贴近真实码率（~12 tok/s）的预算（1.5x 余量），
    既防循环（循环会被更快截断）又不截断正常偏慢的朗读。"""
    return max(128, int(expected_duration_s(text) * 12 * 1.5 + 48))


def split_zh(text, max_chars=CHUNK_MAX_CHARS):
    """把中文文本按标点切成 <= max_chars 的块（尽量在句/逗处断开）。"""
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r'(?<=[。！？!?；;])', text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_chars:
            out.append(p)
            continue
        sub = re.split(r'(?<=[，,、：:—\-])', p)
        buf = ""
        for s in sub:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) <= max_chars:
                buf += s
            else:
                if buf:
                    out.append(buf.strip())
                if len(s) > max_chars:
                    for i in range(0, len(s), max_chars):
                        out.append(s[i:i + max_chars].strip())
                    buf = ""
                else:
                    buf = s
        if buf:
            out.append(buf.strip())
    return [o for o in out if o]


def read_rows(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            text = (row.get("Text") or "").strip()
            if not text:
                continue
            rows.append({"idx": i, "voice": (row.get("Voice") or "").strip(),
                         "emotion": (row.get("Emotion") or "").strip(),
                         "text": text})
    return rows


def merge_segments(seg_paths, out_wav, gap_ms):
    if not seg_paths:
        raise RuntimeError("没有可合并的分段")
    inputs, filters, labels = [], [], []
    for i, p in enumerate(seg_paths):
        inputs += ["-i", str(p)]
        filters.append(f"[{i}:a]aformat=channel_layouts=mono,aresample={SAMPLE_RATE}[a{i}]")
        labels.append(f"[a{i}]")
        if i < len(seg_paths) - 1:
            filters.append(f"[a{i}]apad=pad_dur={gap_ms/1000:.4f}[a{i}p]")
            labels[-1] = f"[a{i}p]"
    # 注意：concat 之后用逗号链式接 loudnorm/alimiter，最终标签 [out] 放到末尾，
    # 不能写成 "concat...[out],loudnorm"（[out] 会切断链路导致 loudnorm 无输入）。
    fc = ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1," \
        f"loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95:level=0[out]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
                    "-map", "[out]", "-c:a", "pcm_s16le", str(out_wav)], check=True)
    mp3 = os.path.splitext(out_wav)[0] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
                    "-c:a", "libmp3lame", "-b:a", "192k", mp3], check=True)
    return out_wav, mp3


def estimate_dur(p):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True)
        return float(out.stdout.strip() or 0)
    except Exception:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--speed", type=float, default=0.9)
    ap.add_argument("--gap-ms", type=int, default=600)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    ap.add_argument("--voice", default=None,
                    help="强制覆盖 CSV 中的音色（如 serena）；不填则沿用 CSV 的 Voice 列")
    ap.add_argument("--tag", default=None,
                    help="输出文件名追加的标签（如 sohee/serena），用于区分不同音色产物，避免互相覆盖")
    args = ap.parse_args()

    csv_path = os.path.abspath(args.csv)
    out_dir = os.path.dirname(csv_path)
    rows = read_rows(csv_path)
    voice_label = (args.voice or "CSV默认").upper()
    speed_label = "1.0x（原速，不做 ffmpeg 处理）" if abs(args.speed - 1.0) < 1e-6 \
        else f"{args.speed}x（ffmpeg atempo）"
    tag_suffix = f"_{args.tag}" if args.tag else ""
    print(f"读取 CSV：{csv_path}\n  共 {len(rows)} 段，输出目录：{out_dir}"
          f"\n  音色={voice_label}  语速={speed_label}  标签={args.tag or '无'}  段间={args.gap_ms}ms"
          f"  分块≤{CHUNK_MAX_CHARS}字", flush=True)

    def seg_path(idx):
        return os.path.join(out_dir, f"tts_seg{tag_suffix}_{idx:03d}.wav")

    if args.merge_only:
        segs = sorted([seg_path(r["idx"]) for r in rows if os.path.exists(seg_path(r["idx"]))],
                      key=lambda p: int(os.path.basename(p).split("_")[-1].split(".")[0]))
        if not segs:
            print("没有可合并的 tts_seg_*.wav")
            return
        full = os.path.join(out_dir, os.path.splitext(os.path.basename(csv_path))[0] + f"{tag_suffix}_full")
        w, m = merge_segments(segs, full + ".wav", args.gap_ms)
        print(f"合并完成：{w}\n          + {m}\n共 {len(segs)} 段，时长约 "
              f"{sum(estimate_dur(p) for p in segs):.0f}s")
        return

    # ── 加载模型（仅一次）──
    t0 = time.time()
    from mlx_audio.tts.utils import load_model
    import mlx.core as mx
    from mlx_audio.audio_io import write as audio_write
    model = load_model(REPO)
    sr = getattr(model, "sample_rate", SAMPLE_RATE)
    print(f"[model] loaded in {time.time()-t0:.1f}s sr={sr}", flush=True)

    def synth_chunk(text, voice, lang, instruct, sampling, temperature=None, max_tokens=None):
        """生成单个分块，返回 mx 音频数组；空则返 None。"""
        params = dict(sampling)
        if temperature is not None:
            params["temperature"] = temperature
        mt = max_tokens or max_tokens_for(text)
        mx.clear_cache()  # 关键：避免同一进程第二次 generate 卡死
        results = list(model.generate_custom_voice(
            text=text, speaker=voice, language=lang,
            instruct=instruct, max_tokens=mt, **params))
        segs = []
        for res in results:
            a = res.audio if hasattr(res, "audio") else res
            if hasattr(a, "flatten"):
                a = a.flatten()
            segs.append(a)
        if not segs:
            return None
        return mx.concatenate(segs, axis=0)

    def gen_with_retry(text, voice, lang, instruct, sampling, temperature=None, depth=0):
        """生成一段文本；若时长异常（循环/幻觉续写）则二次分片 + 降温度 + 收紧 token 预算重试。
        复刻 TTS-Offline 服务端 _safer_retry_advanced 的抗循环策略。"""
        a = synth_chunk(text, voice, lang, instruct, sampling, temperature=temperature)
        if a is None:
            return None
        dur = float(a.shape[0]) / sr
        exp = expected_duration_s(text)
        # 精确判循环：若分段几乎用满 token 预算（≈未正常吐 EOS 而跑到上限），才算循环；
        # 这样不会误伤“偏慢但正常结束”的朗读。
        cap_dur = max_tokens_for(text) / 12.0  # 预算换算成秒（~12 tok/s）
        if dur > cap_dur * 0.9 and depth < 4:
            new_temp = (max(0.06, 0.14 - 0.015 * (depth + 1)) if temperature is None
                        else max(0.05, temperature - 0.1))
            safe_tokens = max(80, min(320, len(text) * 4 + 64))
            print(f"          ↳ 分块疑似循环({dur:.0f}s≈预算{cap_dur:.0f}s)，"
                  f"二次分片重试(t={new_temp:.2f},max_tok={safe_tokens})", flush=True)
            parts = split_zh(text, max_chars=max(12, CHUNK_MAX_CHARS // 2))
            sub = [gen_with_retry(p, voice, lang, instruct, sampling,
                                  temperature=new_temp, depth=depth + 1) for p in parts]
            sub = [s for s in sub if s is not None]
            if sub:
                out = []
                for s in sub:
                    out.append(s)
                    out.append(mx.zeros((int(sr * CHUNK_GAP_S),), dtype=s.dtype))
                return mx.concatenate(out[:-1], axis=0)
            # 分片仍不可用 → 退回：同文本、更低温度、更紧预算再试一次
            a2 = synth_chunk(text, voice, lang, instruct, sampling,
                             temperature=new_temp, max_tokens=safe_tokens)
            if a2 is not None:
                return a2
        return a

    def synthesize_segment(r, sp):
        voice = resolve_voice(args.voice) if args.voice else resolve_voice(r["voice"])
        lang = "Chinese" if is_chinese(r["text"]) else "English"
        sampling = ({"temperature": 0.2, "top_p": 0.85, "top_k": 20} if is_chinese(r["text"])
                    else {"temperature": 0.18, "top_p": 0.78, "top_k": 12})
        instruct = r["emotion"] or "平静自然地朗读输入文本；严格只朗读 text 原文，不添加任何额外内容。"
        chunks = split_zh(r["text"])
        print(f"[生成] 第{r['idx']:>2}段（{len(r['text'])}字 → {len(chunks)}块）"
              f"音色={voice} 风格={r['emotion'][:16]}…", flush=True)
        tg = time.time()
        arrs = []
        for ci, ch in enumerate(chunks, 1):
            a = gen_with_retry(ch, voice, lang, instruct, sampling)
            if a is not None:
                arrs.append(a)
                arrs.append(mx.zeros((int(sr * CHUNK_GAP_S),), dtype=a.dtype))
        if not arrs:
            print(f"        ✗ 第{r['idx']}段无音频，跳过", flush=True)
            return None
        audio = mx.concatenate(arrs[:-1], axis=0)
        raw = sp + ".raw.wav"
        audio_write(raw, audio, sr)
        if abs(args.speed - 1.0) < 1e-6:
            # 原速：不做语速处理，直接转封装为最终 wav（避免 atempo 重编码）
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw,
                            "-c:a", "pcm_s16le", sp], check=True)
        else:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw,
                            "-af", f"atempo={args.speed}", "-c:a", "pcm_s16le", sp], check=True)
        os.remove(raw)
        dur = estimate_dur(sp)
        exp = expected_duration_s(r["text"])
        flag = ""
        if dur > exp * 1.8:
            flag = " ⚠️偏长(可能循环/未正常结束)"
        elif dur < exp * 0.4:
            flag = " ⚠️偏短(可能截断)"
        print(f"        ✓ 第{r['idx']}段 用时 {time.time()-tg:.1f}s "
              f"{dur:.1f}s(期望~{exp:.0f}s){flag} {os.path.getsize(sp)/1024:.0f}KB", flush=True)
        return sp

    todo = [r for r in rows if r["idx"] > args.skip]
    if args.limit:
        todo = todo[:args.limit]

    for r in todo:
        sp = seg_path(r["idx"])
        if os.path.exists(sp) and not args.force:
            print(f"[跳过] 第{r['idx']:>2}段（已存在）", flush=True)
            continue
        try:
            synthesize_segment(r, sp)
        except Exception as e:
            print(f"        ✗ 第{r['idx']}段失败：{e}", flush=True)

    # ── 合并 ──
    segs = sorted([seg_path(r["idx"]) for r in rows if os.path.exists(seg_path(r["idx"]))],
                  key=lambda p: int(os.path.basename(p).split("_")[-1].split(".")[0]))
    if not segs:
        print("没有可用的分段，跳过合并")
        return
    full = os.path.join(out_dir, os.path.splitext(os.path.basename(csv_path))[0] + f"{tag_suffix}_full")
    w, m = merge_segments(segs, full + ".wav", args.gap_ms)
    print(f"\n合并完成：{w}\n          + {m}\n共 {len(segs)} 段，时长约 "
          f"{sum(estimate_dur(p) for p in segs):.0f}s")


if __name__ == "__main__":
    main()
