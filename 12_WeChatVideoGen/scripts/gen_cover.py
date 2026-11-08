#!/usr/bin/env python3
# 生成「抽象流体色块」风格的演示视频封面（片头 PNG / 微信封面）。
# 风格参考：深色底 + 大面积柔和有机 blob 色块，配色走极简抽象壁纸（Minimal
# Abstract）的协调粉彩路线（低饱和、互相协调），现代安静、有设计感。
# 用法: python3 gen_cover.py --out 封面.png --title ModbusSim \
#        --subtitle "Modbus RTU/TCP 模拟器" --tagline "演示视频"
import sys, os, random, argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
W, H = 1600, 1000
random.seed(20260906)

# 极简抽象壁纸（Minimal Abstract）风格的协调粉彩配色。
# 来源：同风格真实配色（HueHive / ColorAny 等），柔和低饱和、互相协调，
# 在深灰蓝底上显色柔和有层次。后续若用户提供 Pinterest pin 精确色值可一键替换。
PALETTE = [
    (230, 213, 229),  # 0 粉紫
    (183, 226, 214),  # 1 薄荷绿
    (179, 215, 230),  # 2 雾蓝
    (247, 209, 181),  # 3 蜜桃
    (243, 235, 175),  # 4 柠檬
    (241, 211, 211),  # 5 芭蕾粉
    (201, 182, 228),  # 6 薰衣草
    (240, 233, 224),  # 7 米白（点缀）
    (230, 201, 201),  # 8 玫瑰灰
    (163, 196, 224),  # 9 亮雾蓝
]


def _blob_layer(cx, cy, w, h, fill, rot=0, blur=0):
    """生成一个椭圆色块的透明图层。"""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    ld.ellipse([x0, y0, x0 + w, y0 + h], fill=fill + (255,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
    if rot:
        layer = layer.rotate(rot, expand=False, resample=Image.BILINEAR)
    return layer


def _rect_blob_layer(cx, cy, w, h, fill, rot=0, radius=80, blur=0):
    """生成一个圆角长条形色块的透明图层。"""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    ld.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=radius,
                         fill=fill + (255,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
    if rot:
        layer = layer.rotate(rot, expand=False, resample=Image.BILINEAR)
    return layer


def gen_cover(title, subtitle, tagline, out_path):
    # 1) 深灰蓝背景，带轻微竖向渐变
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top, bottom = (30, 37, 56), (22, 28, 46)
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c + (255,))

    # 2) 抽象流体色块：大椭圆 + 倾斜长条，避开中央文字区
    # 中央保护区
    margin_x, margin_y = 280, 180
    px0, py0 = margin_x, margin_y
    px1, py1 = W - margin_x, H - margin_y

    # 大型柔和流体 blob（椭圆 + 高斯模糊），营造抽象艺术背景
    fluid_blobs = [
        (140, 80, 520, 360, PALETTE[0], -20, 90),
        (W - 140, 60, 480, 340, PALETTE[1], 25, 80),
        (90, H - 80, 440, 320, PALETTE[3], -15, 85),
        (W - 120, H - 100, 420, 300, PALETTE[4], 18, 80),
        (W // 2, -40, 540, 240, PALETTE[2], 8, 70),
        (W // 2 + 120, H - 20, 520, 220, PALETTE[5], -10, 90),
        (W // 2 - 300, H // 2 - 100, 300, 220, PALETTE[6], 40, 70),
        (W // 2 + 360, H // 2 + 80, 260, 200, PALETTE[8], -35, 70),
    ]
    for cx, cy, bw, bh, fill, rot, blur in fluid_blobs:
        img = Image.alpha_composite(
            img, _blob_layer(cx, cy, bw, bh, fill, rot=rot, blur=blur))

    # 清晰边界装饰椭圆/圆点
    accents = [
        (180, 220, 160, 160, PALETTE[7], 30),
        (W - 200, 260, 130, 130, PALETTE[0], 0),
        (240, H - 220, 150, 150, PALETTE[6], 45),
        (W - 250, H - 200, 120, 120, PALETTE[9], 15),
        (W // 2, 120, 80, 80, PALETTE[5], 60),
        (W // 2, H - 130, 90, 90, PALETTE[3], -30),
    ]
    for x, y, ew, eh, fill, rot in accents:
        img = Image.alpha_composite(
            img, _blob_layer(x, y, ew, eh, fill, rot=rot, blur=0))

    # 3) 中央文字面板：半透明深色 + 细边框，现代卡片感
    panel_w, panel_h = 960, 420
    px = (W - panel_w) // 2
    py = (H - panel_h) // 2

    # 面板后加一层柔光，让文字从背景色块中浮出
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([px - 12, py - 12, px + panel_w + 12, py + panel_h + 12],
                         radius=40, fill=(0, 0, 0, 80))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)

    # 主面板
    d.rounded_rectangle([px, py, px + panel_w, py + panel_h],
                       radius=32, fill=(28, 34, 52, 245))
    # 顶部彩色装饰条（蜜桃粉彩）
    d.rounded_rectangle([px, py, px + panel_w, py + 10], radius=10,
                       fill=(247, 209, 181, 255))

    # 4) 文字
    title_font = ImageFont.truetype(FONT, 96, index=0)
    sub_font = ImageFont.truetype(FONT, 38, index=0)
    tag_font = ImageFont.truetype(FONT, 42, index=0)

    # 主标题
    title_w = d.textlength(title, font=title_font)
    d.text(((px + (panel_w - title_w) // 2), py + 80), title,
           font=title_font, fill=(255, 255, 255))

    # 标题下强调短横
    bar_w = 120
    d.rounded_rectangle([px + (panel_w - bar_w) // 2, py + 205,
                         px + (panel_w + bar_w) // 2, py + 213],
                       radius=4, fill=(247, 209, 181, 255))

    sub_w = d.textlength(subtitle, font=sub_font)
    d.text(((px + (panel_w - sub_w) // 2), py + 235), subtitle,
           font=sub_font, fill=(190, 200, 220))

    tag_w = d.textlength(tagline, font=tag_font)
    d.text(((px + (panel_w - tag_w) // 2), py + 300), tagline,
           font=tag_font, fill=(247, 209, 181))

    img.convert('RGB').save(out_path, quality=95)
    return out_path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--tagline', default='演示视频')
    a = ap.parse_args()
    gen_cover(a.title, a.subtitle, a.tagline, a.out)
    print('COVER ->', a.out)
