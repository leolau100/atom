#!/usr/bin/env python3
"""
把长文本切成 K 段（默认 5），用于分段配音。

特点：
  - 按句子边界切，不会把句子拦腰截断
  - **优先不切在引号 / 书名号 / 括号内部**（切在引号里 TTS 读起来会别扭）
  - 在上面的前提下用动态规划切到恰好 K 段，并让各段长度尽量均衡
  - 长度相同时优先切在段落结尾
  - 可自动丢弃标题行（# 开头）

用法：
  python split_text.py --in "原文.txt" --outdir out/ --parts 5

输出：
  out/chunk_01.txt ... chunk_0K.txt
  out/.split_report.txt   （各段字数、全文、切点情况）
"""
import argparse, re, pathlib, functools


def char_len(s):
    return len(re.sub(r'\s', '', s))


def split_text(text, k):
    # 去标题行
    lines = [l for l in text.split("\n") if not l.strip().startswith("#")]
    text = "\n".join(lines)
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    # 句子单元 + 是否段末
    units = []
    for p in paras:
        ss = [s for s in re.split(r'(?<=[。！？])', p) if s.strip()]
        for i, s in enumerate(ss):
            units.append((s, i == len(ss) - 1))
    n = len(units)
    pre = [0] * (n + 1)
    for i, (s, _) in enumerate(units, 1):
        pre[i] = pre[i - 1] + char_len(s)
    full = "".join(u for u, _ in units)

    def unsafe(pos):
        """切点是否落在引号/书名号/括号内部"""
        t = full[:pos]
        for a, b in (("“", "”"), ("《", "》"), ("（", "）"), ("(", ")")):
            if t.count(a) != t.count(b):
                return True
        return False

    def solve(safe_only):
        """safe_only=True 时只在引号外切；无解返回 None"""
        @functools.lru_cache(None)
        def dp(i, kk):
            if kk == 1:
                return (pre[n] - pre[i], 0)
            best = None
            for j in range(i + 1, n - kk + 2):
                if safe_only and unsafe(pre[j]):
                    continue
                sub = dp(j, kk - 1)
                if sub is None:
                    continue
                cand = (max(pre[j] - pre[i], sub[0]),
                        sub[1] + (0 if units[j - 1][1] else 1))
                if best is None or cand < best:
                    best = cand
            return best

        if dp(0, k) is None:
            return None
        cuts, i, kk = [], 0, k
        while kk > 1:
            found = False
            for j in range(i + 1, n - kk + 2):
                if safe_only and unsafe(pre[j]):
                    continue
                sub = dp(j, kk - 1)
                if sub is None:
                    continue
                cand = (max(pre[j] - pre[i], sub[0]),
                        sub[1] + (0 if units[j - 1][1] else 1))
                if cand == dp(i, kk):
                    cuts.append(j); i = j; kk -= 1; found = True
                    break
            if not found:
                return None
        cuts.append(n)
        segs, prev = [], 0
        for end in cuts:
            segs.append("".join(u for u, _ in units[prev:end])); prev = end
        return segs, dp(0, k)

    if n < k:
        raise SystemExit(f"文本只有 {n} 个句子，不足 {k} 段")

    res = solve(True)
    safe = True
    if res is None:                       # 引号外无解时退回普通切分
        res = solve(False); safe = False
    segs, cost = res
    return segs, cost, safe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--parts", type=int, default=5)
    ap.add_argument("--prefix", default="chunk")
    args = ap.parse_args()

    text = pathlib.Path(args.src).read_text(encoding="utf-8")
    segs, cost, safe = split_text(text, args.parts)

    od = pathlib.Path(args.outdir); od.mkdir(parents=True, exist_ok=True)
    report = [f"源文件: {args.src}", f"总字数(去空白): {char_len(text)}",
              f"切成 {len(segs)} 段，最长段 {cost[0]} 字，"
              f"切点为{'引号外（安全）' if safe else '含引号内部（无法避开）'}，"
              f"切在段中 {cost[1]} 处", ""]
    print(f"切成 {len(segs)} 段（{'引号外安全切点' if safe else '含引号内切点'}）：")
    for i, s in enumerate(segs, 1):
        p = od / f"{args.prefix}_{i:02d}.txt"
        p.write_text(s + "\n", encoding="utf-8")
        line = f"{p.name}  {char_len(s):4d} 字  |  {s[:34]}…"
        print("  " + line)
        report += [line, f"    全文: {s}", ""]
    (od / ".split_report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\n文本已保存到 {od}/，报告: {od}/.split_report.txt")


if __name__ == "__main__":
    main()
