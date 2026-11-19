#!/usr/bin/env python3
"""字幕「一小句一条」（用户 2026-11-16 最终规则）。

把每条字幕按中文标点切成小分句（标点留在句尾），再去掉每条小句尾部的
断句标点（分行本身即停顿）；成对引号 ""、书名号《》、括号等保留。
时间轴按各小句字数比例从原段时长分配；配音是独立整段 wav，拆字幕不影响声音。

只改 material 的 content.text + styles[0].range，以及 segment 的时间/id；
不动配音轨、位置/缩放/字号、BGM。两份 draft_info.json 写同一份数据。

用法:
  python3 split_subtitles.py <草稿名> [--dry-run] [--no-quit]
"""
import sys, os, json, copy, uuid, argparse, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jy_draft as J

# 断点标点：遇到就切开（切开后尾部断句标点会被去掉）
BREAK = set("，。！？；：、,!?;:")
# 只去掉这些句尾断句标点；成对引号 ""/书名号《》/括号 ()（）【】《》〈〉「」『』 保留
TAIL = "，。！？；：、,!?;:"
# 无标点长句硬切阈值（避免极少数超长句一行放不下）
HARD = 69


def split_clauses(text):
    """按标点切成小分句，去掉每句尾部断句标点（保留成对符号）。"""
    out, buf = [], []
    for ch in text:
        buf.append(ch)
        if ch in BREAK:
            seg = "".join(buf)
            seg = seg.rstrip(TAIL).strip()
            if seg:
                out.append(seg)
            buf = []
    tail = "".join(buf).rstrip(TAIL).strip()
    if tail:
        out.append(tail)
    # 极少数无标点超长句硬切（已 rstrip，这里按字数切）
    final = []
    for s in out:
        while len(s) > HARD:
            final.append(s[:HARD])
            s = s[HARD:]
        if s:
            final.append(s)
    return final or ([text.rstrip(TAIL).strip()] if text.strip() else [])


def new_uuid():
    return str(uuid.uuid4()).upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", help="草稿名")
    ap.add_argument("--dry-run", action="store_true", help="只预演不写盘")
    ap.add_argument("--no-quit", action="store_true",
                    help="不退出剪映（链路中前面已退出时用）")
    args = ap.parse_args()

    fold = os.path.join(J.DEFAULT_ROOT, args.draft)
    paths = J.draft_info_paths(fold)
    base = J.decrypt_json(paths[1])
    tr = J.subtitle_track(base)
    texts = {m["id"]: m for m in base["materials"]["texts"]}
    anims = {m["id"]: m for m in base["materials"].get("material_animations", [])}
    segs = tr["segments"]

    def get_text(mid):
        try:
            return str(json.loads(texts[mid].get("content", "{}")).get("text", ""))
        except Exception:
            return ""

    plan = [(s, get_text(s["material_id"]), split_clauses(get_text(s["material_id"])))
            for s in segs]
    n_new = sum(len(p) for _, _, p in plan)
    part_lens = [len(p) for _, _, ps in plan for p in ps]
    print("原段数 %d -> 新段数 %d (新增 %d)" % (len(segs), n_new, n_new - len(segs)))
    if part_lens:
        print("平均 %.1f 字/条, 最长 %d 字" % (sum(part_lens)/len(part_lens), max(part_lens)))
    for s, t, ps in plan[:5]:
        print("  [%d字] %s" % (len(t), t))
        print("     -> %d条: %s" % (len(ps), " / ".join(ps)))
    if args.dry_run:
        print("[dry-run] 未写盘")
        return

    if not args.no_quit:
        subprocess.run([sys.executable, os.path.join(HERE, "open_draft.py"), "--quit-only"],
                       check=False)

    old_text_ids, old_anim_ids = set(), set()
    new_segs = []
    for s, t, parts in plan:
        st = s.get("target_timerange", {}).get("start", 0)
        dur = s.get("target_timerange", {}).get("duration", 0)
        old_text_ids.add(s["material_id"])
        old_anim_ids.update(s.get("extra_material_refs") or [])
        total = len(t)
        acc = 0
        for part in parts:
            pdur = round(dur * len(part) / total) if total else 0
            mid, sid, aid = new_uuid(), new_uuid(), new_uuid()
            mat = copy.deepcopy(texts[s["material_id"]])
            mat["id"] = mid
            cj = json.loads(mat.get("content", "{}"))
            cj["text"] = part
            if cj.get("styles"):
                st0 = copy.deepcopy(cj["styles"][0])
                st0["range"] = [0, len(part)]
                cj["styles"] = [st0]
            mat["content"] = json.dumps(cj, ensure_ascii=False, separators=(",", ":"))
            base["materials"]["texts"].append(mat)
            seg = copy.deepcopy(s)
            seg["id"] = sid
            seg["material_id"] = mid
            seg["target_timerange"] = {"start": st + acc, "duration": pdur}
            seg["extra_material_refs"] = [aid]
            seg["render_index"] = 0
            new_segs.append(seg)
            acc += pdur
            templ = anims.get((s.get("extra_material_refs") or [None])[0])
            an = copy.deepcopy(templ) if templ else {"type": "sticker_animation"}
            an["id"] = aid
            base["materials"].setdefault("material_animations", []).append(an)

    keep_mid = {x["material_id"] for x in new_segs}
    base["materials"]["texts"] = [m for m in base["materials"]["texts"]
                                  if m["id"] not in old_text_ids or m["id"] in keep_mid]
    new_segs.sort(key=lambda x: x.get("target_timerange", {}).get("start", 0))
    for i, sg in enumerate(new_segs):
        sg["render_index"] = 14098 + i
    tr["segments"] = new_segs
    used = {r for sg in new_segs for r in (sg.get("extra_material_refs") or [])}
    base["materials"]["material_animations"] = [a for a in base["materials"].get(
        "material_animations", []) if a["id"] in used]

    for p in paths:
        J.encrypt_json(p, base, backup=True)
    # 一致性复核
    a = J.decrypt_json(paths[0])
    b = J.decrypt_json(paths[1])
    ok = json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
        b, sort_keys=True, ensure_ascii=False)
    print("两份工程一致: %s; 已写入, 新段数=%d" % (ok, len(new_segs)))


if __name__ == "__main__":
    main()
