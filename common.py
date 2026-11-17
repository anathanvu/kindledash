"""Bố cục + hàm vẽ dùng chung cho render.py (GitHub) và build_assets.py (Kindle)."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Màn hình Kindle Basic 2019: 600x800 dọc -> 800x600 ngang ----
W, H = 800, 600
PHOTO_W = 430                      # cột ảnh gia đình (nằm trên Kindle, không đưa lên GitHub)
INFO_X, INFO_W = PHOTO_W, W - PHOTO_W   # cột thông tin 370px

# Ô đồng hồ & pin (toạ độ ngang). Kindle tự dán đè lên ảnh thông tin.
CLOCK_RECT = (INFO_X + 8, 4, 354, 122)     # x, y, w, h
BATT_RECT = (INFO_X + 196, 556, 166, 38)

# Hướng xoay: "cw" = cạnh USB/nút nguồn nằm bên PHẢI khi đặt ngang; "ccw" = bên TRÁI
ROTATE = os.environ.get("KDASH_ROTATE", "cw")


def font(weight, size):
    name = {"r": "Inter-Regular.otf", "m": "Inter-Medium.otf", "b": "Inter-Bold.otf"}[weight]
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)


def rotate_img(img):
    if ROTATE == "cw":
        return img.transpose(Image.Transpose.ROTATE_270)
    return img.transpose(Image.Transpose.ROTATE_90)


def rect_to_portrait(rect):
    """Đổi hình chữ nhật (x,y,w,h) từ toạ độ ngang sang toạ độ dọc của khung hình Kindle."""
    x, y, w, h = rect
    if ROTATE == "cw":
        return (H - y - h, x, h, w)
    return (y, W - x - w, h, w)


def gray16(img, dither=False):
    """Ép về 16 mức xám như e-ink. dither=True cho ảnh chụp."""
    img = img.convert("L")
    if not dither:
        return img.point(lambda v: min(255, int(round(v / 17.0)) * 17))
    pal = Image.new("P", (1, 1))
    pal.putpalette([c for i in range(16) for c in (i * 17,) * 3] + [0] * (768 - 48))
    q = img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG)
    return q.convert("L")


def save_png(img, path, dither=False):
    gray16(img, dither).save(path, optimize=True)


# ------------------------------------------------------------------ đồng hồ / pin
def clock_strip(hh, mm):
    w, h = CLOCK_RECT[2], CLOCK_RECT[3]
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    d.text((w // 2, h // 2 + 2), f"{hh:02d}:{mm:02d}", font=font("b", 112), fill=0, anchor="mm")
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
        bolt = [(cx + 3, cy - 10), (cx - 6, cy + 2), (cx, cy + 2), (cx - 3, cy + 10), (cx + 6, cy - 3), (cx, cy - 3)]
        d.polygon(bolt, fill=255, outline=0)
    d.text((w - 2, h // 2 + 1), f"{level}%", font=font("b", 24), fill=0, anchor="rm")
    return im


# ------------------------------------------------------------------ biểu tượng thời tiết
def weather_icon(draw, cx, cy, s, kind):
    def sun(x, y, r, rays=True):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=0)
        if rays:
            import math
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
        sun(cx - 10, cy - 10, 11)
        cloud(cx + 6, cy + 6, 0.9)
    elif kind == "cloud":
        cloud(cx, cy, 1.1)
    elif kind in ("rain", "storm"):
        cloud(cx, cy - 8, 1.0)
        if kind == "rain":
            for dx in (-14, 0, 14):
                draw.line((cx + dx + 4, cy + 14, cx + dx - 3, cy + 28), fill=0, width=4)
        else:
            bolt = [(cx + 4, cy + 8), (cx - 6, cy + 22), (cx, cy + 22), (cx - 4, cy + 34), (cx + 9, cy + 17), (cx + 2, cy + 17)]
            draw.polygon(bolt, fill=0)
    else:  # fog
        for i in range(4):
            draw.line((cx - 24 + (i % 2) * 6, cy - 14 + i * 10, cx + 24 - (i % 2) * 6, cy - 14 + i * 10), fill=0, width=4)


WMO = {0: ("Trời quang", "sun"), 1: ("Ít mây", "sun"), 2: ("Có mây", "partly"), 3: ("Nhiều mây", "cloud"),
       45: ("Sương mù", "fog"), 48: ("Sương mù", "fog"), 51: ("Mưa phùn", "rain"), 53: ("Mưa phùn", "rain"),
       55: ("Mưa phùn", "rain"), 56: ("Mưa phùn lạnh", "rain"), 57: ("Mưa phùn lạnh", "rain"),
       61: ("Mưa nhỏ", "rain"), 63: ("Mưa vừa", "rain"), 65: ("Mưa to", "rain"), 66: ("Mưa lạnh", "rain"),
       67: ("Mưa lạnh", "rain"), 80: ("Mưa rào", "rain"), 81: ("Mưa rào", "rain"), 82: ("Mưa rào to", "rain"),
       95: ("Dông", "storm"), 96: ("Dông, mưa đá", "storm"), 99: ("Dông, mưa đá", "storm")}
