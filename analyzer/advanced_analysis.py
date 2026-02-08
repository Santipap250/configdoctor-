# analyzer/advanced_analysis.py
# เพิ่มการคำนวณเชิงประมาณ (heuristic) เพื่อให้ผลวิเคราะห์ "ฉลาด" ขึ้น
import math

GRAVITY = 9.80665

def parse_battery_s(batt_str):
    """รับ '4S' -> 4, '6S' -> 6, ถ้าไม่รู้คืน 4"""
    if not batt_str:
        return 4
    s = ''.join([c for c in batt_str.upper() if c.isdigit()])
    try:
        return int(s) if s else 4
    except Exception:
        return 4

def default_capacity_by_size(size_inch):
    """ประมาณความจุก้อนแบตเตอรี่ตามขนาดโดรน (mAh) — ใช้เป็นค่าเริ่มต้นถ้า user ไม่ระบุ"""
    s = float(size_inch or 5)
    if s <= 2.5: return 300
    if s <= 3.5: return 650
    if s <= 4.5: return 850
    if s <= 5.5: return 1500
    if s <= 6.5: return 1800
    if s <= 7.5: return 3000
    return 4000

def energy_wh_from_mAh_and_cells(mAh, cells):
    """ประมาณ Wh = (mAh/1000) * (cells * 3.7)"""
    v = cells * 3.7
    return (mAh / 1000.0) * v

def estimate_hover_power_w(weight_g, style="freestyle", thrust_ratio=1.0):
    """
    heuristic: วัดเฉลี่ยพลังไฟฟ้าที่ต้องใช้ในการ hover (W)
    - base W/kg ขึ้นกับ style
    - ปรับตาม TWR (thrust_ratio) เล็กน้อย (ถ้ามีสูง -> มักใช้กำลังมากขึ้นเมื่อ aggressive)
    """
    wkg_map = {
        "freestyle": 220,   # W per kg (typical freestyle)
        "racing": 300,
        "longrange": 140,
        "mini": 180,
        "micro": 120,
        "default": 200
    }
    style_key = style.lower() if style else "default"
    base = wkg_map.get(style_key, wkg_map["default"])
    weight_kg = max(0.001, weight_g / 1000.0)
    # if thrust ratio >> 1, assume we will use more power during aggressive flight.
    twr_factor = 1.0 + max(0.0, (thrust_ratio - 1.2) * 0.25)
    return base * weight_kg * twr_factor

def twr_classification(thrust_ratio):
    """ให้ label แบบง่าย"""
    if thrust_ratio <= 1.2:
        return "Low (underpowered) — เหมาะสำหรับนิ่งมาก, อาจไม่เพียงพอสำหรับท่า"
    if thrust_ratio <= 1.6:
        return "Moderate — เหมาะสำหรับบินทั่วไป / cinematic"
    if thrust_ratio <= 2.0:
        return "Good — เหมาะกับ freestyle และส่วนใหญ่"
    return "High — เกินพอสำหรับ aggressive / racing (ระวังแบตและความร้อน)"

def suggest_motor_kv(size_inch, battery_s, weight_g):
    """
    ให้คำแนะนำ KV แบบกว้าง ๆ ตามขนาด/แบต:
    - This is heuristic, not exact.
    """
    s = float(size_inch or 5)
    cells = parse_battery_s(battery_s)
    # typical mapping:
    if s <= 3.5:
        return "2000-4500 KV (Whoops & toothpick)"
    if s <= 4.5:
        # 3-4s
        if cells >= 6: return "1200-1700 KV (6S cine/long), 1800-2600 KV (4S freestyle)"
        return "1800-2600 KV (4S freestyle)"
    if s <= 5.5:
        if cells >= 6: return "1400-2000 KV (6S long/freestyle)"
        return "2200-2600 KV (4S freestyle) or 1900-2300 (balanced)"
    if s <= 7.5:
        return "500-900 KV (6S long-range), 900-1600 KV (heavy 4S)"
    return "300-800 KV (big props / long-range)"
    
