#!/usr/bin/env python3
"""Tạo info.png (cột thông tin, đã xoay cho Kindle) + data.json + index.html.
Chạy trong GitHub Actions mỗi ~15 phút. Dự phòng: nguồn tự động -> manual.json -> dữ liệu lần trước."""
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


def http(url, method="GET", **kw):
    kw.setdefault("timeout", 20)
    kw.setdefault("headers", UA)
    r = requests.request(method, url, **kw)
    r.raise_for_status()
    return r


def get_weather():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&current=temperature_2m,relative_humidity_2m,weather_code"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           "&timezone=Asia%%2FBangkok&forecast_days=4") % (CFG["lat"], CFG["lon"])
    j = http(url).json()
    dl = j["daily"]
    days = [{"date": dl["time"][i], "code": dl["weather_code"][i], "tmax": round(dl["temperature_2m_max"][i]),
             "tmin": round(dl["temperature_2m_min"][i]), "rain": dl["precipitation_probability_max"][i]}
            for i in range(len(dl["time"]))]
    return {"temp": round(j["current"]["temperature_2m"]), "hum": j["current"]["relative_humidity_2m"],
            "code": j["current"]["weather_code"], "tmax": days[0]["tmax"], "tmin": days[0]["tmin"],
            "rain": days[0]["rain"], "days": days[1:4]}


def _to_trieu_luong(v):
    v = float(v)
    if v < 40e6:
        v *= 10
    return round(v / 1e6, 1)


def gold_vnappmob():
    key = http("https://api.vnappmob.com/api/request_api_key?scope=gold").json()["results"]
    r = http("https://api.vnappmob.com/api/v2/gold/sjc", headers={**UA, "Authorization": "Bearer " + key}).json()["results"][0]
    return _to_trieu_luong(r["buy_1l"]), _to_trieu_luong(r["sell_1l"])


def gold_btmc():
    j = http("http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v").json()
    for row in j["DataList"]["Data"]:
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
            log("gold FAIL:", fn.__name__, "giá vô lý", buy, sell)
        except Exception as e:
            log("gold FAIL:", fn.__name__, repr(e)[:120])
    return None


def usd_vcb():
    x = http("https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx").text
    m = re.search(r'<Exrate[^>]*CurrencyCode="USD"[^>]*>', x)
    num = lambda k: int(float(re.search(k + r'="([\d,.]+)"', m.group(0)).group(1).replace(",", "")))
    return {"buy": num("Buy"), "sell": num("Sell"), "src": "Vietcombank"}


def usd_erapi():
    v = http("https://open.er-api.com/v6/latest/USD").json()["rates"]["VND"]
    return {"buy": None, "sell": int(round(v)), "src": "thị trường"}


def get_usd():
    for fn in (usd_vcb, usd_erapi):
        try:
            r = fn()
            if 15000 < r["sell"] < 60000:
                log("usd OK:", fn.__name__, r)
                return r
            log("usd FAIL:", fn.__name__, "giá vô lý", r)
        except Exception as e:
            log("usd FAIL:", fn.__name__, repr(e)[:120])
    return None


def fuel_vietfuel():
    j = http("https://vietfuel-api.tranqui.workers.dev/api/fuel-prices/petrolimex").json()
    return {x["name"]: int(x["region1"]) for x in j["data"]}


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
        pats = want["match"] if isinstance(want["match"], list) else [want["match"]]
        hit = None
        for pat in pats:
            hit = next(((n, v) for n, v in prices.items() if pat.lower() in n.lower()), None)
            if hit:
                break
        if hit:
            res.append((want["label"], hit[1]))
    return res


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
    d = {"stale": []}
    if offline:
        d["weather"] = {"temp": 24, "hum": 78, "code": 3, "tmax": 26, "tmin": 21, "rain": 30}
        d["gold"] = {"buy": 144.1, "sell": 147.1, "src": "mẫu"}
        d["fuel"] = {"prices": {"Xăng E10 RON 95 mức 3": 19840, "Xăng E5 RON 92 mức 2": 19390}, "src": "mẫu"}
        d["usd"] = {"buy": 26128, "sell": 26398, "src": "Vietcombank"}
        d["weather"]["days"] = [{"date": "2026-11-18", "code": 2, "tmax": 30, "tmin": 23, "rain": 10},
                                {"date": "2026-11-19", "code": 61, "tmax": 27, "tmin": 22, "rain": 70},
                                {"date": "2026-11-20", "code": 3, "tmax": 25, "tmin": 20, "rain": 20}]
        return d
    prev = previous_data()
    try:
        manual = json.load(open(os.path.join(C.HERE, "manual.json"), encoding="utf-8"))
    except Exception:
        manual = {}
    for key, fn in (("weather", get_weather), ("gold", get_gold), ("usd", get_usd), ("fuel", get_fuel)):
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


DOW_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def vn(n, dec=0):
    """Định dạng số kiểu Việt Nam: 26.398 / 134,7"""
    t = f"{n:,.{dec}f}"
    return t.replace(",", "§").replace(".", ",").replace("§", ".")


