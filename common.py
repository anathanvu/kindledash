"""Bố cục + hàm vẽ dùng chung cho render.py (GitHub) và build_assets.py (Kindle)."""
import math, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# Kindle Basic 2019: 600x800 dọc -> 800x600 ngang
W, H = 800, 600
PHOTO_W = 392
INFO_X, INFO_W = PHOTO_W, W - PHOTO_W      # cột thông tin 408px
CLOCK_RECT = (INFO_X + 27, -4, 354, 122)    # x, y, w, h (toạ độ ngang)
BATT_RECT = (W - 8 - 166, 562, 166, 38)
BRAND = "VŨ HOME BOARD"                    # tên dashboard
OWNER = "AnathanVu"

# "cw" = cạnh nút nguồn/USB nằm bên PHẢI khi đặt ngang; "ccw" = bên TRÁI
ROTATE = os.environ.get("KDASH_ROTATE") or "cw"


def font(weight, size):
    name = {"r": "Inter-Regular.otf", "m": "Inter-Medium.otf", "b": "Inter-Bold.otf"}[weight]
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)


def rotate_img(img):
    if ROTATE == "cw":
        return img.transpose(Image.Transpose.ROTATE_270)
    return img.transpose(Image.Transpose.ROTATE_90)


def rect_to_portrait(rect):
    x, y, w, h = rect
    if ROTATE == "cw":
        return (H - y - h, x, h, w)
    return (y, W - x - w, h, w)


def gray16(img, dither=False):
    img = img.convert("L")
    if not dither:
        return img.point(lambda v: min(255, int(round(v / 17.0)) * 17))
    pal = Image.new("P", (1, 1))
    pal.putpalette([c for i in range(16) for c in (i * 17,) * 3] + [0] * (768 - 48))
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


def save_png(img, path, dither=False):
    gray16(img, dither).save(path, optimize=True)


def clock_strip(hh, mm):
    w, h = CLOCK_RECT[2], CLOCK_RECT[3]
    im = Image.new("L", (w, h), 255)
    ImageDraw.Draw(im).text((w // 2, h // 2 + 2), f"{hh:02d}:{mm:02d}", font=font("b", 112), fill=0, anchor="mm")
    return im


def battery_strip(level, charging=False):
    w, h = BATT_RECT[2], BATT_RECT[3]
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    bx, by, bw, bh = 4, 6, 50, 24
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=4, outline=0, width=3)
    d.rectangle((bx + bw + 1, by + 7, bx + bw + 5, by + bh - 7), fill=0)
    inner = max(0, min(100, level)) / 100.0 * (bw - 9)
    if inner > 0:
        d.rectangle((bx + 4, by + 4, bx + 4 + inner, by + bh - 4), fill=0 if level > 15 else 110)
    if charging:
        cx, cy = bx + bw // 2, by + bh // 2
        d.polygon([(cx + 3, cy - 10), (cx - 6, cy + 2), (cx, cy + 2), (cx - 3, cy + 10), (cx + 6, cy - 3), (cx, cy - 3)], fill=255, outline=0)
    d.text((w - 2, h // 2 + 1), f"{level}%", font=font("b", 24), fill=0, anchor="rm")
    return im


def _weather_icon_draw(draw, cx, cy, kind):
    def sun(x, y, r):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=0)
        for i in range(8):
            a = i * math.pi / 4
            draw.line((x + math.cos(a) * (r + 5), y + math.sin(a) * (r + 5),
                       x + math.cos(a) * (r + 12), y + math.sin(a) * (r + 12)), fill=0, width=4)

    def cloud(x, y, sc=1.0, fill=235):
        r = int(13 * sc)
        for ox, oy, rr in ((-14, 4, r), (2, -4, int(r * 1.35)), (18, 5, r)):
            draw.ellipse((x + ox * sc - rr, y + oy * sc - rr, x + ox * sc + rr, y + oy * sc + rr), fill=fill, outline=0, width=3)
        draw.rectangle((x - 14 * sc, y + 6 * sc, x + 18 * sc, y + 18 * sc), fill=fill)
        draw.line((x - 14 * sc - r + 2, y + 17 * sc, x + 18 * sc + r - 2, y + 17 * sc), fill=0, width=3)

    if kind == "sun":
        sun(cx, cy, 15)
    elif kind == "partly":
        sun(cx - 10, cy - 10, 11); cloud(cx + 6, cy + 6, 0.9)
    elif kind == "cloud":
        cloud(cx, cy, 1.1)
    elif kind == "rain":
        cloud(cx, cy - 8, 1.0)
        for dx in (-14, 0, 14):
            draw.line((cx + dx + 4, cy + 14, cx + dx - 3, cy + 28), fill=0, width=4)
    elif kind == "storm":
        cloud(cx, cy - 8, 1.0)
        draw.polygon([(cx + 4, cy + 8), (cx - 6, cy + 22), (cx, cy + 22), (cx - 4, cy + 34), (cx + 9, cy + 17), (cx + 2, cy + 17)], fill=0)
    else:
        for i in range(4):
            draw.line((cx - 24 + (i % 2) * 6, cy - 14 + i * 10, cx + 24 - (i % 2) * 6, cy - 14 + i * 10), fill=0, width=4)


WMO = {0: ("Trời quang", "sun"), 1: ("Ít mây", "sun"), 2: ("Có mây", "partly"), 3: ("Nhiều mây", "cloud"),
       45: ("Sương mù", "fog"), 48: ("Sương mù", "fog"), 51: ("Mưa phùn", "rain"), 53: ("Mưa phùn", "rain"),
       55: ("Mưa phùn", "rain"), 56: ("Mưa phùn lạnh", "rain"), 57: ("Mưa phùn lạnh", "rain"),
       61: ("Mưa nhỏ", "rain"), 63: ("Mưa vừa", "rain"), 65: ("Mưa to", "rain"), 66: ("Mưa lạnh", "rain"),
       67: ("Mưa lạnh", "rain"), 80: ("Mưa rào", "rain"), 81: ("Mưa rào", "rain"), 82: ("Mưa rào to", "rain"),
       95: ("Dông", "storm"), 96: ("Dông, mưa đá", "storm"), 99: ("Dông, mưa đá", "storm")}


def weather_icon_img(kind, size):
    """Vẽ biểu tượng ở 96px rồi thu nhỏ cho nét mượt."""
    big = Image.new("L", (96, 96), 255)
    _weather_icon_draw(ImageDraw.Draw(big), 48, 48, kind)
    sm = big.resize((size, size), Image.Resampling.LANCZOS)
    return sm.point(lambda v: 0 if v < 150 else (235 if v < 245 else 255))   # đậm nét cho e-ink
