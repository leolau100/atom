#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去除生成图右下角的「AI生成 / WORKBUDDY」等标识。

模式：
  auto（默认，2026-11 实测）：
    - 亮底插画（水彩等无方向性纹理）→ 大核中值，避免克隆搬来水平错位线。
    - 深底星场 → 邻近克隆 + 暗像素亮度匹配。
    - 只羽化左 / 上边界；右 / 下贴图像边缘不羽化，否则最角落会残留。
  clone（2026-11-15 新增，摄影图必用）：
    写实摄影的木纹 / 织物有方向性横纹，中值会抹成模糊块、白色笔画
    inpaint 会留竖条。改为紧邻左侧同宽同高「沿纹理方向水平平移克隆」+
    中位数亮度匹配，只羽化左边界，纹理连续无痕。

用法:
  python3 clean_ai_mark.py --in generated.png --out clean.jpg
  python3 clean_ai_mark.py --in photo.png --out clean.png --mode clone
  python3 clean_ai_mark.py --in a.png --out a.jpg --x0 0.89 --y0 0.91
"""
import argparse
import os

import cv2
import numpy as np


def _write(dst, img):
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    if dst.lower().endswith(".png"):
        cv2.imwrite(dst, img)          # 无损
    else:
        cv2.imwrite(dst, img, [cv2.IMWRITE_JPEG_QUALITY, 95])


def clean(src, dst, x0r=0.895, y0r=0.910, offset_ratio=0.125, feather=18,
          clean_mode="auto"):
    img = cv2.imread(src, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"无法读取图片: {src}")
    h, w = img.shape[:2]
    x0, y0 = int(w * x0r), int(h * y0r)
    x1, y1 = w, h
    bw, bh = x1 - x0, y1 - y0
    if bw < 20 or bh < 20:
        raise SystemExit("水印区域过小，请检查 --x0 / --y0")

    dst_patch = img[y0:y1, x0:x1].astype(np.float32)
    mean_lum = float(img.mean())

    if clean_mode == "clone":
        sx0 = max(0, x0 - bw)
        src_patch = img[y0:y1, sx0:sx0 + bw].astype(np.float32)
        if src_patch.shape != dst_patch.shape:
            raise SystemExit("克隆源越界，请调小 --x0")
        ref = np.percentile(dst_patch.reshape(-1, 3), 50, axis=0)
        pm = np.maximum(np.percentile(src_patch.reshape(-1, 3), 50, axis=0), 1.0)
        matched = np.clip(src_patch * np.clip(ref / pm, 0.90, 1.10), 0, 255)
        xx = np.arange(bw, dtype=np.float32)[None, :]
        alpha = np.clip(xx / max(feather, 1), 0, 1)
        alpha = cv2.GaussianBlur(np.repeat(alpha, bh, axis=0), (0, 0), 3)[..., None]
        out = matched * alpha + dst_patch * (1 - alpha)
        img[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)
        _write(dst, img)
        print(f"已去标识: {dst}  ({w}x{h}, 处理区 x>={x0}, y>={y0}, 模式=摄影水平克隆)")
        return

    if clean_mode == "auto" and mean_lum > 140:
        # 明亮浅色插画：亮底上的白色细笔画水印用大核中值即可抹掉，
        # 且补丁取自目标区自身，不会产生跨区域纹理错位。
        matched = cv2.medianBlur(dst_patch.astype(np.uint8), 31).astype(np.float32)
        matched = cv2.GaussianBlur(matched, (0, 0), 1.2)
        mode = "亮底中值"
    else:
        # 深色 / 星场图沿用原来的「邻近克隆 + 亮度匹配」方案
        dx = int(w * offset_ratio)
        sx0 = max(0, x0 - dx)
        src_patch = img[y0:y1, sx0:sx0 + bw].astype(np.float32)
        if src_patch.shape != dst_patch.shape:
            raise SystemExit("克隆源越界，请调小 --offset")
        lum = dst_patch.mean(axis=2)
        dark = dst_patch[lum < np.percentile(lum, 60)]
        ref = dark.mean(axis=0) if len(dark) > 100 else dst_patch.mean(axis=(0, 1))
        pm = np.maximum(src_patch.mean(axis=(0, 1)), 1.0)
        ratio = np.clip(ref / pm, 0.82, 1.18)
        matched = np.clip(src_patch * ratio, 0, 255)
        mode = "暗底克隆"

    # 只羽化左 / 上边界；右 / 下贴图像边缘不羽化，否则最角落的水印会残留
    yy, xx = np.mgrid[0:bh, 0:bw]
    dist = np.minimum(xx, yy).astype(np.float32)
    alpha = np.clip(dist / feather, 0, 1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 6)[..., None]
    out = matched * alpha + dst_patch * (1 - alpha)
    img[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)

    _write(dst, img)
    print(f"已去标识: {dst}  ({w}x{h}, 处理区 x>={x0}, y>={y0}, 模式={mode})")


def main():
    ap = argparse.ArgumentParser(description="去除生成图右下角 AI 标识")
    ap.add_argument("--in", dest="inp", required=True, help="输入图片")
    ap.add_argument("--out", required=True, help="输出 jpg / png")
    ap.add_argument("--x0", type=float, default=0.895, help="处理区左边界比例")
    ap.add_argument("--y0", type=float, default=0.910, help="处理区上边界比例")
    ap.add_argument("--offset", type=float, default=0.125, help="克隆源左移比例")
    ap.add_argument("--feather", type=int, default=18, help="羽化宽度 px")
    ap.add_argument("--mode", dest="clean_mode", choices=["auto", "clone"],
                    default="auto", help="clone=摄影图沿纹理水平克隆（推荐摄影图）")
    a = ap.parse_args()
    clean(os.path.expanduser(a.inp), os.path.expanduser(a.out),
          a.x0, a.y0, a.offset, a.feather, a.clean_mode)


if __name__ == "__main__":
    main()
