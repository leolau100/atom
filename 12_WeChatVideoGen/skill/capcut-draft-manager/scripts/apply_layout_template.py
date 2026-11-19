#!/usr/bin/env python3
"""套用「标题 + 字幕」坐标模板（用户 2026-11-16 在《活着》草稿里调好后确认的新模板）。

把字幕轨全部片段、标题轨（type=text 且仅 1 段的顶部书名）的 clip.scale / clip.transform
设成模板值。只动坐标/缩放，不碰文本、配音、时间轴。

用法:
  python3 apply_layout_template.py <草稿名> [--dry-run] [--no-quit]
"""
import sys, os, json, argparse, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jy_draft as J

# 用户 2026-11-16 确认的新模板（来自改后的《活着》草稿）
# 字幕轨（正文）：scale 0.21，位置 x=0.1616243516 y=-0.0229360965
SUBTITLE_SCALE = {"x": 0.21, "y": 0.21}
SUBTITLE_TRANSFORM = {"x": 0.16162435162435163, "y": -0.022936096453552546}
# 标题轨（顶部书名，type=text 且仅 1 段）：scale 0.3504791069，位置 x=-0.0346906847 y=0.3870542764
TITLE_SCALE = {"x": 0.35047910687294226, "y": 0.35047910687294226}
TITLE_TRANSFORM = {"x": -0.03469068472791481, "y": 0.38705427635455214}
# 播放器装饰轨（type=sticker，scale.x≈0.61 的那条）：位置 x=0.1645219307 y=-0.4317739389
# 用 scale.x 接近 0.61 识别（其它 sticker 分别 ≈0.33 / ≈0.17）
PLAYER_SCALE_X = 0.6106738102592387
PLAYER_SCALE = {"x": 0.6106738102592387, "y": 0.6106738102592387}
PLAYER_TRANSFORM = {"x": 0.16452193071701648, "y": -0.43177393886545246}


def apply(seg, scale, transform):
    clip = seg.setdefault("clip", {})
    if scale:
        clip["scale"] = json.loads(json.dumps(scale))
    if transform:
        clip["transform"] = json.loads(json.dumps(transform))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-quit", action="store_true")
    args = ap.parse_args()

    fold = os.path.join(J.DEFAULT_ROOT, args.draft)
    paths = J.draft_info_paths(fold)
    base = J.decrypt_json(paths[1])
    tracks = base.get("tracks", [])

    # 字幕轨 = type=text 且片段数>1（取最多）
    sub = [t for t in tracks if t.get("type") == "text" and len(t.get("segments", [])) > 1]
    sub = max(sub, key=lambda t: len(t["segments"])) if sub else None
    # 标题轨 = type=text 且仅 1 段（排除字幕轨）
    title = [t for t in tracks if t.get("type") == "text" and len(t.get("segments", [])) == 1]
    title = title[0] if title else None
    # 播放器装饰轨 = sticker 且首段 scale.x≈0.61
    player = None
    for t in tracks:
        segs = t.get("segments", [])
        if t.get("type") == "sticker" and segs:
            sx = (segs[0].get("clip", {}).get("scale") or {}).get("x", 0)
            if abs(sx - PLAYER_SCALE_X) < 0.02:
                player = t
                break

    print("字幕轨: %d 段; 标题轨: %s; 播放器轨: %s" % (
        len(sub["segments"]) if sub else 0, "有" if title else "无", "有" if player else "无"))
    if args.dry_run:
        print("[dry-run] 未写盘")
        return

    if not args.no_quit:
        subprocess.run([sys.executable, os.path.join(HERE, "open_draft.py"), "--quit-only"],
                       check=False)

    if sub:
        for s in sub["segments"]:
            apply(s, SUBTITLE_SCALE, SUBTITLE_TRANSFORM)
    if title:
        apply(title["segments"][0], TITLE_SCALE, TITLE_TRANSFORM)
    if player:
        for s in player["segments"]:
            apply(s, PLAYER_SCALE, PLAYER_TRANSFORM)

    for p in paths:
        J.encrypt_json(p, base, backup=True)
    a = J.decrypt_json(paths[0]); b = J.decrypt_json(paths[1])
    ok = json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    print("两份工程一致: %s; 已套用坐标模板" % ok)


if __name__ == "__main__":
    main()
