#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把外部「整段旁白 wav + 对齐 SRT」注入到加密剪映草稿。

用途（2026-11-14）：用户让 agent 批量生成语音和草稿时，
`make_jy_draft.py` 产出的中间草稿是明文 draft_content.json，新版剪映打不开。
本脚本以《住小房子的女人》这类「导入型字幕 + 单段旁白 wav」的加密草稿为模板，
把 SRT 的每条字幕和新的 wav 直接写进两份加密 draft_info.json，
得到当前剪映能打开的成品草稿。

只改：字幕轨片段与素材、旁白轨素材路径与时长、顶层 duration。
不改：标题轨、配图/贴纸轨、BGM 轨、封面工程、任何配音业务关联字段。
后续仍需跑 fit-duration / fix-subtitles / set-bg / fix-cover 完成收尾。

用法:
  python3 inject_srt.py -s "三体" --srt <字幕.srt> --wav <旁白.wav> [--dry-run]
"""
import argparse
import copy
import json
import os
import re
import sys
import uuid
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jy_draft as J


def upper_uuid():
    return str(uuid.uuid4()).upper()


def parse_srt(path):
    """返回 [(start_us, end_us, text), ...]；多行字幕合并为一行。"""
    raw = open(path, encoding="utf-8").read()
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues = []
    pat = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
                     r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
    for b in blocks:
        lines = [x for x in b.splitlines() if x.strip()]
        m = None
        idx = 0
        for i, line in enumerate(lines):
            m = pat.search(line)
            if m:
                idx = i + 1
                break
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = ((g[0] * 3600 + g[1] * 60 + g[2]) * 1000 + g[3]) * 1000
        e = ((g[4] * 3600 + g[5] * 60 + g[6]) * 1000 + g[7]) * 1000
        text = " ".join(x.strip() for x in lines[idx:]).strip()
        if text and e > a:
            cues.append((a, e, text))
    if not cues:
        raise RuntimeError("SRT 没解析出任何字幕: " + path)
    return cues


def wav_duration_us(path):
    with wave.open(path, "rb") as w:
        return int(round(w.getnframes() / w.getframerate() * 1_000_000))


def find_voice_track(d):
    """定位单段旁白 wav 轨（按 .wav 排除 8 段 BGM 轨）。"""
    audios = {m["id"]: m for m in d["materials"].get("audios", [])}
    for i, t in enumerate(d.get("tracks", [])):
        if t.get("type") != "audio":
            continue
        for s in t.get("segments", []):
            m = audios.get(s.get("material_id"), {})
            if str(m.get("path", "")).lower().endswith(".wav"):
                return i
    raise RuntimeError("找不到旁白 wav 轨")


def inject_one(d, cues, wav_path, total_us):
    tracks = d["tracks"]
    sub = J.subtitle_track(d)
    if sub is None:
        raise RuntimeError("找不到字幕轨")
    sub_i = next(i for i, t in enumerate(tracks) if t is sub)
    tpl_seg = copy.deepcopy(sub["segments"][0])

    texts = {m["id"]: m for m in d["materials"]["texts"]}
    tpl_mat = copy.deepcopy(texts[tpl_seg["material_id"]])
    old_text_ids = {s["material_id"] for s in sub["segments"]}
    old_anim_ids = {r for s in sub["segments"]
                    for r in (s.get("extra_material_refs") or [])}
    anims = d["materials"].get("material_animations", [])
    tpl_anim = copy.deepcopy(next((m for m in anims if m.get("id") in old_anim_ids),
                                  {"id": upper_uuid(), "type": "sticker_animation"}))

    keep_texts = [m for m in d["materials"]["texts"] if m["id"] not in old_text_ids]
    keep_anims = [m for m in anims if m["id"] not in old_anim_ids]
    base_render = int(tpl_seg.get("render_index") or 14000)

    new_segs = []
    for i, (a, e, text) in enumerate(cues):
        mid, sid, aid = upper_uuid(), upper_uuid(), upper_uuid()

        mat = copy.deepcopy(tpl_mat)
        mat["id"] = mid
        cj = json.loads(mat.get("content", "{}"))
        cj["text"] = text
        styles = cj.get("styles") or []
        if styles:
            st0 = copy.deepcopy(styles[0])
            st0["range"] = [0, len(text)]
            cj["styles"] = [st0]
        mat["content"] = json.dumps(cj, ensure_ascii=False)
        # 导入型字幕不应带任何逐字/配音关联（也让 fix-subtitles 走安全折行模式）
        mat["words"] = {}
        mat["current_words"] = {}
        mat.pop("text_to_audio_ids", None)
        keep_texts.append(mat)

        seg = copy.deepcopy(tpl_seg)
        seg["id"] = sid
        seg["material_id"] = mid
        seg["extra_material_refs"] = [aid]
        seg["target_timerange"] = {"duration": e - a}
        if a:
            seg["target_timerange"]["start"] = a
        seg["render_index"] = base_render + i
        new_segs.append(seg)

        an = copy.deepcopy(tpl_anim)
        an["id"] = aid
        keep_anims.append(an)

    sub["segments"] = new_segs
    d["materials"]["texts"] = keep_texts
    d["materials"]["material_animations"] = keep_anims

    # 旁白轨：整段 wav，路径指向文章目录里的实际文件
    vi = find_voice_track(d)
    vt = tracks[vi]
    if len(vt["segments"]) != 1:
        raise RuntimeError(f"旁白轨应有 1 段，实际 {len(vt['segments'])}")
    aseg = vt["segments"][0]
    am = next(m for m in d["materials"]["audios"]
              if m["id"] == aseg["material_id"])
    am["path"] = wav_path
    am["name"] = os.path.basename(wav_path)
    am["duration"] = str(total_us) if isinstance(am.get("duration"), str) else total_us
    if isinstance(aseg.get("source_timerange"), dict):
        aseg["source_timerange"]["duration"] = total_us
    aseg["target_timerange"] = {"duration": total_us}

    d["duration"] = total_us
    return len(cues), vi, sub_i, total_us


def main():
    ap = argparse.ArgumentParser(description="把 SRT + 旁白 wav 注入加密剪映草稿")
    ap.add_argument("-s", "--source", required=True, help="目标草稿名（已 copy 出的副本）")
    ap.add_argument("--srt", required=True, help="字幕 SRT 路径")
    ap.add_argument("--wav", required=True, help="整段旁白 wav 路径")
    ap.add_argument("--root", help="草稿根目录")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写盘")
    a = ap.parse_args()

    root = a.root or J.DEFAULT_ROOT
    fold = os.path.join(root, a.source)
    if not os.path.isdir(fold):
        raise SystemExit("草稿目录不存在: " + fold)
    if not os.path.isfile(a.srt) or not os.path.isfile(a.wav):
        raise SystemExit("SRT 或 wav 不存在")
    if J.jianying_running():
        raise SystemExit("剪映仍在运行，会回写草稿；请先完全退出")

    cues = parse_srt(a.srt)
    total_us = wav_duration_us(a.wav)
    print(f"草稿: {a.source}")
    print(f"字幕: {len(cues)} 条  |  旁白: {total_us/1e6:.2f}s  "
          f"({total_us/6e7:.2f} 分)")
    print(f"首条: {cues[0][2][:36]!r}")
    print(f"末条: {cues[-1][2][:36]!r}")
    if a.dry_run:
        print("预览模式，未写盘。")
        return

    paths = J.draft_info_paths(fold)
    # 两份工程 JSON 必须写入**完全相同**的数据：随机 UUID 只能生成一次，
    # 否则根目录与时间线副本的片段 id 不一致，剪映会以时间线副本覆盖根目录。
    # 以时间线副本为基准，与 fit-duration 保持一致。
    base_path = next((p for p in paths if os.sep + "Timelines" + os.sep in p), paths[0])
    d = J.decrypt_json(base_path)
    n, vi, si, total = inject_one(d, cues, a.wav, total_us)
    for p in paths:
        J.encrypt_json(p, d)
        print(f"  已写入 {os.path.relpath(p, fold)}")

    # 复核：两份工程一致、片段 id 唯一、素材引用齐全
    ds = [J.decrypt_json(p) for p in paths]
    print("\n校验:")
    print("  两份工程 JSON 一致:", "✅" if ds[0] == ds[1] else "❌")
    d = ds[0]
    ids = [s["id"] for t in d["tracks"] for s in t.get("segments", [])]
    print(f"  segment id 重复: {len(ids)-len(set(ids))} / {len(ids)}")
    mids = {m["id"] for k, arr in d["materials"].items()
            if isinstance(arr, list) for m in arr if isinstance(m, dict) and m.get("id")}
    missing = [s["material_id"] for t in d["tracks"] for s in t.get("segments", [])
               if s.get("material_id") not in mids]
    print("  素材引用缺失:", len(missing))
    sub = J.subtitle_track(d)
    print(f"  字幕段: {len(sub['segments'])}  | 顶层 duration: {d.get('duration')}")
    if ds[0] != ds[1] or len(ids) != len(set(ids)) or missing:
        raise SystemExit("校验未通过，请检查")

    # 关键收尾：剪映还有一份独立的「链接媒体登记表」在加密 draft_meta_info.json
    # 里（draft_materials[type=0].value[].file_Path）。只改工程 path 会让登记表
    # 仍指向源草稿的 wav / 或干脆没有本书条目，剪映打开就弹「链接媒体丢失」，
    # 导出还可能没有旁白。fix_media_one 会搬音频进草稿内并重建登记表。
    print("\n同步链接媒体登记表（fix-media）…")
    J.fix_media_one(fold)


if __name__ == "__main__":
    main()
