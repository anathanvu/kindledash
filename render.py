#!/usr/bin/env python3
"""Tạo info.png (cột thông tin 370x600, đã xoay cho Kindle) + data.json + index.html.
Chạy trong GitHub Actions mỗi ~15 phút. Mọi nguồn dữ liệu đều có dự phòng:
nguồn tự động -> manual.json -> giá trị lần build trước (data.json đã publish)."""
import argparse, json, os, re, sys, datetime as dt
import requests
from PIL import Image, ImageDraw
import common as C
import lunar

TZ = dt.timezone(dt.timedelta(hours=7))
UA = {"User-Agent": "Mozilla/5.0 (kindle-dashboard)"}
CFG = json.load(open(os.path.join(C.HERE, "config.json"), encoding="utf-8"))
DOW = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def log(*a):
    print("[render]", *a, file=sys.stderr)


def http(url, **kw):
    kw.setdefault("timeout", 20)
    kw.setdefault("headers", UA)
    r = requests.get(url, **kw) if kw.pop("method", "GET") == "GET" else requests.post(url, **kw)
    r.raise_for_status()
    return r


# ------------------------------------------------------------------ thời tiết (Open-Meteo, không cần key)
def get_weather():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&current=temperature_2m,relative_humidity_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           "&timezone=Asia%%2FBangkok&forecast_days=1") % (CFG["lat"], CFG["lon"])
    j = http(url).json()
    return {"temp": round(j["current"]["temperature_2m"]), "hum": j["current"]["relative_humidity_2m"],
            "code": j["current"]["weather_code"], "tmax": round(j["daily"]["temperature_2m_max"][0]),
            "tmin": round(j["daily"]["temperature_2m_min"][0]),
            "rain": j["daily"]["precipitation_probability_max"][0]}


# ------------------------------------------------------------------ giá vàng: thử lần lượt nhiều nguồn
def _to_trieu_luong(v):
    v = float(v)
    if v < 40e6:       # nhiều nguồn niêm yết theo chỉ
        v *= 10
    return round(v / 1e6, 1)


def gold_vnappmob():
    key = http("https://api.vnappmob.com/api/request_api_key?scope=gold").json()["results"]
    r = http("https://api.vnappmob.com/api/v2/gold/sjc", headers={**UA, "Authorization": "Bearer " + key}).json()["results"][0]
    return _to_trieu_luong(r["buy_1l"]), _to_trieu_luong(r["sell_1l"])


def gold_btmc():
    j = http("http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v").json()
    rows = j["DataList"]["Data"]
    for row in rows:
        for k, name in row.items():
            if k.startswith("@n_") and "SJC" in str(name).upper():
                n = k.split("_")[1]
                return _to_trieu_luong(row["@pb_" + n]), _to_trieu_luong(row["@ps_" + n])
    raise ValueError("không thấy dòng SJC")


def gold_sjc():
    r = http("https://sjc.com.vn/GoldPrice/Services/PriceService.ashx", method="POST",
             data={"method": "GetCurrentGoldPriceByBranch", "BranchId": "1"}).json()
    row = next(x for x in r["data"] if "SJC" in x.get("TypeName", "").upper())
    return _to_trieu_luong(row["BuyValue"]), _to_trieu_luong(row["SellValue"])


def get_gold():
    for fn in (gold_vnappmob, gold_btmc, gold_sjc):
        try:
            buy, sell = fn()
            if 20 < buy < 1000 and sell >= buy:
                log("gold OK:", fn.__name__, buy, sell)
                return {"buy": buy, "sell": sell, "src": fn.__name__}
        except Exception as e:
            log("gold FAIL:", fn.__name__, repr(e)[:120])
    return None


# ------------------------------------------------------------------ giá xăng
def fuel_vietfuel():
    j = http("https://vietfuel-api.tranqui.workers.dev/api/fuel-prices/petrolimex").json()
    return {x["name"]: int(x["region1"]) for x in j["data"]}   # Hà Nội = Vùng 1


def fuel_webgia():
    html = http("https://webgia.com/gia-xang-dau/petrolimex/").text
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        if len(cells) >= 2 and re.fullmatch(r"\d{2}[.,]\d{3}", cells[1]):
            out[cells[0]] = int(re.sub(r"\D", "", cells[1]))
    if not out:
        raise ValueError("không đọc được bảng")
    return out


def get_fuel():
    for fn in (fuel_vietfuel, fuel_webgia):
        try:
            prices = fn()
            log("fuel OK:", fn.__name__, len(prices), "mục")
            return {"prices": prices, "src": fn.__name__}
        except Exception as e:
            log("fuel FAIL:", fn.__name__, repr(e)[:120])
    return None


def pick_fuel(prices):
    res = []
    for want in CFG["fuel_show"]:
        for name, val in prices.items():
            if want["match"].lower() in name.lower():
                res.append((want["label"], val))
                break
    return res


# ------------------------------------------------------------------ gom dữ liệu + dự phòng
def previous_data():
    base = os.environ.get("PAGES_BASE_URL")
    if not base:
        return {}
    try:
        return http(base.rstrip("/") + "/data.json", timeout=15).json()
    except Exception as e:
        log("không đọc được data.json cũ:", repr(e)[:80])
        return {}


