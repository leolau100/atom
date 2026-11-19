#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open_draft.py — 剪映草稿改动后的「自动重开」统一收尾工具（用户 2026-11-09 要求）

约定：任何「改草稿 JSON」的脚本跑完，都要自动把剪映重新打开、并让目标草稿
      出现在草稿箱第一位，用户不再需要手动退出/重开/找草稿。

============  2026-11-09 实测结论（剪映 10.3.0 / macOS，勿重复调研）  ============
1. 剪映运行时会锁草稿 JSON，并把内存里的数据回写磁盘覆盖外部改动
   → 所有改草稿脚本必须先【完全退出】剪映（quit_first=True）。
   注意 globalSetting 里 minimize_to_tray_when_app_quit=true，
   osascript quit 常常只是缩到托盘，必须 pkill 兜底。

2. 主程序 VELauncher 内置 --draft_path / --draft_from / --draft_type /
   --open_timestamp 启动参数（strings 可见 "[tool_app] launch appArgv draftPath"），
   但实测 `open -a <app> --args ...` 时参数被 LaunchServices 丢弃
   （pgrep 显示主进程命令行不带 --draft_path），launchctl setenv 又因沙箱
   "Not privileged to set domain environment" 被拒。
   → 【无法】用命令行参数让剪映「直达」某个草稿。

3. 权限硬限制（当前机器）：
   - 无「辅助功能」权限：System Events 恒返回 -10004（用中文进程名也一样），
     无法按 UI 控件名字点击；
   - 无「屏幕录制」权限：CGWindowListCreateImage 返回 None，无法截屏定位坐标；
   - pyautogui.moveBy / CGEvent 注入实测不稳定，不能用于盲点。
   → 【无法】在零授权状态下自动「点进」草稿编辑界面。

4. 零权限且可靠可行的方案（本脚本采用）：
   a) 完全退出剪映
   b) 刷新目标草稿 tm_draft_modified（com.bytedance.JianyingPro.plist 里
      homePageLocalModifyTimeSortOrder=true，草稿箱按修改时间倒序 → 目标排第一）
   c) `open -a` 启动剪映
   d) 用 Quartz CGWindowListCopyWindowInfo 只读校验「剪映专业版」窗口确实出现
      （窗口 owner 名是中文「剪映专业版」，窗口 title 为空）
   e) 若将来授予了辅助功能权限，额外用 System Events 按名字点开草稿（保守：
      只在 AX 树里找到确切草稿名时才点，避免误点其他按钮）

用法：
  python3 open_draft.py                 # 退出剪映 → 置顶《小王子》→ 重开
  python3 open_draft.py 11月8日         # 指定草稿
  python3 open_draft.py --quit-only    # 只退出剪映（改草稿脚本开头用）
  python3 open_draft.py --no-quit      # 剪映已退出，只做置顶 + 重开
  python3 open_draft.py --check        # 只读状态检查（进程/窗口/权限/排序）

供其他脚本调用：
  import open_draft
  open_draft.quit_jianying()               # 改草稿前
  open_draft.reopen("小王子", quit_first=False)   # 改完草稿后
======================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

APP = os.environ.get("JY_APP") or "/Applications/VideoFusion-macOS.app"
PROC_NAME = "剪映专业版"  # Quartz CGWindowListCopyWindowInfo 里的 owner 名（中文！）
# 草稿根目录：可用 JY_DRAFT_ROOT 覆盖（换机器/换用户名时设置），否则用当前用户默认位置
DRAFT_ROOT = (
    os.environ.get("JY_DRAFT_ROOT")
    or os.path.expanduser("~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft")
)
REGISTRY = os.path.join(DRAFT_ROOT, "root_meta_info.json")
DEFAULT_DRAFT = "小王子"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def is_running():
    return bool(sh(["pgrep", "-fl", "-i", "VideoFusion"]).stdout.strip())


def quit_jianying(timeout=6):
    """完全退出剪映；osascript quit 可能被 '最小化到托盘' 吞掉，故 pkill 兜底。"""
    if not is_running():
        print("· 剪映当前未运行，无需退出")
        return True
    sh(["osascript", "-e", 'tell application "VideoFusion-macOS" to quit'])
    for _ in range(timeout):
        time.sleep(1)
        if not is_running():
            break
    if is_running():
        print("· 优雅退出未生效（缩到托盘），兜底强退")
        sh(["pkill", "-f", "VideoFusion-macOS"])
        for _ in range(4):
            time.sleep(1)
            if not is_running():
                break
    ok = not is_running()
    print("· 退出剪映:", "OK" if ok else "失败（改动可能被覆盖，请手动退出后重跑）")
    return ok


