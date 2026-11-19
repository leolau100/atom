#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「十分钟读完一本书」系列草稿封面（1920×1080）。

以本书主题插画为底，叠系列名 + 书名 + 署名。会自动判断底图明暗：
深色插画走「压暗 + 暗角 + 白字」，浅色插画走「提亮柔光 + 深墨字 + 白描边」，
两种都保证书名清晰且不破坏插画。供 jy_draft.py 的 make_cover() 调用。

用法:
  python3 make_cover.py --title 明朝那些事 --out /path/to/draft_cover.jpg
  python3 make_cover.py --title 明朝那些事 --out out.jpg --base /path/to/bg.jpg
"""
import argparse
import os
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE = os.path.join(HERE, "assets", "series_bg.jpg")
W, H = 1920, 1080

FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def load_font(size, idx=0):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_spaced(draw, xy, text, font, fill, spacing=8):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bbox = draw.textbbox((x, y), ch, font=font)
        x += (bbox[2] - bbox[0]) + spacing


def text_width(draw, text, font, spacing=0):
    return sum(draw.textbbox((0, 0), c, font=font)[2] for c in text) + spacing * max(len(text) - 1, 0)


def build(title, out, base_path, backup=True):
    if not os.path.isfile(base_path):
        raise SystemExit(f"底图不存在: {base_path}")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if backup and os.path.exists(out) and not os.path.exists(out + ".bak"):
        shutil.copy(out, out + ".bak")
        print("已备份原封面 -> draft_cover.jpg.bak")

    img = Image.open(base_path).convert("RGB")
    sw, sh = img.size
    scale = max(W / sw, H / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img = img.crop((left, top, left + W, top + H))

    # 自动判断底图明暗：系列早期是深蓝星云插画，2026-11-14 起用户要求
    # 换成明亮浅色主题，白字在浅底上会看不清，必须换配色方案。
    lum = sum(ImageStat.Stat(img.resize((64, 64))).mean) / 3
    light = lum >= 140
    print(f"  底图平均亮度 {lum:.0f} → {'浅色明亮版式' if light else '深色暗角版式'}")

    if not light:
        # 深色插画：整体压暗 + 底部深色渐变 + 四角暗角，让白字清晰。
        dark = Image.new("RGB", (W, H), (0, 0, 0))
        base = Image.blend(img, dark, 0.42)

        grad = Image.new("L", (W, H), 0)
        pxd = grad.load()
        for y in range(H):
            t = max(0.0, (y - H * 0.45) / (H * 0.55))
            v = int(170 * t)
            for x in range(W):
                pxd[x, y] = v
        base = Image.composite(Image.new("RGB", (W, H), (8, 10, 24)), base, grad)

        # 暗角：椭圆内为白 → 需反转成「中心 0、边缘 255」，
        # 否则 Image.composite 会把中心区域涂成纯色（原版 bug）。
        vig = Image.new("L", (W, H), 0)
        ImageDraw.Draw(vig).ellipse(
            [-W * 0.10, -H * 0.10, W * 1.10, H * 1.10], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(150))
        vig = vig.point(lambda p: int((255 - p) * 0.60))
        base = Image.composite(Image.new("RGB", (W, H), (6, 8, 20)), base, vig)
        halo_rgb = Image.new("RGB", (W, H), (10, 12, 28))
        halo_strength = 95
    else:
        # 浅色插画：轻微提亮柔化，绝不再压暗，否则又变成用户抱怨的深色封面。
        base = Image.blend(img, Image.new("RGB", (W, H), (255, 253, 247)), 0.10)
        grad = Image.new("L", (W, H), 0)
        pxd = grad.load()
        for y in range(H):
            t = max(0.0, (y - H * 0.62) / (H * 0.38))
            v = int(70 * t)
            for x in range(W):
                pxd[x, y] = v
        base = Image.composite(Image.new("RGB", (W, H), (252, 248, 240)), base, grad)
        halo_rgb = Image.new("RGB", (W, H), (255, 252, 246))
        halo_strength = 120

    # 书名区柔光/压暗：深色图压暗、浅色图提亮，保证文字与插画分离
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse(
        [W * 0.10, H * 0.24, W * 0.90, H * 0.74], fill=halo_strength)
    halo = halo.filter(ImageFilter.GaussianBlur(130))
    base = Image.composite(halo_rgb, base, halo)

    draw = ImageDraw.Draw(base)

    if light:
        c_series, c_title, c_stroke, c_line, c_sub = (
            (150, 98, 52), (42, 50, 58), (255, 252, 246),
            (186, 138, 74), (96, 102, 108))
    else:
        c_series, c_title, c_stroke, c_line, c_sub = (
            (255, 214, 140), (255, 255, 255), (20, 22, 45),
            (255, 214, 140), (220, 224, 240))

    series = "十分钟读完一本书"
    f_series = load_font(58)
    s_w = text_width(draw, series, f_series, 8)
    draw_spaced(draw, ((W - s_w) // 2, int(H * 0.30)), series,
                f_series, fill=c_series, spacing=8)

    size = min(220, int(1500 / max(len(title), 1)))
    f_title = load_font(size)
    t_w = text_width(draw, title, f_title)
    tx, ty = (W - t_w) // 2, int(H * 0.42)
    draw.text((tx, ty), title, font=f_title, fill=c_stroke,
              stroke_width=10, stroke_fill=c_stroke)
    draw.text((tx, ty), title, font=f_title, fill=c_title,
              stroke_width=10, stroke_fill=c_stroke)

    line_w = int(t_w * 0.55)
    lx0, ly = (W - line_w) // 2, ty + size + 30
    draw.line([(lx0, ly), (lx0 + line_w, ly)],
              fill=c_line, width=4)

    sub = "燕麦粥 · 读书"
    f_sub = load_font(44)
    sub_w = text_width(draw, sub, f_sub)
    draw.text(((W - sub_w) // 2, int(H * 0.86)), sub,
              font=f_sub, fill=c_sub)

    base.save(out, "JPEG", quality=92)
    print(f"封面已生成: {out}  ({base.size[0]}x{base.size[1]}, 书名《{title}》)")


def main():
    ap = argparse.ArgumentParser(description="生成系列视频草稿封面")
    ap.add_argument("--title", required=True, help="书名（不带书名号）")
    ap.add_argument("--out", required=True, help="输出 jpg 绝对路径")
    ap.add_argument("--base", default=DEFAULT_BASE, help="底图路径")
    ap.add_argument("--no-backup", action="store_true", help="不备份原封面")
    a = ap.parse_args()
    build(a.title.strip().strip("《》").strip(), os.path.expanduser(a.out),
          os.path.expanduser(a.base), backup=not a.no_backup)


if __name__ == "__main__":
    main()
