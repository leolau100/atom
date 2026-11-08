#!/usr/bin/env python3
# 给截图/视频帧套上 macOS 窗口外观：圆角窗口 + 标题栏 + 红黄绿按钮 + 阴影 + 壁纸背景。
# 壁纸配色与 gen_cover.py 统一（深灰蓝底 + 柔和粉彩 blob）。
# 用法: python3 gen_window_frame.py --input 截图.png --output 输出.png \
#        --title "ModbusSim REST API — Swagger UI"
#       python3 gen_window_frame.py --frame-only --output 框架.png --title "..."   # 只出框架（供视频 overlay）
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
W, H = 1600, 1000
WIN_W, WIN_H, BAR_H = 1360, 900, 48   # 窗口宽高 / 标题栏高；内容区 1360×852 ≈ 16:10
WX, WY = (W - WIN_W) // 2, (H - WIN_H) // 2
RADIUS = 14

# 与封面同风格的柔和粉彩
PASTEL = [
    (230, 213, 229),  # 粉紫
    (183, 226, 214),  # 薄荷
    (179, 215, 230),  # 雾蓝
    (247, 209, 181),  # 蜜桃
    (201, 182, 228),  # 薰衣草
]
BTN = [(255, 95, 87), (254, 188, 46), (40, 200, 64)]  # 红 黄 绿


def wallpaper():
    """深灰蓝渐变壁纸 + 柔和粉彩 blob。"""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top, bottom = (38, 45, 64), (24, 29, 44)
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c + (255,))

    blobs = [
        (140, 120, 520, 380, 0, -18, 70),
        (W - 120, 90, 460, 340, 1, 20, 60),
        (90, H - 70, 420, 300, 2, -12, 65),
        (W - 90, H - 90, 400, 280, 3, 15, 60),
        (W // 2, -30, 480, 220, 4, 8, 55),
    ]
    for cx, cy, bw, bh, ci, rot, blur in blobs:
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2],
                   fill=PASTEL[ci] + (255,))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
        if rot:
            layer = layer.rotate(rot, expand=False, resample=Image.BILINEAR)
        img = Image.alpha_composite(img, layer)
    return img


def gen_window_frame(src_path, out_path, title='', frame_only=False):
    """frame_only=True 时只生成窗口框架（内容区留空），供视频 overlay 使用。"""
    img = wallpaper()

    # 1) 窗口投影
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [WX - 6, WY + 4, WX + WIN_W + 6, WY + WIN_H + 18],
        radius=RADIUS + 6, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(18)))

    # 2) 窗口体（白）
    win = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(win).rounded_rectangle(
        [WX, WY, WX + WIN_W, WY + WIN_H], radius=RADIUS, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, win)

    # 3) 标题栏：用窗口 mask 裁切，保证顶部圆角、底部直角
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [WX, WY, WX + WIN_W, WY + WIN_H], radius=RADIUS, fill=255)
    bar = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rectangle([WX, WY, WX + WIN_W, WY + BAR_H],
                                  fill=(233, 233, 236, 255))
    bar.putalpha(Image.composite(Image.new('L', (W, H), 255),
                                 Image.new('L', (W, H), 0), mask))
    img = Image.alpha_composite(img, bar)

    d = ImageDraw.Draw(img)
    d.line([(WX, WY + BAR_H), (WX + WIN_W, WY + BAR_H)], fill=(212, 212, 216, 255))

    # 4) 红黄绿按钮
    r, cy = 7, WY + BAR_H // 2
    for i, col in enumerate(BTN):
        cx = WX + 22 + i * 22
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))

    # 5) 窗口标题
    if title:
        f = ImageFont.truetype(FONT, 20, index=0)
        tw = d.textlength(title, font=f)
        d.text((WX + (WIN_W - tw) // 2, cy - 14), title, font=f,
               fill=(60, 60, 67, 255))

    # 6) 嵌入页面截图（等比缩放居中）；frame_only 时留空供视频 overlay
    if not frame_only:
        im = Image.open(src_path).convert('RGB')
        cw, chh = WIN_W, WIN_H - BAR_H
        s = min(cw / im.width, chh / im.height)
        nw, nh = int(im.width * s), int(im.height * s)
        im = im.resize((nw, nh), Image.LANCZOS)
        img.paste(im, (WX + (cw - nw) // 2, WY + BAR_H + (chh - nh) // 2))

    img.convert('RGB').save(out_path, quality=95)
    return out_path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default=None, help='页面截图；--frame-only 时可省略')
    ap.add_argument('--output', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--frame-only', action='store_true', help='只生成窗口框架')
    a = ap.parse_args()
    if not a.frame_only and not a.input:
        ap.error('--input 为必填（除非使用 --frame-only）')
    gen_window_frame(a.input, a.output, a.title, a.frame_only)
    print('WINDOW FRAME ->', a.output)