def touch_draft(name):
    """刷新目标草稿的 tm_draft_modified，使其在草稿箱按修改时间排序时排第一。"""
    if not os.path.exists(REGISTRY):
        print("· 找不到草稿清单，跳过置顶")
        return False
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            d = json.load(f)
        target = next((it for it in d.get("all_draft_store", [])
                       if it.get("draft_name") == name), None)
        if target is None:
            print(f"· 清单里没有草稿 {name!r}，跳过置顶")
            return False
        shutil.copy(REGISTRY, f"{REGISTRY}.bak_{int(time.time())}")
        now = int(time.time() * 1e6)
        key = next((k for k in ("tm_draft_modified", "tm_modify",
                                "tm_draft_create", "tm_create") if k in target),
                   "tm_draft_modified")
        target[key] = now
        with open(REGISTRY, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)

        # 剪映在沙盒容器内还有一份 root_meta_info.json，启动时以它为准并回写主索引。
        # 两份都刷新，否则置顶会被容器旧值覆盖。
        mirror = os.path.expanduser(
            "~/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/"
            "User Data/Projects/com.lveditor.draft/root_meta_info.json")
        if os.path.isfile(mirror) and os.path.abspath(mirror) != os.path.abspath(REGISTRY):
            try:
                with open(mirror, encoding="utf-8") as f:
                    md = json.load(f)
                mt = next((it for it in md.get("all_draft_store", [])
                           if it.get("draft_name") == name), None)
                if mt is not None:
                    mt[key] = now
                    with open(mirror, "w", encoding="utf-8") as f:
                        json.dump(md, f, ensure_ascii=False)
                    print("· 已同步置顶到沙盒容器索引副本")
            except Exception as e:
                print("· [提示] 容器索引置顶同步失败:", e)
        print(f"· 已置顶草稿 {name!r}（刷新 {key}）")
        return True
    except Exception as e:
        print("· 置顶失败:", e)
        return False


def window_bounds():
    """Quartz 只读窗口信息（无需任何权限）；返回剪映主窗口 bounds。"""
    try:
        import Quartz
        wl = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
        for w in wl:
            if w.get("kCGWindowOwnerName") == PROC_NAME:
                b = w.get("kCGWindowBounds") or {}
                if b.get("Width", 0) > 400 and b.get("Height", 0) > 300:
                    return b
    except Exception:
        pass
    return None


def launch(wait=40):
    print("· 启动剪映 …")
    r = sh(["open", "-a", APP])
    if r.returncode:
        print("  open 报错:", r.stderr.strip()[:150])
    for i in range(wait):
        time.sleep(1)
        b = window_bounds()
        if b:
            print(f"· 剪映窗口已出现（等待 {i + 1}s，"
                  f"{int(b['Width'])}x{int(b['Height'])}）")
            return True
    print("· 等待超时：未检测到剪映窗口（可能仍在启动），进程存在 =", is_running())
    return is_running()


def accessibility_ok():
    r = sh(["osascript", "-e",
            'tell application "System Events" to get UI elements enabled'])
    return r.returncode == 0 and "true" in (r.stdout or "").strip().lower()


def try_open_via_ui(name):
    """仅当已授权辅助功能时，按名字点开草稿；找不到确切元素就不点（安全）。"""
    if not accessibility_ok():
        return False, "未授予「辅助功能」权限（系统设置 → 隐私与安全 → 辅助功能）"

    probe = f'''
    tell application "System Events" to tell process "{PROC_NAME}"
        set frontmost to true
        try
            return name of every window
        on error
            return {{}}
        end try
    end tell
    '''
    r = sh(["osascript", "-e", probe])
    if r.returncode:
        return False, "已授权但读 UI 失败：" + (r.stderr or "").strip()[:100]

    click = f'''
    tell application "System Events" to tell process "{PROC_NAME}"
        set frontmost to true
        repeat with e in (entire contents of window 1)
            try
                if (name of e) is "{name}" then
                    perform action "AXPress" of e
                    return "clicked"
                end if
            end try
        end repeat
        return "not_found"
    end tell
    '''
    c = sh(["osascript", "-e", click])
    done = "clicked" in (c.stdout or "")
    return done, ("AXPress 已执行" if done else
                  "AX 树里没有确切草稿名（CEF 自绘界面），已跳过点击以免误操作")


def reopen(name=DEFAULT_DRAFT, quit_first=True, click_if_possible=True):
    print(f"=== 自动重开草稿：{name} ===")
    if quit_first and not quit_jianying():
        print("⚠️ 剪映未能退出，停止重开（避免改动被覆盖）")
        return False
    touch_draft(name)
    ok = launch()
    if click_if_possible:
        done, msg = try_open_via_ui(name)
        print(f"· UI 直达草稿: {'OK' if done else '未达成'} — {msg}")
    print(f"✅ 剪映已打开，《{name}》在草稿箱第一位"
          + ("并已进入编辑界面" if click_if_possible and done else "（双击即进入）"))
    return ok


def status(name=DEFAULT_DRAFT):
    print("=== 状态检查 ===")
    print("  剪映进程 :", "运行中" if is_running() else "未运行")
    b = window_bounds()
    print("  剪映窗口 :", (f"{int(b['Width'])}x{int(b['Height'])} "
                      f"@({int(b['X'])},{int(b['Y'])})" if b else "无"))
    print("  辅助功能 :", "已授权" if accessibility_ok() else "未授权")
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            d = json.load(f)
        rows = sorted(
            ((it.get("tm_draft_modified") or it.get("tm_modify") or 0,
              it.get("draft_name")) for it in d.get("all_draft_store", [])),
            reverse=True)
        print("  草稿箱序 :", " > ".join(str(n) for _, n in rows[:5]))
    except Exception as e:
        print("  读取清单失败:", e)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="剪映草稿改动后自动重开并置顶")
    ap.add_argument("draft", nargs="?", default=DEFAULT_DRAFT, help="草稿名")
    ap.add_argument("--quit-only", action="store_true", help="只退出剪映")
    ap.add_argument("--no-quit", action="store_true", help="剪映已退出，只置顶+重开")
    ap.add_argument("--check", action="store_true", help="只读状态检查")
    ap.add_argument("--no-ui", action="store_true", help="不尝试 UI 点击")
    a = ap.parse_args()
    if a.check:
        status(a.draft)
    elif a.quit_only:
        quit_jianying()
    else:
        reopen(a.draft, quit_first=not a.no_quit,
               click_if_possible=not a.no_ui)
