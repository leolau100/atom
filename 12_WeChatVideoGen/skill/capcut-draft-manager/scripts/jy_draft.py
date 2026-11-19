#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""剪映专业版（macOS 10.x）本地草稿管理 —— WorkBuddy 增强版

子命令:
  list                       列出所有草稿
  copy    -s 源 [-n 新名] [-t 书名]  复制草稿（整目录 + 内外层 id 同步）
  rename  -s 源 -n 新名      修改草稿标题（目录 + 外层索引 + 内层加密 meta）
  retitle -s 草稿 -t 新书名  改时间线里的书名标题并重新生成封面
  set-bg  -s 草稿 -i 图片     替换背景/配图（去 AI 标识）+ 用新图重做封面
  fix-cover -s 草稿          全量重做封面（所有 jpg/png 副本 + 内嵌封面工程）
  fit-duration -s 草稿       把背景图/BGM/贴纸/标题对齐到字幕与配音总时长
  fix-subtitles -s 草稿      对齐字幕样式；默认 flat=去硬换行、保留标点、一整句一行、宽度不变
                              旧 23 字折行需显式 --max-chars 23；--strip-punct 可显式去标点
  materials -s 草稿名        查看草稿素材引用（解密 draft_info.json）
  backup  -d 目标目录        备份整个草稿库
  reopen  [草稿名]           重开剪映并把指定草稿置顶
  covers  -s 书名            收尾：调用文章仓库两个脚本生成手机竖版+电脑横版封面，
                              输出到该文章 markdown 同目录（不碰剪映、不改草稿）

相对 Marvis 原版的修复（2026-11-14 实测校准）:
  1. copy / rename 同步回写内层加密 draft_meta_info.json 的
     draft_id / draft_name / draft_fold_path / 云字段，避免副本与源撞 id、
     避免改名后标题被剪映改回。原来只改外层索引是「半校准」。
  2. materials 改为解密 draft_info.json 读取 materials.*.path，并还原
     draftpath 占位符。原版依赖的 Timelines/project.json 实测只有配置、
     不含任何素材路径。
  3. backup 增加剪映运行态警告；list 提示 draft_ids 漂移。
  4. 所有写操作统一重算 draft_ids；rename 源目录缺失时直接报错，
     不再把索引指向一个不存在的目录。
  5. 按用户约定「零操作」：写操作前自动完全退出剪映，完成后自动重开
     并把目标草稿置顶（--no-reopen 可关闭）。

依赖: scripts/bin/jy-draftc-mac（自带）、剪映 App 的
      /Applications/VideoFusion-macOS.app/Contents/Frameworks/libvideoeditor.dylib
