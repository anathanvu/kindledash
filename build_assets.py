#!/usr/bin/env python3
"""Tạo toàn bộ ảnh nằm SẴN TRÊN KINDLE (ảnh gia đình không bao giờ lên GitHub):
  img/photo.png   cột ảnh gia đình của dashboard
  img/rest.png    ảnh toàn màn hình cho chế độ nghỉ
  clock/HHMM.png  1440 ảnh đồng hồ (mỗi phút 1 ảnh, Kindle chỉ việc dán)
  battery/bat_N.png, bat_N_c.png   biểu tượng pin 0..100% (thường / đang sạc)
  layout.env      toạ độ để script shell dán ảnh
Dùng:  python3 build_assets.py family.jpg --out ../kindle/kdash
Chỉnh khung cắt: --photo-cx/--rest-cy (0..1 = vị trí tâm khuôn mặt trong ảnh gốc)."""
import argparse, os
from PIL import Image, ImageOps
import common as C


def crop_to(img, w, h, cx, cy):
    """Cắt vùng tỉ lệ w:h lớn nhất, tâm tại (cx,cy) tính theo tỉ lệ ảnh gốc."""
    iw, ih = img.size
    r = w / h
    cw, ch = (iw, int(iw / r)) if iw / ih < r else (int(ih * r), ih)
    x0 = min(max(int(cx * iw - cw / 2), 0), iw - cw)
    y0 = min(max(int(cy * ih - ch / 2), 0), ih - ch)
    return img.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.Resampling.LANCZOS)


def prep(img):
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    g = g.point(lambda v: int(255 * (v / 255) ** 0.85))      # sáng hơn một chút cho e-ink
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--out", default="../kindle/kdash")
    ap.add_argument("--photo-cx", type=float, default=0.47)
    ap.add_argument("--photo-cy", type=float, default=0.5)
    ap.add_argument("--rest-cx", type=float, default=0.5)
    ap.add_argument("--rest-cy", type=float, default=0.39)
    a = ap.parse_args()
    for sub in ("img", "clock", "battery"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    src = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")

    panel = prep(crop_to(src, C.PHOTO_W, C.H, a.photo_cx, a.photo_cy))
    C.save_png(C.rotate_img(panel), os.path.join(a.out, "img/photo.png"), dither=True)
    C.save_png(panel, os.path.join(a.out, "img/photo_landscape_preview.png"), dither=True)
    rest = prep(crop_to(src, C.W, C.H, a.rest_cx, a.rest_cy))
    C.save_png(C.rotate_img(rest), os.path.join(a.out, "img/rest.png"), dither=True)
    C.save_png(rest, os.path.join(a.out, "img/rest_landscape_preview.png"), dither=True)

    for h in range(24):
        for m in range(60):
            C.save_png(C.rotate_img(C.clock_strip(h, m)), os.path.join(a.out, f"clock/{h:02d}{m:02d}.png"))
    for lv in range(101):
        C.save_png(C.rotate_img(C.battery_strip(lv, False)), os.path.join(a.out, f"battery/bat_{lv}.png"))
        C.save_png(C.rotate_img(C.battery_strip(lv, True)), os.path.join(a.out, f"battery/bat_{lv}_c.png"))

    px, py, _, _ = C.rect_to_portrait((0, 0, C.PHOTO_W, C.H))
    ix, iy, _, _ = C.rect_to_portrait((C.INFO_X, 0, C.INFO_W, C.H))
    cx, cy, _, _ = C.rect_to_portrait(C.CLOCK_RECT)
    bx, by, _, _ = C.rect_to_portrait(C.BATT_RECT)
    with open(os.path.join(a.out, "layout.env"), "w") as f:
        f.write(f"# Sinh tự động bởi build_assets.py (KDASH_ROTATE={C.ROTATE}) - đừng sửa tay\n")
        for k, v in dict(PHOTO_X=px, PHOTO_Y=py, INFO_X=ix, INFO_Y=iy, CLOCK_X=cx, CLOCK_Y=cy, BAT_X=bx, BAT_Y=by).items():
            f.write(f"{k}={v}\n")
    print("xong ->", a.out)


if __name__ == "__main__":
    main()
