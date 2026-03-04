# analyzer/battery_logic.py — OBIXConfig Doctor
# ============================================================
# v2.2 FIX — เขียนใหม่ให้สมบูรณ์
# ก่อนหน้า: stub รองรับแค่ "4S"/"6S" → "ไม่ทราบแบตเตอรี่"
# หลังแก้:  parse ได้ทุกรูปแบบ คืน dict พร้อมใช้
# ============================================================
from __future__ import annotations
import re
from typing import Optional

_NOMINAL_V_PER_CELL = 3.7
_MAX_V_PER_CELL     = 4.2
_MIN_V_PER_CELL     = 3.5

_CELL_DESC = {
    1: "1S — Tiny whoop / micro indoor",
    2: "2S — Micro toothpick",
    3: "3S — Whoop / 3\" freestyle / micro cine",
    4: "4S — มาตรฐาน FPV 5\" (ที่นิยมมากที่สุด)",
    5: "5S — Mid-spec, ไม่ค่อยพบ",
    6: "6S — แรงขับสูง 5\"–10\" / long range",
    7: "7S — Specialty",
    8: "8S — Heavy lift / cinema drone",
}

_TYPICAL_MAH = {
    1: (250, 550),
    2: (350, 850),
    3: (450, 1800),
    4: (650, 2200),
    5: (1000, 2600),
    6: (2000, 6000),
    7: (2500, 8000),
    8: (3000, 10000),
}


def _parse_battery_string(battery: str):
    """
    Parse battery string → (cells, mAh)
    รองรับ: "4S", "4S 1500mAh", "4s1500", "6S 5000", "3"
    """
    if not battery:
        return None, None
    s = str(battery).upper().strip()

    # "4S 1500" หรือ "4S1500MAH"
    m = re.match(r'^(\d+)\s*S\s*(\d+)', s)
    if m:
        return int(m.group(1)), int(m.group(2))

    # "4S" เปล่าๆ
    m = re.match(r'^(\d+)\s*S', s)
    if m:
        return int(m.group(1)), None

    # ตัวเลขเดี่ยว
    m = re.match(r'^(\d+)$', s)
    if m:
        c = int(m.group(1))
        if 1 <= c <= 12:
            return c, None

    return None, None


def analyze_battery(battery: str) -> dict:
    """
    วิเคราะห์ battery string → dict
    Returns {"error": "..."} ถ้า parse ไม่ได้
    """
    cells, mah = _parse_battery_string(battery)

    if cells is None:
        return {"error": f"รูปแบบแบตผิด: '{battery}' — ใช้เช่น '4S', '4S 1500mAh'"}

    if not (1 <= cells <= 12):
        return {"error": f"จำนวน cell ผิดปกติ: {cells}S"}

    v_nom = round(cells * _NOMINAL_V_PER_CELL, 1)
    v_max = round(cells * _MAX_V_PER_CELL, 1)
    v_min = round(cells * _MIN_V_PER_CELL, 1)
    desc  = _CELL_DESC.get(cells, f"{cells}S — {cells} cell LiPo")
    mah_lo, mah_hi = _TYPICAL_MAH.get(cells, (500, 5000))

    mah_warning = False
    if mah is not None:
        mah_warning = not (mah_lo * 0.5 <= mah <= mah_hi * 1.5)

    label = f"{cells}S {mah}mAh" if mah else f"{cells}S"

    return {
        "cells":            cells,
        "mAh":              mah,
        "voltage_nominal":  v_nom,
        "voltage_max":      v_max,
        "voltage_min":      v_min,
        "label":            label,
        "description":      desc,
        "mah_typical_low":  mah_lo,
        "mah_typical_high": mah_hi,
        "mah_warning":      mah_warning,
    }


def get_battery_summary(battery: str) -> str:
    """คืน string สั้นสำหรับ UI"""
    result = analyze_battery(battery)
    if "error" in result:
        return str(battery)
    return f"{result['label']} ({result['voltage_nominal']}V nominal)"