"""

import argparse
import json
import os
import re
import unicodedata
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEFAULT_ROOT = os.path.expanduser(
    "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
)
INDEX_NAME = "root_meta_info.json"
PROC_PATTERN = "VideoFusion-macOS"
APP_FRAMEWORKS = "/Applications/VideoFusion-macOS.app/Contents/Frameworks"
CRYPTO_BIN = os.path.join(HERE, "bin", "jy-draftc-mac")
CRYPTO_ENV = dict(os.environ, DYLD_LIBRARY_PATH=APP_FRAMEWORKS)
COVER_SCRIPT = os.path.join(HERE, "make_cover.py")
COVER_BASE = os.path.join(HERE, "assets", "series_bg.jpg")
PLACEHOLDER = "##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##"


# ---------------- 基础工具 ----------------

def fail(msg, code=1):
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(code)


def now_us():
    return int(time.time() * 1000000)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024.0
    return f"{n:.1f}GB"


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def jianying_running():
    try:
        out = subprocess.run(["pgrep", "-f", PROC_PATTERN],
                             capture_output=True, text=True)
        return bool(out.stdout.strip())
    except Exception:
        return False


def auto_quit(force=False, no_quit=False):
    """写操作前自动完全退出剪映（用户约定：零操作，不要求用户手动 Cmd+Q）。"""
    if no_quit:
        print("· --no-quit：假定剪映已退出，跳过退出检查")
        return
    if not jianying_running():
        print("· 剪映未运行，可直接修改")
        return
    if force:
        print("· --force：跳过自动退出（请确认剪映确已退出，否则改动会被回写覆盖）")
        return
    print("· 剪映正在运行，先自动完全退出 …")
    try:
        import open_draft
        if not open_draft.quit_jianying():
            fail("无法完全退出剪映，已中止，避免改动被内存状态覆盖")
    except ImportError:
        fail("缺少同目录的 open_draft.py，无法自动退出剪映")


def maybe_reopen(name, enabled=True, root=None):
    """写操作后自动重开剪映，并让目标草稿排在草稿箱第一位。"""
    if not enabled:
        print("· --no-reopen：保持剪映关闭（需要时手动运行 reopen 子命令）")
        return
    try:
        import open_draft
        if root:
            open_draft.REGISTRY = os.path.join(root, INDEX_NAME)
        open_draft.reopen(name, quit_first=False, click_if_possible=True)
    except ImportError:
        print("· [提示] 缺少 open_draft.py，跳过自动重开")


# ---------------- 加解密 ----------------

def _crypto(mode, src, dst):
    if not os.path.isfile(CRYPTO_BIN):
        fail(f"缺少加解密工具: {CRYPTO_BIN}")
    r = subprocess.run([CRYPTO_BIN, mode, src, dst],
                       env=CRYPTO_ENV, capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"jy-draftc {mode} 失败: {(r.stderr or r.stdout).strip()[:200]}")


def decrypt_json(path):
    """解密剪映加密 JSON，返回 dict。使用空 context，与剪映实际存储一致。"""
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        _crypto("decrypt", path, tmp)
        with open(tmp, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        fail(f"解密结果不是合法 JSON: {path} -> {e}")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def encrypt_json(path, data, backup=True):
    """把 dict 加密后原子覆盖回剪映文件（先备份原密文）。"""
    fd, tmp = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    try:
        if backup and os.path.isfile(path):
            try:
                with open(path, "rb") as _fsrc, open(f"{path}.bak_{int(time.time())}", "wb") as _fdst:
                    _fdst.write(_fsrc.read())
            except OSError:
                pass
        _crypto("encrypt", tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------- 索引 ----------------

def resolve_root(arg):
    root = os.path.expanduser(arg) if arg else DEFAULT_ROOT
    if not os.path.isdir(root):
        fail(f"草稿根目录不存在: {root}")
    return root


def index_path(root):
    return os.path.join(root, INDEX_NAME)


def load_index(root):
    p = index_path(root)
    if not os.path.isfile(p):
        fail(f"索引文件不存在: {p}")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        fail(f"索引文件不是合法 JSON（可能已损坏）: {e}")


MIRROR_INDEX = os.path.expanduser(
    "~/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/"
    "Projects/com.lveditor.draft/root_meta_info.json"
)


def mirror_index_path():
    """剪映沙盒容器内的索引副本（若存在）。实测两份内容完全一致。"""
    return MIRROR_INDEX if os.path.isfile(MIRROR_INDEX) else None


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def backup_index(root):
    p = index_path(root)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = f"{p}.bak.{stamp}"
    shutil.copy2(p, dst)
    mp = mirror_index_path()
    if mp and os.path.abspath(mp) != os.path.abspath(p):
        try:
            shutil.copy2(mp, f"{mp}.bak.{stamp}")
        except OSError:
            pass
    return dst


def save_index(root, data):
    """原子写入主索引，并同步沙盒容器副本。

    剪映 10.3.0 在 ~/Movies/... 和 ~/Library/Containers/com.lemon.lvpro/...
    各维护一份 root_meta_info.json，启动时以容器副本为准并回写主索引。
    只写一份可能被旧副本覆盖，故两份都写。
    """
    data["draft_ids"] = len(data.get("all_draft_store", []))
    p = index_path(root)
    _atomic_write(p, data)
    mp = mirror_index_path()
    if mp and os.path.abspath(mp) != os.path.abspath(p):
        try:
            _atomic_write(mp, data)
            print("  · 已同步沙盒容器索引副本")
        except OSError as e:
            print(f"  [提示] 容器索引同步失败（主索引已写入）: {e}")


def find_entry(data, name):
    for i, e in enumerate(data.get("all_draft_store", [])):
        if e.get("draft_name") == name or os.path.basename(
                e.get("draft_fold_path", "")) == name:
            return i, e
    return -1, None


def unique_dir(root, name):
    target = os.path.join(root, name)
    if not os.path.exists(target):
        return target, name
    n = 1
    while True:
        cand_name = f"{name} ({n})"
        cand = os.path.join(root, cand_name)
        if not os.path.exists(cand):
            return cand, cand_name
        n += 1


def refresh_paths(entry, new_dir_name):
    root_path = entry.get("draft_root_path") or os.path.dirname(
        entry.get("draft_fold_path", ""))
    fold = os.path.join(root_path, new_dir_name)
    entry["draft_name"] = new_dir_name
    entry["draft_fold_path"] = fold
    entry["draft_json_file"] = os.path.join(fold, "draft_info.json")
    entry["draft_cover"] = os.path.join(fold, "draft_cover.jpg")
    entry["draft_root_path"] = root_path
    return entry


def reset_cloud_fields(entry):
    entry["cloud_draft_sync"] = False
    entry["cloud_draft_cover"] = False
    entry["draft_cloud_template_id"] = ""
    entry["draft_cloud_tutorial_info"] = ""
    entry["draft_cloud_purchase_info"] = ""
    entry["draft_cloud_videocut_purchase_info"] = ""
    entry["draft_cloud_capcut_purchase_info"] = ""
    for k in list(entry.keys()):
        if k.startswith("tm_draft_cloud_") or k.startswith("cloud_"):
            entry[k] = 0 if isinstance(entry[k], int) else (
                False if isinstance(entry[k], bool) else "")
    return entry


# ---------------- 内层加密 meta 同步（核心修复） ----------------

def sync_inner_meta(fold, draft_id, name, is_copy=False):
    """同步草稿目录内加密的 draft_meta_info.json。

    实测该加密包内含 draft_id / draft_name / draft_fold_path / 云同步字段，
    剪映会读取它。只改外层 root_meta_info.json 会产生「半校准」副本：
    id 撞车、改名被改回、副本去拉云端状态。
    """
    p = os.path.join(fold, "draft_meta_info.json")
    if not os.path.isfile(p):
        print("  [提示] 无 draft_meta_info.json，跳过内层同步")
        return False
    d = decrypt_json(p)
    before = (d.get("draft_id"), d.get("draft_name"))
    d["draft_id"] = draft_id
    d["draft_name"] = name
    d["draft_fold_path"] = fold
    d["draft_root_path"] = os.path.dirname(fold)
    d["draft_cover"] = os.path.join(fold, "draft_cover.jpg")
    d["draft_need_rename_folder"] = False
    d["draft_is_invisible"] = False
    reset_cloud_fields(d)
    if is_copy:
        d["tm_draft_create"] = now_us()
    d["tm_draft_modified"] = now_us()
    encrypt_json(p, d)
    print(f"  · 内层 meta 已同步: {before[0]} → {draft_id} / {before[1]} → {name}")
    return True


# ---------------- 书名标题 / 封面 ----------------

def norm_title(s):
    return (s or "").strip().strip("《》").strip()


def draft_info_paths(fold):
    """根目录 + 所有 Timelines/<content_id>/ 下的 draft_info.json。

    实测剪映以时间线副本为准并回写根目录，只改一份会被覆盖。
    content id 必须保持与 Timelines 目录名一致，不要换 uuid。
    """
    paths = []
    root_info = os.path.join(fold, "draft_info.json")
    if os.path.isfile(root_info):
        paths.append(root_info)
    tl = os.path.join(fold, "Timelines")
    if os.path.isdir(tl):
        for sub in sorted(os.listdir(tl)):
            p = os.path.join(tl, sub, "draft_info.json")
            if os.path.isfile(p):
                paths.append(p)
    return paths


def retitle_draft(fold, old_title, new_title):
    """只替换精确等于书名的标题文本，不动正文里的同名字样（正文字幕是占位内容）。

    返回替换总数。styles[].range 会跟着新标题长度更新，避免样式截断。
    """
    old = norm_title(old_title)
    new = f"《{norm_title(new_title)}》"
    total = 0
    for p in draft_info_paths(fold):
        d = decrypt_json(p)
        n = 0
        for t in d.get("materials", {}).get("texts", []):
            c = t.get("content")
            if not isinstance(c, str):
                continue
            try:
                cj = json.loads(c)
            except (ValueError, TypeError):
                continue
            if not isinstance(cj, dict):
                continue
            txt = str(cj.get("text", "")).strip()
            if txt in (old, f"《{old}》"):
                cj["text"] = new
                for st in cj.get("styles", []):
                    if isinstance(st, dict) and "range" in st:
                        st["range"] = [0, len(new)]
                t["content"] = json.dumps(cj, ensure_ascii=False)
                n += 1
        if n:
            encrypt_json(p, d)
        total += n
        print(f"  · {os.path.relpath(p, fold)}: 标题替换 {n} 处")
    return total


def current_bg(fold):
    """取草稿当前正在使用的背景图绝对路径。

    封面必须用草稿自己的配图作底，不能退回 skill 内置的《小王子》星场图，
    否则 retitle / copy 重做封面时会把这本书的主题插画覆盖掉。
    """
    p = os.path.join(fold, "draft_info.json")
    if not os.path.isfile(p):
        return COVER_BASE
    try:
        d = decrypt_json(p)
    except Exception:
        return COVER_BASE
    for m in d.get("materials", {}).get("videos", []):
        if not isinstance(m, dict):
            continue
        raw = str(m.get("path", ""))
        if "/Resources/" not in raw or "defaultPlaceholder" in raw:
            continue
        if not raw.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        real = raw.replace(PLACEHOLDER + "/", fold + "/").replace(PLACEHOLDER, fold)
        if os.path.isfile(real):
            return real
    return COVER_BASE


def _fit_cover(src, size):
    """等比放大后居中裁切到目标尺寸，不拉伸变形。"""
    from PIL import Image
    w, h = size
    iw, ih = src.size
    s = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * s))), max(h, int(round(ih * s)))
    r = src.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return r.crop((left, top, left + w, top + h))


def sync_cover_copies(fold, cover_jpg, base_img=None):
    """把草稿内所有封面副本统一成当前书封面。

    剪映的「封面编辑」是嵌在 draft_info.json 里的一个 composition 草稿，
    独立持有底图 Resources/cover/*.png 和模板书名文字；渲染结果会缓存成
    Resources/cover/*.jpg，并在用户点开封面编辑再取消时写回
    draft_cover.jpg（2026-11-14 实测：封面「又变回上一本书」的根因）。
    因此除了根目录的大图/缩略图，还必须同步：
      · Timelines/<content_id>/draft_cover.jpg（时间线副本）
      · draft_cover.jpg.bak
      · Resources/cover/*.jpg（封面候选/缓存，全部覆盖）
      · Resources/cover/*.png（封面编辑器底图，换成本书插画）
    """
    from PIL import Image
    jpgs, pngs = [], []
    targets = [os.path.join(fold, "draft_cover.jpg.bak")]
    tl = os.path.join(fold, "Timelines")
    if os.path.isdir(tl):
        for sub in os.listdir(tl):
            p = os.path.join(tl, sub, "draft_cover.jpg")
            if os.path.isfile(p):
                targets.append(p)
    cdir = os.path.join(fold, "Resources", "cover")
    if os.path.isdir(cdir):
        for f in sorted(os.listdir(cdir)):
            p = os.path.join(cdir, f)
            if f.lower().endswith((".jpg", ".jpeg")):
                jpgs.append(p)
            elif f.lower().endswith(".png"):
                pngs.append(p)
    targets += jpgs

    n = 0
    try:
        im = Image.open(cover_jpg).convert("RGB")
        for t in targets:
            if not os.path.isfile(t):
                continue
            try:
                sz = Image.open(t).size
                # 显式指定 format：draft_cover.jpg.bak 这种扩展名 PIL 猜不出来
                _fit_cover(im, sz).save(t, format="JPEG", quality=92)
                n += 1
            except Exception as e:
                print(f"  [提示] 跳过 {os.path.relpath(t, fold)}: {e}")
        print(f"  · 封面 jpg 副本已同步 {n} 个（时间线副本 / .bak / 封面候选）")
    except Exception as e:
        print(f"  [提示] 封面副本同步失败: {e}")

    if base_img and os.path.isfile(base_img) and pngs:
        try:
            bg = Image.open(base_img).convert("RGB")
            for p in pngs:
                sz = Image.open(p).size
                _fit_cover(bg, sz).save(p)
            print(f"  · 封面编辑器底图已换成本书插画（{len(pngs)} 个 png）")
        except Exception as e:
            print(f"  [提示] 封面底图同步失败: {e}")


def is_light_bg(fold):
    """当前配图是否为明亮浅色插画（决定封面文字用深墨还是白色）。"""
    try:
        from PIL import Image, ImageStat
        p = current_bg(fold)
        if not p or not os.path.isfile(p):
            return False
        im = Image.open(p).convert("RGB").resize((64, 64))
        return sum(ImageStat.Stat(im).mean) / 3 >= 140
    except Exception:
        return False


def sync_cover_editor_title(fold, title):
    """把内嵌封面工程的模板书名改成当前书名（两份 draft_info.json 都改）。"""
    full = "《" + norm_title(title) + "》"
    light = is_light_bg(fold)
    fill_rgb = [0.16, 0.19, 0.23] if light else [1, 1, 1]
    text_hex = "#2A303B" if light else "#FFFFFF"
    total = 0
    for p in draft_info_paths(fold):
        d = decrypt_json(p)
        changed = 0
        for comp in d.get("materials", {}).get("drafts", []) or []:
            sub = comp.get("draft") or {}
            for m in (sub.get("materials", {}).get("texts", []) or []):
                raw = m.get("content")
                if not (isinstance(raw, str) and raw.startswith("{")):
                    continue
                try:
                    cj = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if "text" not in cj:
                    continue
                cj["text"] = full
                for st in cj.get("styles", []) or []:
                    if not isinstance(st, dict):
                        continue
                    if "range" in st:
                        st["range"] = [0, len(full)]
                    # 深色插画用白字；明亮水彩插画白字看不清，改深墨色
                    fill = st.get("fill")
                    if isinstance(fill, dict):
                        solid = (fill.get("content") or {}).get("solid")
                        if isinstance(solid, dict) and "color" in solid:
                            solid["color"] = list(fill_rgb)
                m["content"] = json.dumps(cj, ensure_ascii=False)
                if "text_color" in m:
                    m["text_color"] = text_hex
                changed += 1
        if changed:
            encrypt_json(p, d)
            total += changed
            print(f"  · {os.path.relpath(p, fold)}: 封面编辑器书名 → {full}（{changed} 处）")
    return total


def sync_cover_index(fold):
    """修正所有 `draft_cover` 绝对路径（草稿箱 + 编辑页各读一处）。

    剪映有两套独立的封面路径，用户「另存为草稿」/ 从别的草稿导入字幕时
    两者都会继承源草稿，指向上一本书的封面文件：
      · 外层 root_meta_info.json 的 all_draft_store[].draft_cover
        → 草稿箱缩略图读它（2026-11-14 19:45 实测）
      · 内层加密 draft_meta_info.json 的 draft_cover
        → 编辑页「点击编辑封面」/ 播放器封面预览读它（20:25 实测）
    只改外层会出现「草稿箱已换成本书、编辑页封面仍是上一本」。
    主索引 + 沙盒容器索引（同一 inode）+ 内层 meta 都要改。
    """
    fold = os.path.abspath(fold)
    root = os.path.dirname(fold)
    target = os.path.join(fold, "draft_cover.jpg")
    paths = [index_path(root)]
    mp = mirror_index_path()
    if mp and os.path.abspath(mp) != os.path.abspath(paths[0]):
        paths.append(mp)
    n = 0
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        changed = 0
        for e in data.get("all_draft_store", []):
            if os.path.abspath(str(e.get("draft_fold_path", ""))) != fold:
                continue
            if os.path.abspath(str(e.get("draft_cover", ""))) != target:
                print(f"  · 索引 draft_cover 修正: {e.get('draft_cover')} → {target}")
                e["draft_cover"] = target
                changed += 1
        if changed:
            _atomic_write(p, data)
            n += changed

    # 内层加密 meta：编辑页 / 封面编辑器读的是这里的 draft_cover，
    # 用 sync_inner_meta() 会重分配 draft_id，这里只改封面路径一个字段。
    meta_p = os.path.join(fold, "draft_meta_info.json")
    if os.path.isfile(meta_p):
        try:
            meta = decrypt_json(meta_p)
            if os.path.abspath(str(meta.get("draft_cover", ""))) != target:
                print(f"  · 内层 meta draft_cover 修正: "
                      f"{meta.get('draft_cover')} → {target}")
                meta["draft_cover"] = target
                encrypt_json(meta_p, meta)
                n += 1
        except Exception as e:
            print(f"  [提示] 内层 meta 封面路径同步失败: {e}")
    if n:
        print(f"  · 已校正 {n} 处封面路径（外层索引 + 内层 meta）")
    return n


def make_cover(title, out, base=None):
    if base is None:
        base = current_bg(os.path.dirname(os.path.abspath(out)))
    if not os.path.isfile(COVER_SCRIPT):
        print("  [提示] 缺少 make_cover.py，跳过封面生成")
        return False
    r = subprocess.run([sys.executable, COVER_SCRIPT,
                        "--title", norm_title(title),
                        "--out", out, "--base", base or COVER_BASE,
                        "--no-backup"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  [提示] 封面生成失败:", (r.stderr or r.stdout).strip()[:200])
        return False
    print(f"  · 封面已更新: {out}")

    # 剪映草稿箱实际显示的是 320x180 的 draft_local_cover.jpg，而不是
    # draft_cover.jpg。只改大封面时，剪映启动会用旧缩略图把大封面同步回
    # 旧书封面（2026-11-14 实测踩坑），所以两个文件必须一起写。
    fold = os.path.dirname(os.path.abspath(out))
    try:
        from PIL import Image
        im = Image.open(out).convert("RGB")
        local = os.path.join(fold, "draft_local_cover.jpg")
        im.resize((320, 180), Image.LANCZOS).save(local, quality=92)
        print(f"  · 缩略图已同步: {os.path.basename(local)}")
    except Exception as e:
        print(f"  [提示] 缩略图同步失败（草稿箱可能仍显示旧封面）: {e}")

    # 关键：剪映「封面编辑」打开的是内嵌 composition 草稿工程，它有自己的
    # 底图与模板书名，渲染结果缓存为 Resources/cover/*.jpg。只改根目录 jpg
    # 时，点开封面编辑再取消，剪映会把旧模板缓存写回 draft_cover.jpg
    # —— 这就是封面「又变回上一本书」的根因（2026-11-14 实测）。
    # 所有封面副本 + 内嵌工程必须一起同步，不能只改两个 jpg。
    sync_cover_copies(fold, out, base)
    if title:
        sync_cover_editor_title(fold, title)
    sync_cover_index(fold)
    return True


# ---------------- 复制过滤 ----------------

def copy_ignore(dirpath, names):
    """排除纯备份/临时文件（不含素材引用），保留 Resources/ 与 Timelines/ 全部内容。"""
    skip = set()
    for n in names:
        full = os.path.join(dirpath, n)
        if n in (".backup", ".DS_Store"):
            skip.add(n)
        elif os.path.isfile(full) and (
                ".bak" in n or n.endswith(".tmp") or n.startswith("template-")):
            skip.add(n)
    return skip


# ---------------- 子命令 ----------------

def cmd_list(args):
    root = resolve_root(args.root)
    data = load_index(root)
    arr = data.get("all_draft_store", [])
    print(f"草稿根目录: {root}")
    print(f"索引草稿数: {len(arr)}  (draft_ids={data.get('draft_ids')})")
    if data.get("draft_ids") != len(arr):
        print(f"  ⚠️ draft_ids 与实际条目数不一致，任一写操作会自动重算")
    print()
    print(f"{'#':<3}{'草稿名':<24}{'修改时间':<20}{'大小':<10}{'目录存在'}")
    print("-" * 78)
    for i, e in enumerate(arr, 1):
        fold = e.get("draft_fold_path", "")
        exists = "是" if os.path.isdir(fold) else "否(缺失)"
        size = human_size(dir_size(fold)) if os.path.isdir(fold) else "-"
        mt = e.get("tm_draft_modified") or 0
        try:
            mt_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mt / 1e6))
        except (ValueError, OSError):
            mt_str = "-"
        name = e.get("draft_name", "")
        pad = 24 - sum(2 if ord(c) > 127 else 1 for c in name)
        print(f"{i:<3}{name}{' ' * max(pad, 0)}{mt_str:<20}{size:<10}{exists}")
    print()
    print("提示: 写操作会自动退出并重新打开剪映。")


def cmd_copy(args):
    root = resolve_root(args.root)
    auto_quit(args.force, args.no_quit)
    data = load_index(root)
    _idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}（用 list 查看准确名称）")

    src_dir = entry.get("draft_fold_path", "")
    if not os.path.isdir(src_dir):
        fail(f"源草稿目录不存在: {src_dir}")

    src_name = entry.get("draft_name") or os.path.basename(src_dir)
    want = args.name or f"{src_name} 副本"
    dst_dir, dst_name = unique_dir(root, want)

    bak = backup_index(root)
    print(f"[1/6] 已备份索引: {bak}")
    print(f"[2/6] 复制目录: {src_dir} -> {dst_dir}")
    shutil.copytree(src_dir, dst_dir, ignore=copy_ignore)
    print(f"      复制完成，占用 {human_size(dir_size(dst_dir))}（已跳过备份/临时文件）")

    new_id = str(uuid.uuid4()).upper()
    print(f"[3/6] 新 draft_id: {new_id}")
    sync_inner_meta(dst_dir, new_id, dst_name, is_copy=True)

    new_entry = json.loads(json.dumps(entry, ensure_ascii=False))
    refresh_paths(new_entry, dst_name)
    reset_cloud_fields(new_entry)
    new_entry["draft_id"] = new_id
    ts = now_us()
    new_entry["tm_draft_create"] = ts
    new_entry["tm_draft_modified"] = ts
    if "draft_timeline_materials_size" in new_entry:
        new_entry["draft_timeline_materials_size"] = dir_size(dst_dir)

    data["all_draft_store"].insert(0, new_entry)
    save_index(root, data)
    print(f"[4/6] 外层索引已写入（置顶，draft_ids={len(data['all_draft_store'])}）")

    if args.title:
        print(f"[5/6] 书名改为《{norm_title(args.title)}》")
        n = retitle_draft(dst_dir, args.from_title or src_name, args.title)
        if not n:
            print("  [提示] 未找到精确匹配的标题文本，正文保持不变")
        make_cover(args.title, os.path.join(dst_dir, "draft_cover.jpg"))
    else:
        print("[5/6] 未指定 --title，时间线文字与封面沿用源草稿")

    print(f"[6/6] 完成：{dst_name}")
    print(f"      目录: {dst_dir}")
    maybe_reopen(dst_name, not args.no_reopen, root)


def cmd_rename(args):
    root = resolve_root(args.root)
    auto_quit(args.force, args.no_quit)
    data = load_index(root)
    idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")

    old_dir = entry.get("draft_fold_path", "")
    if not os.path.isdir(old_dir):
        fail(f"源草稿目录不存在: {old_dir}（拒绝只改索引，否则草稿会指向不存在的目录）")
    new_name = args.name.strip()
    if not new_name or "/" in new_name:
        fail("新名称不能为空、且不能包含斜杠")

    target_dir, actual_name = unique_dir(root, new_name)
    bak = backup_index(root)
    print(f"[1/4] 已备份索引: {bak}")

    if os.path.abspath(old_dir) != os.path.abspath(target_dir):
        shutil.move(old_dir, target_dir)
        print(f"[2/4] 目录已重命名: {os.path.basename(old_dir)} -> {actual_name}")
    else:
        print("[2/4] 目录名未变化")

    sync_inner_meta(target_dir, entry.get("draft_id"), actual_name)
    refresh_paths(entry, actual_name)
    entry["tm_draft_modified"] = now_us()
    data["all_draft_store"][idx] = entry
    save_index(root, data)
    print(f"[3/4] 索引已更新: draft_name={actual_name}")
    print("[4/4] 完成")
    maybe_reopen(actual_name, not args.no_reopen, root)


def cmd_retitle(args):
    root = resolve_root(args.root)
    auto_quit(args.force, args.no_quit)
    data = load_index(root)
    _idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    if not os.path.isdir(fold):
        fail(f"草稿目录不存在: {fold}")
    print(f"改书名: {entry.get('draft_name')} → 《{norm_title(args.title)}》")
    n = retitle_draft(fold, args.from_title or entry.get("draft_name"), args.title)
    print(f"共替换 {n} 处标题文本")
    make_cover(args.title, os.path.join(fold, "draft_cover.jpg"))
    maybe_reopen(entry.get("draft_name"), not args.no_reopen, root)


def cmd_backup(args):
    root = resolve_root(args.root)
    if jianying_running():
        print("· [警告] 剪映正在运行，备份可能拿到不一致快照；建议先退出剪映再备份")
    dest_base = os.path.expanduser(args.dest)
    os.makedirs(dest_base, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(dest_base, f"lveditor.draft_{stamp}")
    print(f"正在备份: {root}\n     -> {dst}")
    shutil.copytree(root, dst)
    print(f"完成，共 {human_size(dir_size(dst))}")
    print(f"备份路径: {dst}")


def cmd_setbg(args):
    """替换草稿里的背景/配图，并用新图重做封面。"""
    root = resolve_root(args.root)
    auto_quit(args.force, args.no_quit)
    data = load_index(root)
    _idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    if not os.path.isdir(fold):
        fail(f"草稿目录不存在: {fold}")

    src_img = os.path.expanduser(args.image)
    if not os.path.isfile(src_img):
        fail(f"图片不存在: {src_img}")

    tmp_clean = None
    if not args.no_clean_mark:
        script = os.path.join(HERE, "clean_ai_mark.py")
        if os.path.isfile(script):
            fd, tmp_clean = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            r = subprocess.run([sys.executable, script,
                                "--in", src_img, "--out", tmp_clean],
                               capture_output=True, text=True)
            if r.returncode == 0:
                print("[1/5] 已去除右下角 AI 标识")
                src_img = tmp_clean
            else:
                print("[1/5] 去标识失败，使用原图:",
                      (r.stderr or r.stdout).strip()[:120])
        else:
            print("[1/5] 未找到 clean_ai_mark.py，跳过去标识")
    else:
        print("[1/5] --no-clean-mark：跳过去标识")

    filename = args.filename or (
        os.path.splitext(os.path.basename(args.image))[0] + ".jpg")
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        filename += ".jpg"
    res_dir = os.path.join(fold, "Resources")
    os.makedirs(res_dir, exist_ok=True)
    dst_img = os.path.join(res_dir, filename)
    shutil.copy2(src_img, dst_img)
    if tmp_clean and os.path.exists(tmp_clean):
        os.unlink(tmp_clean)
    print(f"[2/5] 图片已放入草稿: {dst_img}")

    nw = nh = None
    try:
        from PIL import Image
        with Image.open(dst_img) as im:
            nw, nh = im.size
        print(f"      尺寸: {nw}x{nh}")
    except Exception:
        pass

    new_path = f"{PLACEHOLDER}/Resources/{filename}"
    total = 0
    for p in draft_info_paths(fold):
        d = decrypt_json(p)
        n = 0
        for m in d.get("materials", {}).get("videos", []):
            if not isinstance(m, dict):
                continue
            old = m.get("path", "")
            if not isinstance(old, str) or "/Resources/" not in old:
                continue
            if not old.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if args.old and args.old not in old:
                continue
            m["path"] = new_path
            if nw and nh:
                m["width"], m["height"] = nw, nh
            n += 1
        if n:
            encrypt_json(p, d)
        total += n
        print(f"  · {os.path.relpath(p, fold)}: 替换 {n} 处图片引用")
    print(f"[3/5] 共替换 {total} 处引用（两份工程 JSON 均已同步）")
    if not total:
        print("  [提示] 未找到匹配的图片引用，可检查 --old 过滤条件")

    if not args.no_cover:
        make_cover(args.title or entry.get("draft_name"),
                   os.path.join(fold, "draft_cover.jpg"), base=dst_img)
        print("[4/5] 封面已用新图重生成")
    else:
        print("[4/5] --no-cover：保留原封面")

    print("[5/5] 完成")
    maybe_reopen(entry.get("draft_name"), not args.no_reopen, root)


# ---------------- 时长对齐（背景图 / BGM / 贴纸 / 标题 → 字幕+配音） ----------------

def track_end(tr):
    end = 0
    for s in tr.get("segments", []):
        tt = s.get("target_timerange") or {}
        end = max(end, int(tt.get("start") or 0) + int(tt.get("duration") or 0))
    return end


def content_track_indices(d):
    """找出字幕轨与配音轨（动态定位，禁止写死下标）。

    字幕轨 = 片段最多的 text 轨（顶部单段书名标题不会被误选）。
    配音轨 = 优先取引用 wav 旁白的 audio 轨，排除多段循环的 BGM mp3 轨；
             识别不到时退回「片段最多的 audio 轨」，兼容 TTS 分段配音草稿。

    2026-11-14 实测：《住小房子的女人》的配音是一整条外部旁白 wav（1 段），
    而 BGM 是 34 段 mp3。若一律按片段数选，会把 BGM 当基准（57 分钟），
    并把旁白轨拉长到 57 分钟，导出后半段全是静音 —— 必须先排除 BGM。
    """
    tracks = d.get("tracks", [])
    text_cand = [i for i, t in enumerate(tracks) if t.get("type") == "text"]
    ti = (max(text_cand, key=lambda i: len(tracks[i].get("segments", [])))
          if text_cand else None)

    paths = {}
    for arr in d.get("materials", {}).values():
        if isinstance(arr, list):
            for m in arr:
                if isinstance(m, dict) and m.get("id"):
                    paths[m["id"]] = str(m.get("path", ""))

    def first_path(i):
        for s in tracks[i].get("segments", [])[:3]:
            p = paths.get(s.get("material_id"), "")
            if p:
                return p.lower()
        return ""

    audio_cand = [i for i, t in enumerate(tracks) if t.get("type") == "audio"]
    if not audio_cand:
        return ti, None
    narr = [i for i in audio_cand
            if ".wav" in first_path(i) and "downloads" not in first_path(i)]
    if narr:
        te = track_end(tracks[ti]) if ti is not None else 0
        ai = min(narr, key=lambda i: abs(track_end(tracks[i]) - te))
    else:
        ai = max(audio_cand, key=lambda i: len(tracks[i].get("segments", [])))
    return ti, ai


def content_duration(d):
    ti, ai = content_track_indices(d)
    tracks = d.get("tracks", [])
    ends = [track_end(tracks[i]) for i in (ti, ai) if i is not None]
    if not ends:
        fail("工程里找不到字幕轨或配音轨，无法计算目标时长")
    return max(ends)


def _clone_material(d, old_id, new_id):
    """复制一份素材条目并换 id；找不到时返回 False 让调用方复用原 id。"""
    for _kind, arr in d.get("materials", {}).items():
        if not isinstance(arr, list):
            continue
        for m in arr:
            if isinstance(m, dict) and m.get("id") == old_id:
                cp = json.loads(json.dumps(m, ensure_ascii=False))
                cp["id"] = new_id
                arr.append(cp)
                return True
    return False


def _clone_segment(d, tmpl, start, length):
    """按模板片段造一个新片段，配套生成新的素材/关联素材 id。

    剪映每个片段都有独立 id、material_id 与 extra_material_refs；
    直接复用会造成 id 冲撞，打开时可能丢片段或报结构错误。
    """
    seg = json.loads(json.dumps(tmpl, ensure_ascii=False))
    seg["id"] = str(uuid.uuid4()).upper()
    tt = seg.setdefault("target_timerange", {})
    if start:
        tt["start"] = start
    else:
        tt.pop("start", None)
    tt["duration"] = length
    st = seg.get("source_timerange")
    if isinstance(st, dict):
        st.pop("start", None)
        st["duration"] = length

    new_mid = str(uuid.uuid4()).upper()
    if not _clone_material(d, tmpl.get("material_id"), new_mid):
        new_mid = tmpl.get("material_id")
    seg["material_id"] = new_mid

    refs = []
    for old in tmpl.get("extra_material_refs", []):
        nr = str(uuid.uuid4()).upper()
        refs.append(nr if _clone_material(d, old, nr) else old)
    if "extra_material_refs" in seg:
        seg["extra_material_refs"] = refs
    return seg


def _stretch_last(s, total):
    tt = s.setdefault("target_timerange", {})
    length = total - int(tt.get("start") or 0)
    if length <= 0:
        return False
    tt["duration"] = length
    st = s.get("source_timerange")
    if isinstance(st, dict) and st.get("duration"):
        st["duration"] = length
    return True


def _trim_track(tr, total):
    kept, removed = [], 0
    for s in tr.get("segments", []):
        tt = s.get("target_timerange") or {}
        st = int(tt.get("start") or 0)
        du = int(tt.get("duration") or 0)
        if st >= total:
            removed += 1
            continue
        if st + du > total:
            tt["duration"] = total - st
            src = s.get("source_timerange")
            if isinstance(src, dict) and src.get("duration"):
                src["duration"] = total - st
        kept.append(s)
    tr["segments"] = kept
    return removed


def fit_tracks(d, total, loop_bgm=True):
    """把铺底轨道对齐到 total，字幕轨与配音轨保持原样。

    时间单位微秒。单段图片/贴纸/标题 → 延长；多段 BGM 音频轨 → 按原循环
    单元继续复制到 total；超出 total 的片段 → 裁掉或裁短。
    """
    ti, ai = content_track_indices(d)
    keep = {i for i in (ti, ai) if i is not None}
    changes = []
    for idx, tr in enumerate(d.get("tracks", [])):
        if idx in keep:
            changes.append((idx, tr.get("type"), "基准轨（字幕/配音），保持不动", track_end(tr)))
            continue
        segs = tr.get("segments", [])
        if not segs:
            changes.append((idx, tr.get("type"), "空轨，跳过", 0))
            continue
        end = track_end(tr)
        if end > total:
            n = _trim_track(tr, total)
            changes.append((idx, tr.get("type"), f"裁短至目标（删除 {n} 段）", track_end(tr)))
            continue
        if end == total:
            changes.append((idx, tr.get("type"), "时长已对齐", end))
            continue
        if len(segs) == 1:
            _stretch_last(segs[0], total)
            changes.append((idx, tr.get("type"), f"单段延长 {end} → {total}", track_end(tr)))
        elif tr.get("type") == "audio" and loop_bgm:
            full = [s for s in segs
                    if (s.get("target_timerange") or {}).get("duration")
                    and (s.get("source_timerange") or {}).get("duration")
                    == (s.get("target_timerange") or {}).get("duration")]
            tmpl = max(full or segs,
                       key=lambda s: (s.get("target_timerange") or {}).get("duration", 0))
            unit = int((tmpl.get("target_timerange") or {}).get("duration") or 0)
            if unit <= 0:
                _stretch_last(segs[-1], total)
                changes.append((idx, tr.get("type"), "无法识别循环单元，延长末段", track_end(tr)))
                continue
            cur, added = end, 0
            while cur < total:
                length = min(unit, total - cur)
                segs.append(_clone_segment(d, tmpl, cur, length))
                cur += length
                added += 1
            changes.append((idx, tr.get("type"), f"按 {unit} 循环补齐 +{added} 段 → {total}",
                            track_end(tr)))
        else:
            _stretch_last(segs[-1], total)
            changes.append((idx, tr.get("type"), f"延长末段 {end} → {total}", track_end(tr)))
    d["duration"] = total
    return changes


def cmd_fit(args):
    root = resolve_root(args.root)
    if not args.dry_run:
        auto_quit(args.force, args.no_quit)
    data = load_index(root)
    _idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    if not os.path.isdir(fold):
        fail(f"草稿目录不存在: {fold}")

    paths = draft_info_paths(fold)
    if not paths:
        fail("找不到任何 draft_info.json")
    probe = decrypt_json(paths[0])
    total = int(args.target) if args.target else content_duration(probe)
    ti, ai = content_track_indices(probe)
    print(f"目标总时长: {total}  ({total / 1e6:.2f} 秒 / {total / 6e7:.2f} 分)")
    print(f"依据: 字幕轨 track[{ti}] 与配音轨 track[{ai}] 的最晚结束时间"
          "（BGM 轨已排除，不参与基准）")
    print()

    # 以时间线副本为基准（剪映以它为准并回写根目录），**同一份数据写入两处**。
    # 若两份各自 fit_tracks()，新增 BGM 段会各自生成随机 uuid，导致
    # segment.id / material_id / beats / speeds 在两份里对不上（2026-11-15 实测）。
    base_path = next((p for p in paths if os.sep + "Timelines" + os.sep in p), paths[0])
    d = decrypt_json(base_path)
    changes = fit_tracks(d, total, loop_bgm=not args.no_bgm_loop)
    print("--- 两份工程 JSON（同一份数据写入，BGM 段 id 一致）---")
    for idx, tp, act, end in changes:
        print(f"  track[{idx}] {str(tp):<8} {act:<42} end={end}")
    if not args.dry_run:
        for p in paths:
            encrypt_json(p, d)

    if not args.dry_run:
        mp = os.path.join(fold, "draft_meta_info.json")
        if os.path.isfile(mp):
            m = decrypt_json(mp)
            if m.get("tm_duration") != total:
                m["tm_duration"] = total
                encrypt_json(mp, m)
                print("  · 内层 meta tm_duration 已同步")
        i, e = find_entry(data, args.source)
        if e and "tm_duration" in e and e["tm_duration"] != total:
            e["tm_duration"] = total
            data["all_draft_store"][i] = e
            save_index(root, data)
            print("  · 外层索引 tm_duration 已同步")
        print("[完成] 两份工程 JSON 已写入")
    else:
        print("[dry-run] 仅预览，未写入任何文件")
    if not args.dry_run:
        maybe_reopen(entry.get("draft_name"), not args.no_reopen, root)


# ---------------- 字幕样式对齐（以已调好的草稿为参照） ----------------

SUBTITLE_MATERIAL_KEYS = (
    "line_spacing", "shadow_alpha", "shadow_smoothing", "shadow_distance",
    "shadow_point", "shadow_angle", "border_color", "border_width",
    "text_color", "font_path", "initial_scale", "background_color",
)
SUBTITLE_RUN_KEYS = ("fill", "font", "size", "strokes", "useLetterColor")

# 系列硬约束（用户 2026-11-14 明确）：字幕每行约 23 字，文本框有最大宽度，
# 否则字幕块向左溢出会遮住画面左侧的光盘/唱片图案。
SERIES_MAX_CHARS = 23
BASE_CHARS_PER_LINE = 22          # 剪映 TTS 生成字幕时每行的实测字数
BASE_FIXED_WIDTH = 1105.048656463623   # 对应 22 字的 fixed_width


def subtitle_track(d):
    """动态定位字幕轨：type=text 且片段多于 1，取片段最多的一条。

    顶部书名标题只有 1 段；用户做完 TTS 后字幕轨下标会变，不能写死。
    """
    cand = [t for t in d.get("tracks", [])
            if t.get("type") == "text" and len(t.get("segments", [])) > 1]
    if not cand:
        fail("找不到字幕轨（type=text 且片段数 > 1）")
    return max(cand, key=lambda t: len(t["segments"]))


def read_subtitle_style(d):
    tr = subtitle_track(d)
    seg = tr["segments"][0]
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    m = texts.get(seg.get("material_id"), {})
    clip = seg.get("clip") or {}
    canvas = d.get("canvas_config") or {}
    style = {
        "scale": json.loads(json.dumps(clip.get("scale", {}), ensure_ascii=False)),
        "transform": json.loads(json.dumps(clip.get("transform", {}), ensure_ascii=False)),
        "material": {}, "run": {},
        "canvas": (canvas.get("width", 6600), canvas.get("height", 3712)),
    }
    for k in SUBTITLE_MATERIAL_KEYS:
        if k in m:
            style["material"][k] = json.loads(json.dumps(m[k], ensure_ascii=False))
    try:
        cj = json.loads(m.get("content", "{}"))
        st = (cj.get("styles") or [{}])[0]
        for k in SUBTITLE_RUN_KEYS:
            if k in st:
                style["run"][k] = json.loads(json.dumps(st[k], ensure_ascii=False))
    except (ValueError, TypeError, AttributeError):
        pass
    return style


def apply_subtitle_style(d, style, size=None):
    """把参照样式套到目标字幕轨的全部片段。

    只改样式字段；content 里的 text、words/current_words、text_to_audio_ids
    等业务字段一律不动，避免破坏字幕文本与配音的关联。
    """
    tr = subtitle_track(d)
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    n = 0
    for s in tr.get("segments", []):
        clip = s.setdefault("clip", {})
        if style.get("scale"):
            clip["scale"] = json.loads(json.dumps(style["scale"], ensure_ascii=False))
        if style.get("transform"):
            clip["transform"] = json.loads(json.dumps(style["transform"], ensure_ascii=False))
        m = texts.get(s.get("material_id"))
        if not isinstance(m, dict):
            continue
        for k, v in style["material"].items():
            m[k] = json.loads(json.dumps(v, ensure_ascii=False))
        # 导入型字幕（非 TTS）会多带一个 font_size 字段，剪映可能优先读它。
        # 参照草稿没有此字段，这里让它与 styles[].size 对齐，否则字号设置不生效。
        if "font_size" in m:
            target = float(size) if size is not None else style["run"].get("size")
            if isinstance(target, (int, float)):
                m["font_size"] = float(target)
        try:
            cj = json.loads(m.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        if not isinstance(cj, dict):
            continue
        txt = str(cj.get("text", ""))
        styles = cj.get("styles") or []
        if not styles:
            styles = [{"range": [0, len(txt)]}]
            cj["styles"] = styles
        for st in styles:
            if not isinstance(st, dict):
                continue
            for k, v in style["run"].items():
                if k == "size" and size is not None:
                    continue
                st[k] = json.loads(json.dumps(v, ensure_ascii=False))
            if size is not None:
                st["size"] = float(size)
            if len(styles) == 1:
                st["range"] = [0, len(txt)]
        m["content"] = json.dumps(cj, ensure_ascii=False)
        n += 1
    return n


# ---------------- 字幕行宽 / 折行控制 ----------------

# 系列字幕规则（2026-11-16 更新）：自动生成的字幕「完全去掉硬换行，
# 一整句一行」，**保留标点**。此前每行≤23字硬换行会把「鸡尾酒」劈成
# 「鸡\n尾酒」，被用户判定为无意义换行；11-15 一度连标点一起去掉，
# 11-16 用户反馈字幕不该没有标点，故恢复标点。flat 默认只拍平换行，
# 保留标点；仅在显式 --strip-punct 时才去标点。flat 只对无逐字绑定的
# 导入型字幕生效（这类字幕配音按整段 wav + segment 时间轴对齐，
# 改标点/换行不影响配音）；有逐字绑定的 TTS 原生字幕自动跳过文本改动。
PUNCT_EXTRA = set("·～—…￥％＃＆＊＋＝／＼｜＜＞｛｝［］「」『』〈〉《》『』")


def strip_subtitle_punct(text):
    """去掉字幕文本里的所有标点符号，返回 (新文本, 是否变化)。

    用 Unicode 标点类别（P*）覆盖中英文全部标点，另加 PUNCT_EXTRA 兜底
    全角符号。保留汉字、字母、数字、空白与 emoji。
    """
    out = []
    changed = False
    for ch in text:
        if unicodedata.category(ch).startswith("P") or ch in PUNCT_EXTRA:
            changed = True
            continue
        out.append(ch)
    return "".join(out), changed


def flatten_subtitle(text, allow_punct=True):
    """一整句一行：去掉所有硬换行（中文直接连接，不留空格）+ 可选去标点。

    返回 (新文本, 是否变化)。allow_punct=False 时只拍平换行、保留标点
    （用于有逐字绑定的字幕，避免改动字符数破坏配音下标）。
    """
    no_break = text.replace("\r", "").replace("\n", "")
    if allow_punct:
        out, _ = strip_subtitle_punct(no_break)
    else:
        out = no_break
    return out, out != text


def reduce_linebreaks(text, max_lines):
    """把一段字幕文本压缩到最多 max_lines 行。

    做法是保留位置最均匀的若干个**原有**换行，其余换行替换成空格：
    - 不改动任何文字内容，也不新造断句，语义与配音完全对得上；
    - 字符总数、字符下标都不变，因此 styles[].range / text_to_audio_ids /
      group_id 等全部无需改动，属于零风险改动。
    """
    if max_lines < 1 or "\n" not in text:
        return text, False
    parts = text.split("\n")
    if len(parts) <= max_lines:
        return text, False

    # 断点编号 b = 1..len(parts)-1，位于 parts[b-1] 与 parts[b] 之间
    break_pos = {}
    acc = 0
    for b in range(1, len(parts)):
        acc += len(parts[b - 1]) + 1
        break_pos[b] = acc - 1
    total = len(text)
    keep = set()
    for k in range(1, max_lines):
        target = total * k / max_lines
        keep.add(min(break_pos, key=lambda b: (abs(break_pos[b] - target), b)))

    out = parts[0]
    for b in range(1, len(parts)):
        out += ("\n" if b in keep else " ") + parts[b]
    return out, out != text


def rewrap_by_chars(text, max_chars, allow_insert=False):
    """按「每行最多 max_chars 字」重新折行，保证文本框不会宽到遮住左侧光盘。

    默认（TTS 字幕）：只在**空格 / 原有断点**处断开，把该空格替换成 \\n，
    字符总数与字符下标都不变，styles[].range / 逐字配音关联零风险。

    allow_insert=True（导入型字幕，无 words / 配音下标）：中文长句常常整段
    没有空格，此时在字数上限处**插入** \\n。字符数会增加，调用方
    apply_subtitle_layout 会把 styles[].range 同步到新长度；这类字幕没有
    逐字关联，故不会破坏配音。启用前必须用 subtitle_has_word_binding 判断。
    """
    if max_chars < 1:
        return text, False
    flat = text.replace("\n", " ")
    n = len(flat)
    orig_breaks = {i for i, c in enumerate(text) if c == "\n"}
    breaks = set()      # 把该位置的空格替换成 \n（字符数不变）
    inserts = set()     # 在该字符前插入 \n（字符数 +1）
    start = 0
    for _ in range(60):
        if n - start <= max_chars:
            break
        hi = min(start + max_chars, n - 1)
        cand = [i for i in range(start + 1, hi + 1) if flat[i] == " "]
        good = [i for i in cand if i - start >= max_chars * 0.6]
        if good:
            breaks.add(max(good))
            start = max(good) + 1
            continue
        orig = [i for i in orig_breaks if start < i <= hi]
        if orig:
            breaks.add(max(orig))
            start = max(orig) + 1
            continue
        if cand:
            breaks.add(max(cand))
            start = max(cand) + 1
            continue
        if allow_insert:
            b = start + max_chars
            inserts.add(b)
            start = b                   # 插入后该字符成为新行首
            continue
        break                           # 无法安全断开，剩余保持一整行
    out = []
    for i, c in enumerate(flat):
        if i in inserts:
            out.append("\n")
        out.append("\n" if i in breaks else c)
    nt = "".join(out)
    return nt, nt != text


def subtitle_has_word_binding(d):
    """字幕是否带逐字 words / 配音下标关联（TTS 字幕为 True）。

    只有确认没有关联时，才允许折行时插入新的 \n（字符数变化）。
    """
    tr = subtitle_track(d)
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    for s in tr.get("segments", []):
        m = texts.get(s.get("material_id"), {})
        if m.get("words") or m.get("current_words") or m.get("text_to_audio_ids"):
            return True
    return False


def subtitle_widths(d):
    from collections import Counter
    tr = subtitle_track(d)
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    widths = Counter()
    for s in tr.get("segments", []):
        m = texts.get(s.get("material_id"), {})
        if "fixed_width" in m:
            try:
                widths[round(float(m["fixed_width"]), 4)] += 1
            except (TypeError, ValueError):
                pass
    return widths


def _wrap_text(text, plan):
    if plan["mode"] == "flat":
        return flatten_subtitle(text, allow_punct=plan.get("allow_punct", True))
    if plan["mode"] == "chars":
        return rewrap_by_chars(text, plan["max_chars"],
                               allow_insert=plan.get("allow_insert", False))
    return reduce_linebreaks(text, plan["max_lines"])


def plan_subtitle_layout(d, mode, max_lines, max_chars,
                         width_mode, width_value, strip_punct=False):
    """统计折行改动，并决定新的 fixed_width（保证两份工程 JSON 用同一个值）。

    mode="flat" 是系列默认（2026-11-16 更新）：完全去掉硬换行、一整句一行，
    **保留标点**，文本框宽度保持不变（仍防遮挡光盘）；仅 strip_punct=True
    时才去标点。mode="chars" 是旧规则：按每行字数上限折行，宽度设成对应上限。
    """
    from collections import Counter
    tr = subtitle_track(d)
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    has_binding = subtitle_has_word_binding(d)
    allow_insert = (mode == "chars" and not has_binding)
    allow_punct = (mode == "flat" and not has_binding and strip_punct)
    probe = {"mode": mode, "max_lines": max_lines, "max_chars": max_chars,
             "allow_insert": allow_insert, "allow_punct": allow_punct}
    before, after = Counter(), Counter()
    bmax = amax = 0
    changed = 0
    for s in tr.get("segments", []):
        m = texts.get(s.get("material_id"), {})
        try:
            tx = str(json.loads(m.get("content", "{}")).get("text", ""))
        except (ValueError, TypeError, AttributeError):
            continue
        bl = tx.split("\n")
        before[len(bl)] += 1
        bmax = max(bmax, *[len(r) for r in bl])
        nt, hit = _wrap_text(tx, probe)
        al = nt.split("\n")
        after[len(al)] += 1
        amax = max(amax, *[len(r) for r in al])
        changed += int(hit)

    wd = subtitle_widths(d)
    old_width = wd.most_common(1)[0][0] if wd else None
    if width_mode == "auto_width":
        new_width = "auto"                      # 删除 fixed_width，回到自动宽度
    elif width_mode == "fixed":
        new_width = float(width_value)
    elif width_mode == "keep":
        new_width = None                        # 完全不动
    elif mode == "flat":
        new_width = None                        # flat 一整句一行：宽度保持不变，仍防遮挡
    elif mode == "chars":
        # 22 字 ≈ 1105 是剪映 TTS 生成字幕时的实测宽度，按字数线性换算
        new_width = round(BASE_FIXED_WIDTH * max_chars / BASE_CHARS_PER_LINE, 4)
    else:
        new_width = (round(old_width * (amax / bmax) * 1.05, 4)
                     if old_width is not None and bmax > 0 else None)
    return {
        "mode": mode, "max_lines": max_lines, "max_chars": max_chars,
        "before": before, "after": after, "bmax": bmax, "amax": amax,
        "changed": changed, "old_width": old_width, "new_width": new_width,
        "width_mode": width_mode, "allow_insert": allow_insert,
        "allow_punct": allow_punct,
    }


def apply_subtitle_layout(d, plan):
    tr = subtitle_track(d)
    texts = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    n = 0
    for s in tr.get("segments", []):
        m = texts.get(s.get("material_id"))
        if not isinstance(m, dict):
            continue
        try:
            cj = json.loads(m.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        if not isinstance(cj, dict):
            continue
        tx = str(cj.get("text", ""))
        nt, hit = _wrap_text(tx, plan)
        if hit:
            cj["text"] = nt
            for st in cj.get("styles", []) or []:
                if isinstance(st, dict) and len(st.get("range", [])) == 2:
                    st["range"] = [0, len(nt)]
            m["content"] = json.dumps(cj, ensure_ascii=False)
            n += 1
        nw = plan["new_width"]
        if nw == "auto":
            m.pop("fixed_width", None)
        elif isinstance(nw, (int, float)):
            m["fixed_width"] = float(nw)
    return n


def cmd_fixsub(args):
    root = resolve_root(args.root)
    if not args.dry_run:
        auto_quit(args.force, args.no_quit)
    data = load_index(root)
    _i, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到目标草稿: {args.source}")
    _j, ref = find_entry(data, args.from_draft)
    if ref is None:
        fail(f"未找到参照草稿: {args.from_draft}")
    fold = entry.get("draft_fold_path", "")
    ref_fold = ref.get("draft_fold_path", "")
    if not os.path.isdir(fold) or not os.path.isdir(ref_fold):
        fail("目标或参照草稿目录不存在")

    style = read_subtitle_style(decrypt_json(os.path.join(ref_fold, "draft_info.json")))
    w, h = style["canvas"]
    if args.scale is not None:
        style["scale"] = {"x": args.scale, "y": args.scale}
    if args.x is not None or args.y is not None:
        base = dict(style["transform"] or {"x": 0.0, "y": 0.0})
        if args.x is not None:
            base["x"] = args.x / w
        if args.y is not None:
            base["y"] = args.y / h
        style["transform"] = base
    if args.line_spacing is not None:
        style["material"]["line_spacing"] = args.line_spacing

    sc = style["scale"] or {}
    tr = style["transform"] or {}
    print(f"参照草稿: {ref.get('draft_name')}  | 画布 {w}x{h}")
    print(f"目标样式: 缩放 {sc.get('x')} / 位置 X={round(tr.get('x', 0) * w)} "
          f"Y={round(tr.get('y', 0) * h)} / 字号 "
          f"{args.size if args.size is not None else style['run'].get('size')} / "
          f"行间距 {style['material'].get('line_spacing')}")
    print(f"同时补齐 {len(style['material'])} 个 material 字段、"
          f"{len(style['run'])} 个 styles 字段\n")

    paths = draft_info_paths(fold)
    max_lines = getattr(args, "max_lines", 0) or 0
    max_chars = getattr(args, "max_chars", 0) or 0
    if max_lines > 0:
        layout_mode = "lines"          # 显式指定最大行数时覆盖系列默认
        if max_chars > 0:
            print("  [提示] --max-lines 与 --max-chars 同时给出，按最大行数执行")
    elif max_chars > 0:
        layout_mode = "chars"          # 显式指定按字数折行（旧规则）
    elif getattr(args, "no_flat", False):
        layout_mode = None             # 完全不碰文本（保留原换行与标点）
    else:
        layout_mode = "flat"           # 默认：去硬换行、保留标点，一整句一行

    plan = None
    if layout_mode:
        wm = ("fixed" if getattr(args, "width", None) is not None else
              "auto_width" if getattr(args, "auto_width", False) else
              "keep" if getattr(args, "keep_width", False) else "scale")
        plan = plan_subtitle_layout(decrypt_json(paths[0]), layout_mode,
                                    max_lines, max_chars, wm,
                                    getattr(args, "width", None),
                                    strip_punct=getattr(args, "strip_punct", False))
        bl = ", ".join(f"{k}行×{v}段" for k, v in sorted(plan["before"].items()))
        al = ", ".join(f"{k}行×{v}段" for k, v in sorted(plan["after"].items()))
        title = ("最多 %d 行" % max_lines if layout_mode == "lines" else
                 f"每行最多 {max_chars} 字（旧折行规则）" if layout_mode == "chars" else
                 "一整句一行 + 保留标点（系列默认）" if not plan.get("allow_punct") else
                 "一整句一行 + 去标点（--strip-punct）")
        print(f"折行控制: {title} / 需改 {plan['changed']} 段")
        print(f"  行数分布  改前 {bl}  →  改后 {al}")
        print(f"  最长单行  {plan['bmax']} 字  →  {plan['amax']} 字")
        nw = plan["new_width"]
        desc = ("删除(自动宽度)" if nw == "auto" else
                "保持不变" if nw is None else f"{nw}")
        print(f"  文本框宽度 fixed_width: {plan['old_width']}  →  {desc}")
        if layout_mode == "flat":
            if plan.get("allow_punct"):
                print("  字幕绑定: 无逐字 words / 配音下标 → 去硬换行、去标点"
                "（显式 --strip-punct），一整句一行；配音按整段对齐不受影响\n")
            else:
                print("  字幕绑定: 无逐字 words / 配音下标 → 只去硬换行、保留标点，"
                      "一整句一行；配音按整段对齐不受影响\n")
        elif plan.get("allow_insert"):
            print("  字幕绑定: 无逐字 words / 配音下标 → 中文长句在字数上限处插入换行，"
                  "文字不变、styles.range 已同步\n")
        else:
            print("  字幕绑定: 检测到逐字关联 → 只在空格处替换成换行，"
                  "文字与字符总数不变，配音关联不受影响\n")

    for p in paths:
        d = decrypt_json(p)
        n = apply_subtitle_style(d, style, size=args.size)
        extra = apply_subtitle_layout(d, plan) if plan is not None else 0
        msg = f"已套用 {n} 段字幕样式"
        if plan is not None:
            msg += f"，重排 {extra} 段折行"
        print(f"  · {os.path.relpath(p, fold)}: {msg}")
        if not args.dry_run:
            encrypt_json(p, d)
    if args.dry_run:
        print("[dry-run] 仅预览，未写入任何文件")
    else:
        print("[完成] 两份工程 JSON 已写入")
        maybe_reopen(entry.get("draft_name"), not args.no_reopen, root)


def cmd_fixcover(args):
    """重做封面并校准草稿箱缩略图、素材显示名。

    剪映草稿箱实际显示 draft_local_cover.jpg（320x180），只改大封面时
    剪映启动会用旧缩略图把大封面同步回旧书封面（2026-11-14 实测）。
    """
    root = resolve_root(args.root)
    data = load_index(root)
    _i, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    if not os.path.isdir(fold):
        fail(f"草稿目录不存在: {fold}")
    title = args.title or entry.get("draft_name", "")
    base = args.base or current_bg(fold)
    out = os.path.join(fold, "draft_cover.jpg")
    print(f"重做封面: 书名={title!r}  底图={base}")
    if args.dry_run:
        print("[dry-run] 仅预览，未写盘、未退出剪映")
        return
    auto_quit(args.force, args.no_quit)
    make_cover(title, out, base)

    for p in draft_info_paths(fold):
        d = decrypt_json(p)
        n = 0
        for m in d.get("materials", {}).get("videos", []):
            if not isinstance(m, dict):
                continue
            raw = str(m.get("path", ""))
            if "/Resources/" not in raw:
                continue
            fn = os.path.basename(raw)
            if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            for k in ("material_name", "name", "file_name"):
                if k in m:
                    m[k] = fn
            m.setdefault("material_name", fn)
            n += 1
        if n:
            encrypt_json(p, d)
            print(f"  · {os.path.relpath(p, fold)}: 同步 {n} 个素材显示名")
    maybe_reopen(entry.get("draft_name"), not args.no_reopen, root)


def cmd_materials(args):
    root = resolve_root(args.root)
    data = load_index(root)
    _idx, entry = find_entry(data, args.source)
    if entry is None:
        fail(f"未找到草稿: {args.source}")
    fold = entry.get("draft_fold_path", "")
    if not os.path.isdir(fold):
        fail(f"草稿目录不存在: {fold}")

    info = os.path.join(fold, "draft_info.json")
    if not os.path.isfile(info):
        fail(f"找不到 draft_info.json: {info}")
    d = decrypt_json(info)
    raw = set()
    for kind, arr in d.get("materials", {}).items():
        if not isinstance(arr, list):
            continue
        for m in arr:
            if not isinstance(m, dict):
                continue
            for k in ("path", "file_Path", "filePath", "local_path"):
                v = m.get(k)
                if isinstance(v, str) and v.strip():
                    raw.add(v.strip())
                    break

    print(f"草稿 {entry.get('draft_name')} 引用的素材（{len(raw)} 条）:")
    for p in sorted(raw):
        real = p.replace(PLACEHOLDER + "/", fold + "/").replace(PLACEHOLDER, fold)
        mark = "" if os.path.exists(real) else "  [缺失]"
        shown = real if real != p else p
        if real != p:
            shown = f"{p}  →  {real}"
        print(f"  {shown}{mark}")
    if not raw:
        print("  未解析到素材路径（草稿可能为空工程）")


# ---------------- 链接媒体修复（2026-11-15 实测） ----------------
# 剪映弹「链接媒体丢失」时，用户看到的 materials.audios[].path 可能完全正确、
# 文件也真实存在。真正被校验的是加密 draft_meta_info.json 里的
# draft_materials[type=0].value[].file_Path —— 剪映自己的「链接媒体登记表」。
# 用 copy 生成新草稿后只改工程 path、没同步这张表，表里要么仍记着上一本书的
# wav，要么压根没有本书 wav，于是两边对不上，弹媒体丢失。

_DEFAULT_LINK_ENTRY = {
    "ai_group_type": "", "create_time": 0, "duration": 0, "enter_from": 0,
    "extra_info": "", "file_Path": "", "height": 0, "id": "",
    "import_time": 0, "import_time_ms": 0, "item_source": 1, "md5": "",
    "metetype": "music",
    "roughcut_time_range": {"duration": 0, "start": 0},
    "sub_time_range": {"duration": -1, "start": -1},
    "type": 0, "width": 0,
}


def _link_entry(mid, fp, dur, name, template=None):
    import copy
    v = copy.deepcopy(template if isinstance(template, dict) else _DEFAULT_LINK_ENTRY)
    v["id"] = mid
    v["file_Path"] = fp
    v["extra_info"] = name
    v["duration"] = dur
    v["metetype"] = "music"
    v["type"] = 0
    rtr = v.get("roughcut_time_range")
    if isinstance(rtr, dict):
        rtr["duration"] = dur
        rtr["start"] = 0
    return v


def fix_media_one(fold, dry_run=False):
    """把外部绝对路径音频搬进草稿内，并重建加密 meta 的链接媒体登记表。"""
    paths = draft_info_paths(fold)
    base = next((p for p in paths if os.sep + "Timelines" + os.sep in p), paths[0])
    d = decrypt_json(base)
    meta_path = os.path.join(fold, "draft_meta_info.json")
    meta = decrypt_json(meta_path) if os.path.isfile(meta_path) else None

    audios = d.get("materials", {}).get("audios", [])
    groups = {}   # 真实绝对路径 -> [素材条目]
    for m in audios:
        p = m.get("path")
        if not isinstance(p, str) or not p.strip() or "/Cache/" in p:
            continue
        real = p.replace(PLACEHOLDER + "/", fold + "/").replace(PLACEHOLDER, fold)
        groups.setdefault(real, []).append(m)

    g0, old_reg = None, []
    if isinstance(meta, dict):
        for g in (meta.get("draft_materials") or []):
            if isinstance(g, dict) and g.get("type") == 0:
                g0, old_reg = g, (g.get("value") or [])
                break
    tpl_by_path = {}
    for v in old_reg:
        if isinstance(v, dict):
            tpl_by_path.setdefault(v.get("file_Path", ""), v)

    media_dir = os.path.join(fold, "Resources", "media")
    changes, new_reg = [], []
    for real, mats in groups.items():
        name = os.path.basename(real)
        is_external = real.startswith("/") and not real.startswith(fold + os.sep)
        if not os.path.isfile(real):
            changes.append(f"  [跳过] 源文件不存在: {real}")
            continue
        if is_external:
            dst = os.path.join(media_dir, name)
            if not dry_run:
                os.makedirs(media_dir, exist_ok=True)
                if not (os.path.isfile(dst) and
                        os.path.getsize(dst) == os.path.getsize(real)):
                    shutil.copy2(real, dst)
            # 工程 path 与登记表 file_Path 必须指向同一字符串，否则剪映仍判丢失
            reg_path = dst
        else:
            dst = real
            reg_path = mats[0].get("path", real)

        mid, local_id = str(uuid.uuid4()), str(uuid.uuid4())
        for m in mats:
            if is_external:
                m["path"] = reg_path
            # 只更新已存在的媒体库 ID，不给 TTS 类素材凭空加字段
            for k, val in (("music_id", mid), ("resource_id", mid),
                           ("local_material_id", local_id)):
                if k in m:
                    m[k] = val
            if "name" in m:
                m["name"] = name

        m0 = mats[0]
        dur = int(m0.get("duration") or 0)
        tpl = tpl_by_path.get(real) or (old_reg[0] if old_reg else None)
        new_reg.append(_link_entry(m0.get("id"), reg_path, dur, name, tpl))
        new_reg.append(_link_entry(local_id, reg_path, dur, name, tpl))
        changes.append(
            f"  {name}: {'外部→草稿内, ' if is_external else ''}"
            f"{len(mats)} 段素材换新 ID, 登记表 2 条, duration={dur}"
        )

    if dry_run:
        print(f"\n=== {os.path.basename(fold)} 链接媒体诊断（预览）===")
        print("  登记表原有 %d 条: %s" % (
            len(old_reg),
            ", ".join(os.path.basename(str(v.get("file_Path", "")))
                      for v in old_reg) or "（空）"))
        print("\n".join(changes) if changes else "  无需改动")
        return

    if g0 is None:
        if not isinstance(meta, dict):
            meta = {}
        meta.setdefault("draft_materials", [])
        g0 = {"type": 0, "value": []}
        meta["draft_materials"].insert(0, g0)
    g0["value"] = new_reg

    for p in paths:
        encrypt_json(p, d)
    encrypt_json(meta_path, meta)
    print(f"\n=== {os.path.basename(fold)} ===")
    print("\n".join(changes))
    print(f"  已同步 {len(paths)} 份 draft_info.json + "
          f"draft_meta_info.json 登记表 {len(new_reg)} 条")


def cmd_fixmedia(args):
    root = resolve_root(args.root)
    names = args.source
    if not names:
        fail("请用 -s 指定至少一个草稿名（可重复传 -s）")
    if not args.dry_run:
        auto_quit(args.force, args.no_quit)
    for n in names:
        data = load_index(root)
        _idx, entry = find_entry(data, n)
        if entry is None:
            print(f"[跳过] 索引里找不到草稿: {n}")
            continue
        fold = entry.get("draft_fold_path", "")
        if not os.path.isdir(fold):
            print(f"[跳过] 草稿目录不存在: {fold}")
            continue
        try:
            fix_media_one(fold, args.dry_run)
        except Exception as e:
            print(f"[失败] {n}: {e}")
    if not args.dry_run and not args.no_reopen:
        maybe_reopen(names[0], True, root)


def cmd_reopen(args):
    root = resolve_root(args.root)
    name = args.draft or "小王子"
    print(f"重开剪映并置顶: {name}")
    maybe_reopen(name, True, root)


# 文章仓库根目录：可用 BOOK_ROOT 覆盖（换机器/换路径时设置），否则用默认位置
ARTICLE_ROOT = (
    os.environ.get("BOOK_ROOT")
    or os.path.expanduser("~/Product/WeChatArticle/十分钟读完一本书")
)
COVER_SCRIPTS_DIR_NAME = "scripts"   # 用户 2026-11-14 21:02 把两个封面脚本移进此子目录
COVER_SCRIPTS = ("手机封片图片.py", "横版电脑封面.py")


def cover_script_path(article_root, script):
    """封面脚本优先在 <文章根>/scripts/ 找，兼容旧的根目录位置。

    脚本与模板图（生成横版图片_原.png / 生成竖版背景_临时.png）必须在同一目录，
    因为脚本用 __file__ 所在目录拼模板路径；不要只搬脚本不搬模板图。
    """
    moved = os.path.join(article_root, COVER_SCRIPTS_DIR_NAME, script)
    if os.path.isfile(moved):
        return moved
    legacy = os.path.join(article_root, script)
    if os.path.isfile(legacy):
        return legacy
    raise RuntimeError(
        f"找不到封面脚本 {script}（已查 {moved} 与 {legacy}）；"
        "确认脚本与模板图都在 <文章根>/scripts/ 下")


def locate_markdown_dir(book, article_root):
    """按书名找到该文章的 markdown 所在目录（封面图必须与 .md 同目录）。

    规则：目录名含书名、目录内至少有 1 个 .md；优先取文件名也含书名的 md，
    多个候选时按 md 修改时间取最新。assets / scripts / .git 不参与搜索。
    """
    skip = {"assets", "scripts", ".git", "参考", "__pycache__"}
    cands = []
    for dp, dirs, files in os.walk(article_root):
        dirs[:] = [x for x in dirs if x not in skip and not x.startswith(".")]
        if book not in os.path.basename(dp):
            continue
        mds = [f for f in files if f.lower().endswith(".md")]
        if not mds:
            continue
        pref = [f for f in mds if book in f] or mds
        best = max(pref, key=lambda f: os.path.getmtime(os.path.join(dp, f)))
        cands.append((os.path.getmtime(os.path.join(dp, best)), dp, best))
    if not cands:
        raise RuntimeError(
            f"在 {article_root} 下找不到书名「{book}」对应的 markdown 目录；"
            "请用 --md 明确指定 .md 文件或其所在目录")
    cands.sort(reverse=True)
    return cands[0][1], cands[0][2]


def cmd_covers(args):
    """收尾步骤：调用文章仓库里的两个脚本，生成手机竖版 + 电脑横版封面。

    用户 2026-11-14 明确：以后每本书处理完都必须执行，且两张图片
    必须落在 markdown 同文件夹。此命令不碰剪映、不改草稿。
    """
    root = os.path.abspath(args.article_root or ARTICLE_ROOT)
    book = (args.source or "").strip().strip("《》").strip()
    if not book:
        raise RuntimeError("请用 -s 指定书名")

    if args.md:
        target = os.path.abspath(args.md)
        if os.path.isdir(target):
            folder = target
            mds = sorted(f for f in os.listdir(folder) if f.lower().endswith(".md"))
            md_path = os.path.join(folder, mds[0]) if mds else "(未找到 md)"
        elif os.path.isfile(target):
            folder, md_path = os.path.dirname(target), target
        else:
            raise RuntimeError("--md 路径不存在: " + target)
    else:
        folder, md_name = locate_markdown_dir(book, root)
        md_path = os.path.join(folder, md_name)

    print(f"书名: {book}")
    print(f"markdown: {md_path}")
    print(f"输出目录（同 md）: {folder}\n")

    expected = {
        COVER_SCRIPTS[0]: f"{book}_封面.png",
        COVER_SCRIPTS[1]: f"{book}.png",
    }
    for script in COVER_SCRIPTS:
        sp = cover_script_path(root, script)
        print(f"  脚本: {sp}")
        cmd = [sys.executable, sp, book, args.author or "", folder]
        if args.dry_run:
            print("  [预览] " + " ".join(cmd))
            continue
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout.strip())
            print(r.stderr.strip(), file=sys.stderr)
            raise RuntimeError(f"{script} 执行失败 (code={r.returncode})")
        for line in r.stdout.strip().splitlines():
            if line.startswith("[完成]") or line.startswith("[提示]"):
                print("  " + line)

    if args.dry_run:
        print("\n预览模式，未写盘。")
        return
    print("\n校验:")
    ok = True
    for script, name in expected.items():
        p = os.path.join(folder, name)
        exists = os.path.isfile(p)
        ok &= exists
        print(f"  {'✅' if exists else '❌'} {name}"
              f"{'  ' + str(os.path.getsize(p)) + ' bytes' if exists else ''}")
    if not ok:
        raise RuntimeError("封面输出不完整")
    print("  两张封面均与 markdown 同目录。")


def add_common(p):
    p.add_argument("--no-reopen", action="store_true",
                   help="完成后不自动重开剪映")
    p.add_argument("--no-quit", action="store_true",
                   help="假定剪映已退出，跳过自动退出")
    p.add_argument("--force", action="store_true",
                   help="跳过自动退出直接执行（仅在确认剪映已退出时使用）")


def main():
    ap = argparse.ArgumentParser(description="剪映专业版(macOS)草稿管理 · WorkBuddy 版")
    ap.add_argument("--root", help="草稿根目录，默认 ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出草稿")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("copy", help="复制草稿")
    p.add_argument("-s", "--source", required=True, help="源草稿名称或目录名")
    p.add_argument("-n", "--name", help="新草稿名称")
    p.add_argument("-t", "--title", help="同时把时间线书名标题与封面改成这本书")
    p.add_argument("--from-title", help="源书名（默认取源草稿名）")
    add_common(p)
    p.set_defaults(func=cmd_copy)

    p = sub.add_parser("rename", help="修改草稿标题")
    p.add_argument("-s", "--source", required=True, help="原草稿名称或目录名")
    p.add_argument("-n", "--name", required=True, help="新名称")
    add_common(p)
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("retitle", help="改时间线书名标题并重新生成封面")
    p.add_argument("-s", "--source", required=True, help="草稿名称或目录名")
    p.add_argument("-t", "--title", required=True, help="新书名")
    p.add_argument("--from-title", help="源书名（默认取草稿名）")
    add_common(p)
    p.set_defaults(func=cmd_retitle)

    p = sub.add_parser("backup", help="备份整个草稿库")
    p.add_argument("-d", "--dest", required=True, help="备份目标目录")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("set-bg", help="替换草稿背景/配图并用新图重做封面")
    p.add_argument("-s", "--source", required=True, help="草稿名称或目录名")
    p.add_argument("-i", "--image", required=True, help="新图片路径")
    p.add_argument("--old", help="只替换路径中包含该字符串的图片引用")
    p.add_argument("--filename", help="存入 Resources/ 的文件名")
    p.add_argument("-t", "--title", help="封面书名，默认取草稿名")
    p.add_argument("--no-clean-mark", action="store_true",
                   help="图片已无 AI 标识，跳过清理")
    p.add_argument("--no-cover", action="store_true", help="不重生成封面")
    add_common(p)
    p.set_defaults(func=cmd_setbg)

    p = sub.add_parser("fit-duration", aliases=["fit"],
                       help="把背景图/BGM/贴纸/标题对齐到字幕与配音的总时长")
    p.add_argument("-s", "--source", required=True, help="草稿名称或目录名")
    p.add_argument("--target", help="目标总时长（微秒），默认取字幕/配音最晚结束时间")
    p.add_argument("--no-bgm-loop", action="store_true",
                   help="BGM 不循环补齐，只延长最后一段（可能产生静音）")
    p.add_argument("--dry-run", action="store_true",
                   help="只预览改动，不写盘、不退出剪映")
    add_common(p)
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("fix-subtitles", aliases=["subs"],
                       help="以已调好的草稿为参照，批量对齐字幕字号/缩放/位置/样式")
    p.add_argument("-s", "--source", required=True, help="目标草稿名称或目录名")
    p.add_argument("--from", dest="from_draft", default="小王子",
                   help="参照草稿，默认 小王子")
    p.add_argument("--size", type=float, help="覆盖字号")
    p.add_argument("--scale", type=float, help="覆盖缩放，如 0.21")
    p.add_argument("--x", type=float, help="覆盖面板位置 X（像素）")
    p.add_argument("--y", type=float, help="覆盖面板位置 Y（像素）")
    p.add_argument("--line-spacing", type=float, help="覆盖行间距存储值")
    p.add_argument("--max-chars", type=int, default=0,
                   help="旧折行规则：每行最多字数（防遮住左侧光盘）；默认 0=不按字数折行。"
                        "指定后走旧规则，会插入硬换行")
    p.add_argument("--max-lines", type=int, default=0,
                   help="旧折行规则：把每段字幕压缩到最多 N 行（显式指定时覆盖 --max-chars）")
    p.add_argument("--strip-punct", action="store_true",
                   help="显式去掉标点（默认保留标点，只去硬换行）")
    p.add_argument("--no-flat", action="store_true",
                   help="关闭系列默认的扁平化（去硬换行、保留标点），完全不改动字幕文本")
    wg = p.add_mutually_exclusive_group()
    wg.add_argument("--max-width", "--width", dest="width", type=float,
                    help="最大文本框宽度 fixed_width（默认按 22字≈1105 线性换算）")
    wg.add_argument("--auto-width", action="store_true",
                    help="删除 fixed_width，恢复参照草稿的自动宽度")
    wg.add_argument("--keep-width", action="store_true",
                    help="保留原 fixed_width 不动")
    p.add_argument("--dry-run", action="store_true",
                   help="只预览，不写盘、不退出剪映")
    add_common(p)
    p.set_defaults(func=cmd_fixsub)

    p = sub.add_parser("fix-cover", help="全量重做封面（含时间线副本、封面候选、内嵌封面工程）")
    p.add_argument("-s", "--source", required=True, help="草稿名称或目录名")
    p.add_argument("-t", "--title", help="书名，默认草稿名")
    p.add_argument("--base", help="底图，默认草稿当前 Resources 配图")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写盘、不退出剪映")
    add_common(p)
    p.set_defaults(func=cmd_fixcover)

    p = sub.add_parser("materials", help="查看草稿素材引用")
    p.add_argument("-s", "--source", required=True, help="草稿名称或目录名")
    p.set_defaults(func=cmd_materials)

    p = sub.add_parser("fix-media", aliases=["link-media"],
                       help="修复「链接媒体丢失」：音频搬进草稿内并重建加密 meta 登记表")
    p.add_argument("-s", "--source", action="append",
                   help="草稿名，可重复传 -s 一次处理多本")
    p.add_argument("--dry-run", action="store_true",
                   help="只诊断，不写盘、不退出剪映")
    add_common(p)
    p.set_defaults(func=cmd_fixmedia)

    p = sub.add_parser("reopen", help="重开剪映并把指定草稿置顶")
    p.add_argument("draft", nargs="?", help="草稿名，默认 小王子")
    p.set_defaults(func=cmd_reopen)

    p = sub.add_parser("covers", aliases=["article-covers"],
                       help="收尾：生成手机竖版 + 电脑横版封面，输出到 markdown 同目录")
    p.add_argument("-s", "--source", required=True, help="书名（也是草稿名）")
    p.add_argument("--author", default="", help="作者署名，默认留空（系列既有封面只叠书名）")
    p.add_argument("--md", help="指定 .md 文件或其所在目录；默认按书名自动定位")
    p.add_argument("--article-root", help="文章仓库根目录，默认 " + ARTICLE_ROOT)
    p.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令")
    p.set_defaults(func=cmd_covers)

    args = ap.parse_args()
    if not hasattr(args, "force"):
        args.force = False
    if not hasattr(args, "no_quit"):
        args.no_quit = False
    if not hasattr(args, "no_reopen"):
        args.no_reopen = False
    args.func(args)


if __name__ == "__main__":
    main()
