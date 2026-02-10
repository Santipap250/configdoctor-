# analyzer/advanced_analysis.py
"""
Advanced analysis v1.0+ for OBIXConfig Doctor (full, engineering-focused).
วางไฟล์นี้ที่ analyzer/advanced_analysis.py (แทนที่ไฟล์เดิมได้)
ฟังก์ชันหลัก: make_advanced_report(...)
- รับ input หลัก: size (inch), weight_g, battery_s ("4S"), prop_result (จาก analyze_propeller),
  style (string)
- optional: battery_mAh, motor_count, measured_thrust_per_motor_g, motor_kv, esc_current_limit_a
- คืนค่า: dict {"advanced": { ... }} — โครงที่ template / API ใช้งานได้เลย
Design goals:
- defensive (ไม่ให้เว็บล่มเมื่อ input ขาด/ผิด)
- explainable: ค่า +คำอธิบาย (verdicts/warnings)
- diagnostics: ค่า internal สำหรับ debug/log
"""

from typing import Dict, Any, Optional, List, Tuple
import math
import logging

logger = logging.getLogger("advanced_analysis")
# If caller hasn't configured logging, keep it quiet but allow prints during dev.
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# ---------- Constants & heuristics ----------
NOMINAL_CELL_V = 3.7  # 単セル平均電圧 (approx)
# default mAh guesses by typical frame size (fallback)
_DEFAULT_BATT_MAH_BY_SIZE = {
    2.5: {3: 450, 4: 450},
    3.0: {3: 550, 4: 650},
    3.5: {3: 650, 4: 850},
    4.0: {3: 850, 4: 1000},
    5.0: {4: 1500, 5: 1300, 6: 1100},
    6.0: {4: 1800, 5: 1500, 6: 1300},
    7.0: {5: 2200, 6: 1800, 7: 1500},
    8.0: {6: 3000, 7: 2200, 8: 1800}
}

# heuristic power W per kg by flight style (hover estimate)
POWER_W_PER_KG = {
    "freestyle": 550.0,
    "racing": 700.0,
    "longrange": 300.0,
    "cine": 350.0,
    "micro": 420.0,
}

# thresholds for human-readable classifications
HOVER_THRESHOLDS = {
    "excellent": 0.30,  # hover throttle fraction < 0.30 => excellent margin
    "good": 0.45,
    "poor": 0.60
}

# C-rating safety thresholds
C_SAFE = 20.0
C_HIGH = 35.0
C_DANGER = 50.0

# motor load thresholds (g per motor)
MOTOR_SAFE_G = 250.0
MOTOR_HIGH_G = 450.0

# helper: clamp
def _clamp(x, a, b):
    return max(a, min(b, x))

# helper: convert battery string "4S" -> int
def _cells_from_str(s: str) -> int:
    try:
        cells = int(str(s).upper().replace("S", "").strip())
        if cells < 3:
            return 3
        if cells > 8:
            return 8
        return cells
    except Exception:
        return 4

# fallback guess battery mAh from frame size
def _guess_batt_mAh(size_inch: float) -> int:
    try:
        keys = sorted(_DEFAULT_BATT_MAH_BY_SIZE.keys())
        closest = min(keys, key=lambda k: abs(k - size_inch))
        return int(_DEFAULT_BATT_MAH_BY_SIZE.get(closest, 1500))
    except Exception:
        return 1500

# attempt to estimate thrust-per-motor from prop_result or heuristics
def _estimate_thrust_per_motor(prop_result: Dict[str, Any], size_inch: float, blades: int) -> float:
    # prefer explicit value in prop_result.effect.motor_load (grams per motor)
    try:
        eff = prop_result.get("effect", {}) if isinstance(prop_result, dict) else {}
        m_load = eff.get("motor_load")
        if m_load:
            return float(m_load)
    except Exception:
        pass

    # heuristic fallback: approximate by prop size & blades
    # NOTE: these are coarse approximations for desktop analysis only
    # basic tiers:
    if size_inch <= 3.5:
        base = 220.0
    elif size_inch <= 5.0:
        base = 400.0
    elif size_inch <= 6.0:
        base = 520.0
    else:
        base = 700.0

    # more blades -> slightly more static thrust (rough)
    blade_factor = 1.0 + (0.08 * (blades - 2))
    return round(base * blade_factor, 1)

def _format_minutes(m: float) -> int:
    try:
        return int(max(0, round(m)))
    except Exception:
        return 0