def draw_info(d, now):
    im = Image.new("L", (C.INFO_W, C.H), 255)
    g = ImageDraw.Draw(im)
    W = C.INFO_W
    X0, X1 = 16, W - 16
    INK, GRAY, LIGHT, RULE = 0, 85, 150, 170
    COLW = (X1 - X0) // 2
    CB = X0 + COLW + 8                       # cột phải

    def rule(y):
        g.line((X0, y, X1, y), fill=RULE, width=2)

    def label(y, left, right=""):
        g.text((X0, y), left, font=C.font("b", 14), fill=GRAY)
        if right:
            g.text((X1, y), right, font=C.font("m", 13), fill=LIGHT, anchor="ra")

    # vạch ngăn mảnh giữa ảnh và thông tin
    g.line((0, 14, 0, C.H - 14), fill=RULE, width=2)

    # --- NGÀY (đồng hồ y 0-118 do Kindle tự dán)
    g.text((W // 2, 132), f"{DOW[now.weekday()]}, {now:%d/%m/%Y}", font=C.font("b", 25), fill=INK, anchor="mm")
    lu = lunar.describe(now.day, now.month, now.year)
    mark = " nhuận" if lu["leap"] else ""
    g.text((W // 2, 160), f"Âm lịch {lu['day']}/{lu['month']}{mark} · ngày {lu['day_name']} · năm {lu['year_name']}",
           font=C.font("m", 15), fill=GRAY, anchor="mm")
    rule(178)

    # --- THỜI TIẾT
    w = d.get("weather")
    label(186, "THỜI TIẾT", CFG["city"])
    if w:
        text, kind = C.WMO.get(w["code"], ("—", "cloud"))
        im.paste(C.weather_icon_img(kind, 60), (X0 - 4, 206))
        g.text((X0 + 62, 198), f"{w['temp']}°", font=C.font("b", 52), fill=INK)
        g.text((X0 + 65, 255), text, font=C.font("m", 17), fill=INK)
        g.text((X1, 208), f"↑{w['tmax']}°  ↓{w['tmin']}°", font=C.font("b", 19), fill=INK, anchor="ra")
        g.text((X1, 235), f"Độ ẩm {w['hum']}%", font=C.font("m", 15), fill=GRAY, anchor="ra")
        g.text((X1, 255), f"Khả năng mưa {w['rain']}%", font=C.font("m", 15), fill=GRAY, anchor="ra")
        days = w.get("days") or []
        cw = (X1 - X0) / 3
        for i, dd in enumerate(days[:3]):
            x0 = X0 + i * cw
            g.rounded_rectangle((x0 + 3, 284, x0 + cw - 3, 350), radius=8, outline=RULE, width=2)
            dt_ = dt.date.fromisoformat(dd["date"])
            g.text((x0 + cw / 2, 296), f"{DOW_SHORT[dt_.weekday()]} · {dt_:%d/%m}", font=C.font("b", 13), fill=GRAY, anchor="mm")
            ik = C.WMO.get(dd["code"], ("", "cloud"))[1]
            im.paste(C.weather_icon_img(ik, 40), (int(x0 + 8), 305))
            g.text((x0 + cw - 10, 307), f"{dd['tmax']}°/{dd['tmin']}°", font=C.font("b", 17), fill=INK, anchor="ra")
            g.text((x0 + cw - 10, 329), f"mưa {dd['rain']}%", font=C.font("m", 12), fill=GRAY, anchor="ra")
    else:
        g.text((X0, 240), "chưa có dữ liệu", font=C.font("m", 18), fill=GRAY)
    rule(358)

    # --- THỊ TRƯỜNG: bảng 3 cột (tên | cột 1 | cột 2), số căn phải thẳng hàng
    C1, C2 = X0 + 252, X1                    # mép phải 2 cột số
    def head(y, t1, t2):
        g.text((C1, y), t1, font=C.font("b", 12), fill=LIGHT, anchor="ra")
        g.text((C2, y), t2, font=C.font("b", 12), fill=LIGHT, anchor="ra")

    def row(y, name, sub, vals, size, stale):
        g.text((X0, y), name + ("*" if stale else ""), font=C.font("b", 19), fill=INK)
        g.text((X0, y + 25), sub, font=C.font("m", 12), fill=GRAY)
        for edge, v in zip((C1, C2), vals):
            g.text((edge, y - 3), v, font=C.font("b", size), fill=INK, anchor="ra")

    g.text((X0, 366), "THỊ TRƯỜNG", font=C.font("b", 14), fill=GRAY)
    head(368, "MUA", "BÁN")
    gd = d.get("gold")
    row(388, "Vàng SJC", "triệu đồng/lượng",
        [vn(gd["buy"], 1), vn(gd["sell"], 1)] if gd else ["—", "—"], 32, "gold" in d["stale"])
    g.line((X0, 434, X1, 434), fill=220, width=1)
    us = d.get("usd")
    if us:
        uv = [vn(us["buy"]) if us.get("buy") else "—", vn(us["sell"])]
    else:
        uv = ["—", "—"]
    row(444, "USD", f"đồng · {(us or {}).get('src', '')}", uv, 28, "usd" in d["stale"])
    g.line((X0, 490, X1, 490), fill=220, width=1)
    fu = d.get("fuel")
    rows = pick_fuel(fu["prices"]) if fu else []
    caps = [lb for lb, _ in rows] + ["", ""]
    head(498, caps[0].upper(), caps[1].upper())
    row(516, "Xăng", "đồng/lít · Petrolimex", [vn(v) for _, v in rows] or ["—", "—"], 26, "fuel" in d["stale"])
    rule(566)

    # --- CHỮ KÝ (pin ở góc phải do Kindle dán)
    g.text((X0, 571), C.BRAND, font=C.font("b", 13), fill=GRAY)
    g.text((X0, 587), f"© {now.year} {C.OWNER} · cập nhật {now:%H:%M}", font=C.font("m", 11), fill=LIGHT)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    now = dt.datetime.now(TZ)
    d = collect(a.offline)
    info = draw_info(d, now)
    C.save_png(info, os.path.join(a.out, "info_landscape.png"))
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
