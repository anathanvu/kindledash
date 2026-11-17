"""Âm lịch Việt Nam (múi giờ UTC+7) - thuật toán Hồ Ngọc Đức."""
import math

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]


def _jd_from_date(dd, mm, yy):
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def _new_moon(k):
    T = k / 1236.85
    T2, T3 = T * T, T * T * T
    dr = math.pi / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * T2 - 0.000000155 * T3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * T - 0.009173 * T2) * dr)
    M = 359.2242 + 29.10535608 * k - 0.0000333 * T2 - 0.00000347 * T3
    Mpr = 306.0253 + 385.81691806 * k + 0.0107306 * T2 + 0.00001236 * T3
    F = 21.2964 + 390.67050646 * k - 0.0016528 * T2 - 0.00000239 * T3
    c1 = (0.1734 - 0.000393 * T) * math.sin(M * dr) + 0.0021 * math.sin(2 * dr * M)
    c1 -= 0.4068 * math.sin(Mpr * dr) + 0.0161 * math.sin(dr * 2 * Mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * Mpr)
    c1 += 0.0104 * math.sin(dr * 2 * F) - 0.0051 * math.sin(dr * (M + Mpr))
    c1 -= 0.0074 * math.sin(dr * (M - Mpr)) + 0.0004 * math.sin(dr * (2 * F + M))
    c1 -= 0.0004 * math.sin(dr * (2 * F - M)) - 0.0006 * math.sin(dr * (2 * F + Mpr))
    c1 += 0.0010 * math.sin(dr * (2 * F - Mpr)) + 0.0005 * math.sin(dr * (2 * Mpr + M))
    if T < -11:
        dt = 0.001 + 0.000839 * T + 0.0002261 * T2 - 0.00000845 * T3 - 0.000000081 * T * T3
    else:
        dt = -0.000278 + 0.000265 * T + 0.000262 * T2
    return jd1 + c1 - dt


def _new_moon_day(k, tz):
    return int(_new_moon(k) + 0.5 + tz / 24)


def _sun_longitude(jdn, tz):
    T = (jdn - 2451545.5 - tz / 24) / 36525
    T2 = T * T
    dr = math.pi / 180
    M = 357.52910 + 35999.05030 * T - 0.0001559 * T2 - 0.00000048 * T * T2
    L0 = 280.46645 + 36000.76983 * T + 0.0003032 * T2
    dl = (1.914600 - 0.004817 * T - 0.000014 * T2) * math.sin(dr * M)
    dl += (0.019993 - 0.000101 * T) * math.sin(dr * 2 * M) + 0.000290 * math.sin(dr * 3 * M)
    L = (L0 + dl) * dr
    L -= math.pi * 2 * int(L / (math.pi * 2))
    return int(L / math.pi * 6)


def _lunar_month_11(yy, tz):
    off = _jd_from_date(31, 12, yy) - 2415021
    k = int(off / 29.530588853)
    nm = _new_moon_day(k, tz)
    if _sun_longitude(nm, tz) >= 9:
        nm = _new_moon_day(k - 1, tz)
    return nm


def _leap_month_offset(a11, tz):
    k = int((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    i = 1
    arc = _sun_longitude(_new_moon_day(k + i, tz), tz)
    while True:
        last = arc
        i += 1
        arc = _sun_longitude(_new_moon_day(k + i, tz), tz)
        if not (arc != last and i < 14):
            break
    return i - 1


def solar_to_lunar(dd, mm, yy, tz=7):
    """Trả về (ngày, tháng, năm, nhuận?) âm lịch."""
    day_number = _jd_from_date(dd, mm, yy)
    k = int((day_number - 2415021.076998695) / 29.530588853)
    month_start = _new_moon_day(k + 1, tz)
    if month_start > day_number:
        month_start = _new_moon_day(k, tz)
    a11 = _lunar_month_11(yy, tz)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = _lunar_month_11(yy - 1, tz)
    else:
        lunar_year = yy + 1
        b11 = _lunar_month_11(yy + 1, tz)
    lunar_day = day_number - month_start + 1
    diff = int((month_start - a11) / 29)
    leap = 0
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_diff = _leap_month_offset(a11, tz)
        if diff >= leap_diff:
            lunar_month = diff + 10
            if diff == leap_diff:
                leap = 1
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return lunar_day, lunar_month, lunar_year, leap


def year_name(lunar_year):
    return f"{CAN[(lunar_year + 6) % 10]} {CHI[(lunar_year + 8) % 12]}"


def day_name(dd, mm, yy):
    jd = _jd_from_date(dd, mm, yy)
    return f"{CAN[(jd + 9) % 10]} {CHI[(jd + 1) % 12]}"


def describe(dd, mm, yy):
    d, m, y, leap = solar_to_lunar(dd, mm, yy)
    return {"day": d, "month": m, "year": y, "leap": bool(leap),
            "year_name": year_name(y), "day_name": day_name(dd, mm, yy)}


if __name__ == "__main__":
    for t in [(17, 2, 2026), (29, 1, 2025), (16, 2, 2026), (17, 11, 2026), (10, 2, 2024)]:
        print(t, describe(*t))