def collect(offline=False):
    prev = previous_data()
    manual = {}
    try:
        manual = json.load(open(os.path.join(C.HERE, "manual.json"), encoding="utf-8"))
    except Exception:
        pass
    d = {"stale": []}
    if offline:
        d["weather"] = {"temp": 24, "hum": 78, "code": 3, "tmax": 26, "tmin": 21, "rain": 30}
        d["gold"] = {"buy": 144.1, "sell": 147.1, "src": "mẫu"}
        d["fuel"] = {"prices": {"Xăng RON 95-III": 24330, "Xăng E5 RON 92-II": 23330}, "src": "mẫu"}
        return d
    for key, fn in (("weather", get_weather), ("gold", get_gold), ("fuel", get_fuel)):
        val = None
        try:
            val = fn()
        except Exception as e:
            log(key, "FAIL", repr(e)[:120])
        if val is None and key == "gold" and manual.get("gold"):
            val = {**manual["gold"], "src": "manual"}
        if val is None and key == "fuel" and manual.get("fuel"):
            val = {"prices": manual["fuel"], "src": "manual"}
        if val is None and prev.get(key):
            val = prev[key]
            d["stale"].append(key)
        d[key] = val
    return d


# ------------------------------------------------------------------ vẽ cột thông tin
def draw_info(d, now):
    im = Image.new("L", (C.INFO_W, C.H), 255)
    g = ImageDraw.Draw(im)
    X0, X1 = 12, C.INFO_W - 12
    GRAY, MID = 95, 140

    # ngày dương + âm
    g.text((X0, 128), f"{DOW[now.weekday()]}, {now:%d/%m/%Y}", font=C.font("b", 26), fill=0)
    lu = lunar.describe(now.day, now.month, now.year)
    mark = " (nhuận)" if lu["leap"] else ""
    g.text((X0, 162), f"Âm lịch {lu['day']}/{lu['month']}{mark} · {lu['year_name']}", font=C.font("m", 20), fill=GRAY)
    g.line((X0, 198, X1, 198), fill=MID, width=2)

    # thời tiết
    w = d.get("weather")
    if w:
        text, kind = C.WMO.get(w["code"], ("—", "cloud"))
        C.weather_icon(g, 52, 258, 64, kind)
        g.text((104, 204), f"{w['temp']}°", font=C.font("b", 60), fill=0)
        g.text((X1, 214), CFG["city"], font=C.font("m", 18), fill=GRAY, anchor="ra")
        g.text((X1, 238), f"Ẩm {w['hum']}%", font=C.font("m", 18), fill=GRAY, anchor="ra")
        g.text((104, 272), text, font=C.font("m", 21), fill=0)
        g.text((X0, 304), f"Cao {w['tmax']}° · Thấp {w['tmin']}° · Mưa {w['rain']}%", font=C.font("m", 19), fill=GRAY)
    else:
        g.text((X0, 240), "Thời tiết: chưa có dữ liệu", font=C.font("m", 20), fill=GRAY)
    g.line((X0, 336, X1, 336), fill=MID, width=2)

    # vàng
    gd = d.get("gold")
    star = "*" if "gold" in d["stale"] else ""
    g.text((X0, 344), f"{CFG['gold_label']} · triệu đ/lượng{star}", font=C.font("b", 16), fill=GRAY)
    if gd:
        g.text((X0, 368), "MUA", font=C.font("m", 15), fill=GRAY)
        g.text((X0, 384), f"{gd['buy']:.1f}".replace(".", ","), font=C.font("b", 44), fill=0)
        g.text((196, 368), "BÁN", font=C.font("m", 15), fill=GRAY)
        g.text((196, 384), f"{gd['sell']:.1f}".replace(".", ","), font=C.font("b", 44), fill=0)
    else:
        g.text((X0, 390), "chưa có dữ liệu", font=C.font("m", 20), fill=GRAY)
    g.line((X0, 446, X1, 446), fill=MID, width=2)

    # xăng
    fu = d.get("fuel")
    star = "*" if "fuel" in d["stale"] else ""
    g.text((X0, 454), f"XĂNG · đồng/lít{star}", font=C.font("b", 16), fill=GRAY)
    rows = pick_fuel(fu["prices"]) if fu else []
    for i, (label, val) in enumerate(rows[:2]):
        y = 480 + i * 33
        g.text((X0, y + 4), label, font=C.font("m", 20), fill=0)
        g.text((X1, y), f"{val:,}".replace(",", "."), font=C.font("b", 27), fill=0, anchor="ra")
    if not rows:
        g.text((X0, 486), "chưa có dữ liệu", font=C.font("m", 20), fill=GRAY)

    # chân trang (phần pin do Kindle tự dán)
    g.text((X0, 570), f"Cập nhật {now:%H:%M}", font=C.font("m", 15), fill=GRAY)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--offline", action="store_true", help="dùng số liệu mẫu (để xem thử)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    now = dt.datetime.now(TZ)
    d = collect(a.offline)
    info = draw_info(d, now)
    C.save_png(info.convert("L"), os.path.join(a.out, "info_landscape.png"))
    C.save_png(C.rotate_img(info), os.path.join(a.out, "info.png"))
    d["generated"] = now.isoformat(timespec="seconds")
    json.dump(d, open(os.path.join(a.out, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(a.out, "index.html"), "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>kindle dash</title>"
        "<body style='font-family:sans-serif'><h3>Cập nhật %s</h3>"
        "<img src=info_landscape.png style='border:1px solid #888'>"
        "<pre>%s</pre></body>" % (d["generated"], json.dumps(d, ensure_ascii=False, indent=1)))
    log("xong", d["generated"], "stale=", d["stale"])


if __name__ == "__main__":
    main()
