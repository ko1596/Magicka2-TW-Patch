"""安裝程式的美術：背景合成、面板、勾選框、按鈕。

全部在執行時依螢幕縮放比例繪製，高解析度螢幕也不會模糊。
配色取自「巫師2」標誌：深紅、金色，搭配夜空背景。
"""

import math

from PIL import Image, ImageDraw, ImageFilter

from . import ASSETS_DIR

GOLD = (233, 180, 76)
GOLD_LIGHT = (255, 224, 150)
GOLD_DARK = (140, 92, 28)
RED = (178, 20, 28)
RED_DARK = (98, 8, 12)
INK = (12, 10, 24)

def _vgrad(w, h, top, bottom):
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize((w, h), Image.BICUBIC)


def background(w: int, h: int, panels: list[tuple[int, int, int, int]], s: float) -> Image.Image:
    """背景插畫＋半透明面板（金色細邊、圓角）。"""
    bg = Image.open(ASSETS_DIR / "installer_bg.jpg").convert("RGB")
    # 依比例填滿視窗
    scale = max(w / bg.width, h / bg.height)
    bg = bg.resize((math.ceil(bg.width * scale), math.ceil(bg.height * scale)), Image.LANCZOS)
    bg = bg.crop(((bg.width - w) // 2, 0, (bg.width - w) // 2 + w, h)).convert("RGBA")
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = int(14 * s)
    for x0, y0, x1, y1 in panels:
        d.rounded_rectangle((x0, y0, x1, y1), r, fill=(*INK, 205))
    glow = layer.filter(ImageFilter.GaussianBlur(8 * s))
    bg.alpha_composite(glow)
    bg.alpha_composite(layer)
    d = ImageDraw.Draw(bg)
    for x0, y0, x1, y1 in panels:
        d.rounded_rectangle((x0, y0, x1, y1), r, outline=(*GOLD_DARK, 255), width=max(1, int(1.5 * s)))
        d.rounded_rectangle((x0 + 3 * s, y0 + 3 * s, x1 - 3 * s, y1 - 3 * s), r - 3 * s,
                            outline=(*GOLD, 70), width=1)
    return bg


def logo(width: int) -> Image.Image:
    im = Image.open(ASSETS_DIR / "logo_zh.png").convert("RGBA")
    if bbox := im.getchannel("A").getbbox():
        im = im.crop(bbox)
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def checkbox(size: int, checked: bool, hover: bool = False) -> Image.Image:
    n = size * 4
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad, r = n * .08, n * .2
    if checked:
        d.rounded_rectangle((pad, pad, n - pad, n - pad), r, fill=(*RED, 255))
        d.rounded_rectangle((pad, pad, n - pad, n * .55), r, fill=(210, 40, 44, 255))
    else:
        d.rounded_rectangle((pad, pad, n - pad, n - pad), r, fill=(20, 16, 34, 255))
    d.rounded_rectangle((pad, pad, n - pad, n - pad), r, outline=(*(GOLD_LIGHT if hover else GOLD), 255),
                        width=int(n * .08))
    if checked:
        pts = [(n * .27, n * .52), (n * .44, n * .69), (n * .75, n * .33)]
        d.line(pts, fill=(*GOLD_LIGHT, 255), width=int(n * .12), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def button(w: int, h: int, kind: str, state: str) -> Image.Image:
    """kind: primary（紅底金邊）／secondary（深底金邊）；state: normal／hover／disabled。"""
    k = 3
    W, H = w * k, h * k
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    r = int(H * .22)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), r, fill=255)
    if kind == "primary":
        top, bottom = ((220, 50, 52), (110, 10, 14)) if state != "hover" else ((245, 80, 70), (140, 18, 20))
    else:
        top, bottom = ((44, 34, 70), (18, 14, 32)) if state != "hover" else ((70, 54, 104), (30, 22, 50))
    if state == "disabled":
        top, bottom = (70, 66, 80), (40, 38, 48)
    im.paste(_vgrad(W, H, top, bottom).convert("RGBA"), (0, 0), mask)
    d = ImageDraw.Draw(im)
    edge = (120, 112, 130) if state == "disabled" else (GOLD_LIGHT if state == "hover" else GOLD)
    d.rounded_rectangle((0, 0, W - 1, H - 1), r, outline=(*edge, 255), width=int(2.2 * k))
    d.rounded_rectangle((5 * k, 4 * k, W - 5 * k, H * .45), r * .7, fill=(255, 255, 255, 22))
    return im.resize((w, h), Image.LANCZOS)