def estimate_power_and_runtime(size_inch, weight_g, battery_s, battery_mAh=None, thrust_ratio=1.0, style="freestyle"):
    """
    คืน dict:
      - cells, mAh (used), Wh
      - est_hover_power_w (single estimate)
      - est_flight_time_min (estimate)
      - est_range_power_w (low/high) optional
    """
    cells = parse_battery_s(battery_s)
    if battery_mAh is None:
        battery_mAh = default_capacity_by_size(size_inch)

    wh = energy_wh_from_mAh_and_cells(battery_mAh, cells)
    est_power_w = estimate_hover_power_w(weight_g, style, thrust_ratio)
    # give a range: conservative (hover) and aggressive (x1.4)
    aggressive_power = est_power_w * 1.4
    # ensure non-zero
    est_time_min = max(1, (wh / max(1e-6, est_power_w)) * 60.0)
    est_time_min_aggr = max(1, (wh / max(1e-6, aggressive_power)) * 60.0)

    return {
        "cells": cells,
        "battery_mAh_used": battery_mAh,
        "battery_wh": round(wh, 2),
        "est_hover_power_w": round(est_power_w, 1),
        "est_aggressive_power_w": round(aggressive_power, 1),
        "est_flight_time_min": int(est_time_min),
        "est_flight_time_min_aggressive": int(est_time_min_aggr)
    }

def make_advanced_report(size, weight_g, battery_s, prop_result, style):
    """
    รวมทุกอย่างเป็น dict ที่จะ merge เข้ากับ analysis
    prop_result: ต้องมี prop_result['effect']['motor_load'] (เดิมมี)
    """
    thr_load = 0.0
    try:
        thr_load = float(prop_result.get("effect", {}).get("motor_load", 0))
    except Exception:
        thr_load = 0.0

    # ถ้าฟังก์ชันเดิมมีการคำนวณ thrust_ratio ให้ใช้ ถ้าไม่ใช้ thr_load heuristic
    # NOTE: caller ควรส่ง thrust_ratio ถ้ามี
    thrust_ratio = prop_result.get("thrust_ratio") or thr_load or 1.0
    # normalize minimal
    try:
        thrust_ratio = float(thrust_ratio)
    except Exception:
        thrust_ratio = 1.0

    power_info = estimate_power_and_runtime(size, weight_g, battery_s, None, thrust_ratio, style)
    kv_suggestion = suggest_motor_kv(size, battery_s, weight_g)
    twr_note = twr_classification(thrust_ratio)

    # prop recommendation: simple heuristics
    prop_notes = []
    grip = prop_result.get("effect", {}).get("grip", "unknown")
    noise = prop_result.get("effect", {}).get("noise", "unknown")
    ml = prop_result.get("effect", {}).get("motor_load", 0)
    if ml > 8:
        prop_notes.append("แรงชัดเจน — อาจทำให้มอเตอร์ทำงานหนัก; พิจารณาใช้ใบพัดขนาดเล็กลงหรือ KV ต่ำลง")
    elif ml < 3:
        prop_notes.append("โหลดมอเตอร์ต่ำ — อาจต้องใบพัดมี pitch สูงขึ้นเพื่อแรงฉุดเพิ่มขึ้น")
    else:
        prop_notes.append("โหลดมอเตอร์ปานกลาง — ค่าที่สมดุล")

    # basic warnings
    warnings = []
    if power_info["est_hover_power_w"] * 1.4 > 350:  # arbitrary threshold high power
        warnings.append("เครื่องอาจใช้กำลังสูง — ตรวจสอบ ESC rating และสายไฟ")
    size_val = float(size or 5)
if power_info["battery_mAh_used"] < 500 and size_val > 4.5:
    warnings.append("แบตเตอรี่ความจุน้อยสำหรับขนาดนี้ — แนะนำความจุสูงขึ้นเพื่อเวลาบินที่ปลอดภัย")

    return {
        "advanced": {
            "power": power_info,
            "kv_suggestion": kv_suggestion,
            "twr_note": twr_note,
            "prop_notes": prop_notes,
            "warnings_advanced": warnings,
            "thrust_ratio": round(thrust_ratio, 2)
        }
    }