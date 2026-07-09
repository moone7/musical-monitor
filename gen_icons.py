#!/usr/bin/env python3
"""gen_icons.py — 生成音乐剧监控 PWA 图标（霓虹音符 on 暗紫渐变）"""
from PIL import Image, ImageDraw

SIZES = [192, 256, 384, 512, 180]
TOP = (26, 15, 46)
BOT = (10, 9, 16)
NOTE = (255, 134, 192)


def make_icon(S):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    px = img.load()
    # 垂直渐变背景
    for y in range(S):
        t = y / (S - 1)
        r = int(TOP[0] + (BOT[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOT[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOT[2] - TOP[2]) * t)
        for x in range(S):
            px[x, y] = (r, g, b, 255)

    d = ImageDraw.Draw(img)
    k = S / 512.0  # 缩放因子

    def ell(cx, cy, rx, ry, fill):
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)

    def rect(x0, y0, x1, y1, fill):
        d.rectangle([x0, y0, x1, y1], fill=fill)

    # 左音符
    ell(int(180 * k), int(360 * k), int(56 * k), int(42 * k), NOTE)
    rect(int(226 * k), int(150 * k), int(246 * k), int(365 * k), NOTE)
    d.polygon([(246 * k, 150 * k), (316 * k, 185 * k), (316 * k, 240 * k), (246 * k, 205 * k)], fill=NOTE)
    # 右音符
    ell(int(340 * k), int(330 * k), int(44 * k), int(33 * k), NOTE)
    rect(int(376 * k), int(160 * k), int(392 * k), int(333 * k), NOTE)

    # 圆角遮罩
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.19), fill=255)
    img.putalpha(mask)
    return img


if __name__ == "__main__":
    for S in SIZES:
        img = make_icon(S)
        fn = f"icon-{S}.png"
        img.save(fn)
        print(f"  ✓ {fn} ({S}x{S})")
    print("图标生成完成")