# ---------- core function ----------
def make_advanced_report(
    size: float,
    weight_g: float,
    battery_s: str,
    prop_result: Dict[str, Any],
    style: str,
    battery_mAh: Optional[int] = None,
    motor_count: int = 4,
    measured_thrust_per_motor_g: Optional[float] = None,
    motor_kv: Optional[int] = None,
    esc_current_limit_a: Optional[float] = None,
    blades: Optional[int] = None
) -> Dict[str, Any]:
    """Return an 'advanced' analysis dict.

    Fields returned (top-level 'advanced'):
      - power: {cells, battery_mAh_used, battery_wh, est_hover_power_w,
                est_aggressive_power_w, est_flight_time_min, est_flight_time_min_aggressive}
      - thrust_ratio (TWR)
      - hover_throttle_percent
      - efficiency_class (excellent/good/poor/danger)
      - motor_health, battery_health (safe/high_load/danger)
      - flight_profile, twr_note, kv_suggestion
      - prop_notes (list)
      - warnings_advanced (list of {level,msg})
      - _diagnostics (internal numbers)
    """
    advanced: Dict[str, Any] = {}
    try:
        # sanitise
        cells = _cells_from_str(battery_s)
        size = float(size or 0)
        weight_g = float(weight_g or 0)
        motor_count = int(motor_count or 4)
        blades = int(blades) if blades else None

        # battery mAh: use provided else guess
        if battery_mAh and isinstance(battery_mAh, int) and battery_mAh > 0:
            batt_mAh = int(battery_mAh)
        else:
            batt_mAh = _guess_batt_mAh(size, cells)

        # battery Wh
        pack_voltage = cells * NOMINAL_CELL_V
        batt_wh = (batt_mAh / 1000.0) * pack_voltage

        # thrust per motor: prefer measured param, then prop_result, then heuristic
        if measured_thrust_per_motor_g and measured_thrust_per_motor_g > 0:
            thrust_per_motor_g = float(measured_thrust_per_motor_g)
        else:
            thrust_per_motor_g = _estimate_thrust_per_motor(prop_result or {}, size, blades or 2)

        # total thrust and TWR
        total_thrust_g = thrust_per_motor_g * max(1, motor_count)
        # avoid divide by zero
        twr = (total_thrust_g / weight_g) if weight_g > 0 else float('inf')

        # hover throttle fraction (weight / available thrust)
        hover_throttle = (weight_g / total_thrust_g) if total_thrust_g > 0 else 1.0
        hover_throttle_pct = round(hover_throttle * 100.0, 1)

        # efficiency class based on hover throttle
        if hover_throttle < HOVER_THRESHOLDS["excellent"]:
            efficiency_class = "excellent"
        elif hover_throttle < HOVER_THRESHOLDS["good"]:
            efficiency_class = "good"
        elif hover_throttle < HOVER_THRESHOLDS["poor"]:
            efficiency_class = "poor"
        else:
            efficiency_class = "danger"

        # estimate power: baseline W/kg from style (hover)
        p_per_kg = POWER_W_PER_KG.get(style, POWER_W_PER_KG.get("freestyle", 450.0))
        weight_kg = max(0.001, weight_g / 1000.0)
        est_hover_power_w = p_per_kg * weight_kg
        # apply tweak based on thrust margin: if TWR high, less sustained power to hover,
        # if low, more power (inefficient). We'll correct by a small factor.
        # factor range roughly 0.85 .. 1.35
        try:
            margin_factor = _clamp(1.0 - (1.0 - min(twr, 3.0))/6.0, 0.7, 1.3)
        except Exception:
            margin_factor = 1.0
        est_hover_power_w = est_hover_power_w * margin_factor

        # aggressive power (peak)
        est_aggressive_power_w = est_hover_power_w * 1.8
        # average cruise-like power (slightly above hover)
        avg_power_for_flight_w = est_hover_power_w * 1.12

        # estimate flight time in minutes (use batt_wh / power)
        est_flight_time_min = _format_minutes((batt_wh / avg_power_for_flight_w) * 60.0) if avg_power_for_flight_w > 0 else 0
        est_flight_time_min_aggr = _format_minutes((batt_wh / est_aggressive_power_w) * 60.0) if est_aggressive_power_w > 0 else 0

        # current draw A and C-rating required
        est_hover_current_a = (est_hover_power_w / pack_voltage) if pack_voltage > 0 else 0.0
        est_aggr_current_a = (est_aggressive_power_w / pack_voltage) if pack_voltage > 0 else 0.0
        batt_a_available = batt_mAh / 1000.0 if batt_mAh > 0 else 0.0
        c_required_hover = (est_hover_current_a / batt_a_available) if batt_a_available > 0 else None
        c_required_aggr = (est_aggr_current_a / batt_a_available) if batt_a_available > 0 else None

        # per-motor current (approx): divide total current by motor_count
        per_motor_hover_a = (est_hover_current_a / motor_count) if motor_count > 0 else 0.0
        per_motor_aggr_a = (est_aggr_current_a / motor_count) if motor_count > 0 else 0.0

        # motor stress by thrust-per-motor
        motor_load_g = thrust_per_motor_g
        if motor_load_g < MOTOR_SAFE_G:
            motor_health = "safe"
        elif motor_load_g < MOTOR_HIGH_G:
            motor_health = "high_load"
        else:
            motor_health = "danger"

        # battery health via C required
        if c_required_hover is None:
            battery_health = "unknown"
        else:
            if c_required_hover < C_SAFE:
                battery_health = "safe"
            elif c_required_hover < C_HIGH:
                battery_health = "high_load"
            else:
                battery_health = "danger"

        # ESC current limit check (if provided)
        esc_flag = None
        if esc_current_limit_a:
            # if per-motor expected current exceed ESC limit -> warn
            if per_motor_aggr_a > esc_current_limit_a * 0.9:
                esc_flag = "warning"
            elif per_motor_aggr_a > esc_current_limit_a:
                esc_flag = "danger"
            else:
                esc_flag = "ok"

        # KV suggestion (coarse)
        if size <= 3.5:
            kv_suggestion = "2300-4200"
        elif size <= 5.0:
            kv_suggestion = "1500-2800"
        elif size <= 6.0:
            kv_suggestion = "1200-2000"
        else:
            kv_suggestion = "800-1400"

        # TWR note: human readable advice
        if twr == float('inf'):
            twr_note = "น้ำหนักเป็น 0 — ตรวจสอบค่าน้ำหนัก"
        elif twr >= 2.5:
            twr_note = "แรงเหลือสำหรับ freestyle/racing และ recovery ดี"
        elif twr >= 2.0:
            twr_note = "เพียงพอสำหรับ cinematic/long-range และการบินนิ่ง"
        elif twr >= 1.2:
            twr_note = "พอสู้ได้ แต่ไม่มี margin สำหรับท่าแอ็กทีฟ"
        else:
            twr_note = "แรงไม่พอ — แนะนำลดน้ำหนักหรือเพิ่ม thrust (มอเตอร์/ใบพัด/แบต)"

        # flight profile suggestion
        if twr > 2.5 and efficiency_class in ("excellent", "good"):
            flight_profile = "Freestyle / Racing"
        elif twr >= 2.0:
            flight_profile = "Cinematic / Long-range"
        elif twr >= 1.2:
            flight_profile = "General / Light freestyle"
        else:
            flight_profile = "Not recommended (low thrust)"

        # prop notes from prop_result (if present)
        prop_notes: List[str] = []
        try:
            eff = prop_result.get("effect", {}) if isinstance(prop_result, dict) else {}
            noise = eff.get("noise", None)
            grip = eff.get("grip", None)
            motor_load_indicator = eff.get("motor_load", None)
            if motor_load_indicator:
                # if prop_result's motor_load is in percent or g? assume numeric larger than 10 => grams
                if motor_load_indicator > 100:
                    prop_notes.append(f"Estimated thrust/motor {motor_load_indicator} g")
                else:
                    prop_notes.append(f"Motor load indicator: {motor_load_indicator}")
            if noise:
                prop_notes.append(f"Noise level: {noise}")
            if grip:
                prop_notes.append(f"Grip: {grip}")
        except Exception:
            pass

        # warnings list with severity
        warnings: List[Dict[str, Any]] = []
        # TWR warnings
        if twr < 1.2:
            warnings.append({"level": "danger", "msg": "TWR ต่ำมาก — บังคับยากและเสี่ยงต่อการสูญหาย"})
        elif twr < 1.5:
            warnings.append({"level": "warning", "msg": "TWR ค่อนข้างต่ำ — พิจารณาปรับสเปคหรือโหลดน้อยลง"})

        # battery C warnings
        if c_required_hover is not None:
            if c_required_hover > C_DANGER:
                warnings.append({"level": "danger", "msg": f"ต้องการ C สูง (~{c_required_hover:.0f}C) — เสี่ยง voltage sag/overheat"})
            elif c_required_hover > C_HIGH:
                warnings.append({"level": "warning", "msg": f"ต้องการ C สูง (~{c_required_hover:.0f}C) — แนะนำแบต C สูงขึ้น"})

        # motor warnings
        if motor_health == "danger":
            warnings.append({"level": "warning", "msg": "มอเตอร์ถูกโหลดสูง — ระวังความร้อนและตรวจสอบ ESC"})

        # ESC warnings
        if esc_flag == "danger":
            warnings.append({"level": "danger", "msg": "ESC limit ต่ำกว่าการโหลดคาดการณ์ — risk of ESC overcurrent"})
        elif esc_flag == "warning":
            warnings.append({"level": "warning", "msg": "ESC ใกล้ขีดจำกัดในการบินแบบ aggressive"})

        # flight time warning
        if est_flight_time_min < 2:
            warnings.append({"level": "danger", "msg": "เวลาบินคาดการณ์น้อยกว่า 2 นาที — ไม่แนะนำขึ้นบิน"})
        elif est_flight_time_min < 5:
            warnings.append({"level": "warning", "msg": "เวลาบินสั้น — พิจารณาแบตเตอรี่ใหญ่ขึ้นหรือลดน้ำหนัก"})

        # build result dict
        advanced = {
            "power": {
                "cells": int(cells),
                "battery_mAh_used": int(batt_mAh),
                "battery_wh": round(batt_wh, 2),
                "est_hover_power_w": round(est_hover_power_w, 1),
                "est_aggressive_power_w": round(est_aggressive_power_w, 1),
                "est_flight_time_min": int(est_flight_time_min),
                "est_flight_time_min_aggressive": int(est_flight_time_min_aggr)
            },
            "thrust_ratio": round(twr, 2) if twr != float('inf') else "inf",
            "hover_throttle_percent": hover_throttle_pct,
            "efficiency_class": efficiency_class,
            "motor_health": motor_health,
            "battery_health": battery_health,
            "flight_profile": flight_profile,
            "twr_note": twr_note,
            "kv_suggestion": kv_suggestion,
            "prop_notes": prop_notes,
            "warnings_advanced": warnings,
            # diagnostics for debugging / logging (non-sensitive)
            "_diagnostics": {
                "pack_voltage_v": round(pack_voltage, 2),
                "thrust_per_motor_g": round(thrust_per_motor_g, 1),
                "total_thrust_g": round(total_thrust_g, 1),
                "weight_g": round(weight_g, 1),
                "hover_throttle_frac": round(hover_throttle, 3),
                "est_hover_power_w": round(est_hover_power_w, 1),
                "est_hover_current_a": round(est_hover_current_a, 2),
                "c_required_hover": round(c_required_hover, 2) if c_required_hover is not None else None,
                "per_motor_hover_a": round(per_motor_hover_a, 2),
                "esc_flag": esc_flag,
                "motor_kv": motor_kv
            }
        }

        return {"advanced": advanced}

    except Exception as e:
        logger.exception("make_advanced_report failed")
        return {
            "advanced": {
                "power": {},
                "thrust_ratio": 0,
                "hover_throttle_percent": 100,
                "efficiency_class": "unknown",
                "motor_health": "unknown",
                "battery_health": "unknown",
                "flight_profile": "unknown",
                "twr_note": "",
                "kv_suggestion": "",
                "prop_notes": [],
                "warnings_advanced": [{"level": "danger", "msg": f"advanced analysis error: {e}"}],
                "_diagnostics": {}
            }
        }

# --------- quick local smoke (only when run directly) ----------
if __name__ == "__main__":
    # quick manual tests when running the file directly
    sample = make_advanced_report(
        size=5.0,
        weight_g=900,
        battery_s="4S",
        prop_result={"effect": {"motor_load": 420, "noise": 3, "grip": "medium"}},
        style="freestyle",
        battery_mAh=1500,
        motor_count=4,
        measured_thrust_per_motor_g=None,
        motor_kv=2450,
        esc_current_limit_a=40,
        blades=3
    )
    import json
    print(json.dumps(sample, indent=2, ensure_ascii=False))