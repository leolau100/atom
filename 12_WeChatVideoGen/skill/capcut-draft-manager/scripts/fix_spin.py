#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正「唱片/光盘」旋转动画：让旋转覆盖整片，并把转速调到肉眼可辨。

背景（2026-11-18 实测）：
  母版草稿里那条光盘是一条独立 video 轨，旋转由 segment.common_keyframes 里的
  KFTypeRotation 关键帧驱动：

      clip.rotation            = 360.0          # 静态值（有关键帧时忽略）
      common_keyframes[0].property_type = "KFTypeRotation"
      keyframe_list[0]  time_offset=0        values=[360.0]
      keyframe_list[1]  time_offset=570.3s   values=[1171.0]   # → 共转 2.25 圈

  两个坑：
  1) 关键帧终点的 time_offset 固定是 570.3s（《小王子》的片长）。fit_tracks 只改
     target_timerange / source_timerange，**完全不碰 common_keyframes**，所以片长被
     拉到 1400s+ 之后，光盘转完 9.5 分钟就彻底静止，后面 14 分钟一动不动。
  2) 570.3s 只转 2.25 圈 = 每圈 253 秒（约 4.2 分钟），肉眼几乎看不出在转。

  本脚本把终点 time_offset 对齐到片长，并按「每圈 N 秒」重算总转角。

用法:
  python3 fix_spin.py <草稿名> [--per-turn 10] [--dry-run] [--no-quit]

  --per-turn   每转一圈的秒数，默认 10。越小转得越快。
               5 → 很快    10 → 快（默认）   15 → 很醒目
               30 → 均衡   60 → 接近原始观感   0 → 只修时长同步，不改转速
  本脚本是幂等的：总转角按「片长 / 每圈秒数」重算，重跑不会角度叠加，
  可随时改档位重新运行。
"""

import sys, os, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jy_draft as J

KF_ROTATION = "KFTypeRotation"


def find_rotation(d):
    """返回 [(track_idx, seg_idx, segment, kf)] —— 所有带旋转关键帧的片段。"""
    hits = []
    for ti, tr in enumerate(d.get("tracks") or []):
        for si, seg in enumerate(tr.get("segments") or []):
            for kf in (seg.get("common_keyframes") or []):
                if kf.get("property_type") == KF_ROTATION:
                    hits.append((ti, si, seg, kf))
    return hits


def remap(kf, new_span_us, per_turn, start_angle):
    """把关键帧的 [角度, 时间] 线性重映射到新时长与新转速。返回新终点角度。"""
    kl = kf.get("keyframe_list") or []
    if len(kl) < 2:
        return None
    p0 = kl[0]
    t_old = float(p0.get("time_offset") or 0)
    span_old = float(kl[-1].get("time_offset") or 0) - t_old
    a0 = float((p0.get("values") or [start_angle])[0])

    if per_turn and per_turn > 0:
        turns = max(1, round(new_span_us / 1e6 / per_turn))
    else:
        turns = None
    if turns is None:
        a_new = float(kl[-1].get("values", [a0])[0])
    else:
        a_new = a0 + turns * 360.0

    for p in kl:
        ratio = 0.0 if span_old <= 0 else (
            (float(p.get("time_offset") or 0) - t_old) / span_old)
        ratio = min(max(ratio, 0.0), 1.0)
        p["time_offset"] = t_old + ratio * new_span_us
        vals = p.get("values") or []
        if vals:
            vals[0] = a0 + ratio * (a_new - a0)
            p["values"] = vals
    return a_new, turns


def apply_to_draft(data, per_turn):
    """就地修改 data，返回修改摘要列表。"""
    notes = []
    total = int(data.get("duration") or 0)
    for ti, si, seg, kf in find_rotation(data):
        clip = seg.setdefault("clip", {})
        static = float(clip.get("rotation") or 0)
        start_angle = static if static else 360.0
        res = remap(kf, total, per_turn, start_angle)
        if not res:
            notes.append(f"track[{ti}] 关键帧点不足，跳过")
            continue
        a_new, turns = res
        clip["rotation"] = a_new
        kl = kf["keyframe_list"]
        t_end = float(kl[-1].get("time_offset") or 0)
        a_end = float(kl[-1].get("values", [0])[0])
        per = (t_end - float(kl[0].get("time_offset") or 0)) / 1e6 / turns if turns else 0
        notes.append(
            f"track[{ti}] 终点 t={t_end/1e6:.1f}s 角度={a_end:.0f}° "
            f"总 {turns} 圈 / 每圈 {per:.1f}s")
    return notes


def main():
    ap = argparse.ArgumentParser(description="修正光盘旋转关键帧")
    ap.add_argument("source", help="草稿名")
    ap.add_argument("--per-turn", type=float, default=10.0,
                    help="每圈秒数，0 表示只修时长同步")
    ap.add_argument("--root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="直接改，忽略剪映运行状态")
    ap.add_argument("--no-quit", action="store_true", help="不要退出剪映")
    args = ap.parse_args()

    root = J.resolve_root(args.root)
    if not args.dry_run and not args.no_quit:
        J.auto_quit(args.force, args.no_quit)

    data_idx = J.load_index(root)
    _i, entry = J.find_entry(data_idx, args.source)
    if entry is None:
        J.fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    paths = J.draft_info_paths(fold)
    if not paths:
        J.fail("找不到任何 draft_info.json")

    print(f"草稿: {args.source}")
    print(f"每圈秒数: {args.per_turn if args.per_turn else '仅同步时长(不改转速)'}")

    # 根目录副本为基准，时间线副本同源，两份都要写
    base = J.decrypt_json(paths[0])
    total = int(base.get("duration") or 0)
    print(f"片长: {total/1e6:.1f}s")
    if not total:
        J.fail("片长为 0，先跑 fit-duration")

    # 先在基准上算一遍结果用于预览
    import copy as _copy
    preview = _copy.deepcopy(base)
    notes = apply_to_draft(preview, args.per_turn)
    if not notes:
        J.fail("该草稿里没有找到旋转关键帧（KFTypeRotation）")
    for n in notes:
        print("  " + n)

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return

    for p in paths:
        d = J.decrypt_json(p)
        apply_to_draft(d, args.per_turn)
        J.encrypt_json(p, d)
        print(f"  已写入 {os.path.relpath(p, fold)}")

    # 同步 meta 时长（关键帧已随片长对齐，这里只保险）
    print("[完成] 旋转关键帧已重算")


if __name__ == "__main__":
    main()
