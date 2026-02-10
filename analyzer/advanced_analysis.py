# analyzer/advanced_analysis.py
"""
Advanced analysis v1.0 for OBIXConfig Doctor.
- Input: size (inch), weight_g, battery_s (e.g. "4S"), prop_result dict, style,
         optional battery_mAh, motor_count, prop_thrust_g (per motor thrust in g)
- Output: dict with key "advanced" (contains power, twr, hover throttle, health, warnings)
"""

from typing import Dict, Any, Optional
import math

# ---------- Helpers ----------
def _cells_from_str(s: str) -> int:
    try:
        return int(str(s).upper().replace('S', '').strip())
    except Exception:
        return 4

_DEFAULT_BATT_MAH_BY_SIZE = {
    2.5: 450,
    3.0: 550,
    3.5: 650,
    4.0: 850,
    5.0: 1500,
    6.0: 1800,
    7.0: 2200,
    8.0: 3000
}

def _guess_batt_mAh(size: float) -> int:
    try:
        keys = sorted(_DEFAULT_BATT_MAH_BY_SIZE.keys())
        closest = min(keys, key=lambda k: abs(k - size))
        return _DEFAULT_BATT_MAH_BY_SIZE.get(closest, 1500)
    except Exception:
        return 1500

def _safe_div(a, b, default=0.0):
    try:
        return a / b if b else default
    except Exception:
        return default

def _severity_for_ratio(r: float):
    # For warnings coloring in UI
    if r >= 1.5:
        return "info"
    if r >= 1.0:
        return "warning"
    return "danger"

# ---------- Main function ----------
def make_advanced_report(size: float,
                         weight_g: float,
                         battery_s: str,
                         prop_result: Dict[str, Any],
                         style: str,
                         battery_mAh: Optional[int] = None,
                         motor_count: int = 4,
                         prop_thrust_g: Optional[float] = None
                         ) -> Dict[str, Any]:
    out = {"advanced": {}}
    try:
        # sanitize inputs
        cells = _cells_from_str(battery_s)
        size = float(size or 0)
        weight_g = float(weight_g or 0)
        motor_count = int(motor_count or 4)

        # battery mAh selection (use provided value if valid else guess)
        if battery_mAh and isinstance(battery_mAh, int) and battery_mAh > 0:
            batt_mAh = int(battery_mAh)
        else:
            batt_mAh = _guess_batt_mAh(size)

        # compute battery Wh
        nominal_v = 3.7
        batt_wh = (batt_mAh / 1000.0) * (cells * nominal_v)

        # determine thrust per motor
        # preferred source: explicit prop_thrust_g parameter
        if prop_thrust_g and prop_thrust_g > 0:
            thrust_per_motor_g = float(prop_thrust_g)
        else:
            # fallback to prop_result.effect.motor_load (expected per-motor thrust in g)
            thrust_per_motor_g = float(prop_result.get("effect", {}).get("motor_load", 0) or 0)

        # fallback heuristic: if still zero, estimate from size
        if thrust_per_motor_g <= 0:
            # rough heuristic: smaller props produce less thrust
            if size <= 3.5:
                thrust_per_motor_g = 250
            elif size <= 5.0:
                thrust_per_motor_g = 420
            elif size <= 6.0:
                thrust_per_motor_g = 550
            else:
                thrust_per_motor_g = 700

        total_thrust_g = thrust_per_motor_g * max(1, motor_count)
        # Thrust-to-weight (dimensionless)
        twr = _safe_div(total_thrust_g, weight_g, default=0.0)

        # Hover throttle: fraction of available thrust used to hover
        # hover_throttle = weight / total_thrust  (0..1) -> percent
        hover_throttle = _safe_div(weight_g, total_thrust_g, default=1.0)
        hover_throttle_pct = round(hover_throttle * 100.0, 1)

        # Efficiency class by hover throttle
        if hover_throttle < 0.30:
            efficiency_class = "excellent"
        elif hover_throttle < 0.45:
            efficiency_class = "good"
        elif hover_throttle < 0.6:
            efficiency_class = "poor"
        else:
            efficiency_class = "danger"

        # Power estimation (W) heuristic per kg based on style
        power_w_per_kg_map = {
            "freestyle": 550,
            "racing": 700,
            "longrange": 300,
            "cine": 350,
            "micro": 450
        }
        p_per_kg = power_w_per_kg_map.get(style, 450)
        weight_kg = max(0.001, weight_g / 1000.0)
        est_hover_power_w = p_per_kg * weight_kg
        # aggressive factor
        est_aggressive_power_w = est_hover_power_w * 1.8
        avg_power_for_flight_w = est_hover_power_w * 1.15  # small margin

        # Flight time estimates (minutes)
        est_flight_time_min = int(max(0, _safe_div(batt_wh, avg_power_for_flight_w, 0.0) * 60.0))
        est_flight_time_min_aggr = int(max(0, _safe_div(batt_wh, est_aggressive_power_w, 0.0) * 60.0))

        # Current & C-rate calculation
        # current_draw = power / pack_voltage
        pack_voltage = cells * nominal_v
        est_hover_current_a = _safe_div(est_hover_power_w, pack_voltage, 0.0)
        est_aggr_current_a = _safe_div(est_aggressive_power_w, pack_voltage, 0.0)
        batt_a_available = _safe_div(batt_mAh, 1000.0, 0.0)
        c_required_hover = _safe_div(est_hover_current_a, batt_a_available, 0.0) if batt_a_available else None
        c_required_aggr = _safe_div(est_aggr_current_a, batt_a_available, 0.0) if batt_a_available else None

        # Motor stress estimate (g per motor)
        motor_load_g = thrust_per_motor_g
        # motor_health heuristic
        if motor_load_g < 250:
            motor_health = "safe"
        elif motor_load_g < 450:
            motor_health = "high_load"
        else:
            motor_health = "danger"

        # Battery health heuristic
        batt_health = "unknown"
        if c_required_hover is not None:
            if c_required_hover < 20:
                batt_health = "safe"
            elif c_required_hover < 35:
                batt_health = "high_load"
            else:
                batt_health = "danger"

        # TWR note - more human-readable
        if twr >= 2.5:
            twr_note = "แรงเหลือสำหรับ freestyle/racing และ recovery ดี"
        elif twr >= 2.0:
            twr_note = "เพียงพอสำหรับ cinematic/long-range และการบินนิ่ง"
        elif twr >= 1.2:
            twr_note = "พอสู้ได้ แต่ไม่มี margin สำหรับท่าแอ็กทีฟ"
        else:
            twr_note = "แรงไม่พอ — แนะนำลดน้ำหนักหรือเพิ่ม thrust"

        # Flight profile suggestion
        if twr > 2.5 and efficiency_class in ("excellent", "good"):
            flight_profile = "Freestyle / Racing"
        elif twr >= 2.0:
            flight_profile = "Cinematic / Long-range"
        elif twr >= 1.2:
            flight_profile = "General / Light freestyle"
        else:
            flight_profile = "Not recommended"

        # KV suggestion (coarse)
        if size <= 3.5:
            kv_suggestion = "2300-4200"
        elif size <= 5.0:
            kv_suggestion = "1500-2800"
        elif size <= 6.0:
            kv_suggestion = "1200-2000"
        else:
            kv_suggestion = "800-1400"

        # prop notes from prop_result
        prop_notes = []
        pr_eff = prop_result.get("effect", {}) if isinstance(prop_result, dict) else {}
        if pr_eff.get("motor_load", 0) > 80:
            prop_notes.append("ใบพัดให้โหลดมอเตอร์สูง — ระวังความร้อน")
        if pr_eff.get("noise", 0) > 6:
            prop_notes.append("ระดับเสียงสูง — อาจต้องปรับ filter หรือ balance")
        if pr_eff.get("grip"):
            prop_notes.append(f"Grip: {pr_eff.get('grip')}")

        # warnings (with severity)
        warnings = []
        if twr < 1.2:
            warnings.append({"level": "danger", "msg": "TWR ต่ำมาก — บังคับยากและเสี่ยงต่อการสูญหาย"})
        elif twr < 1.5:
            warnings.append({"level": "warning", "msg": "TWR ต่ำ — แนะนำปรับสเปคหรือลดน้ำหนัก"})
        # battery c check
        if c_required_hover is not None:
            if c_required_hover > 30:
                warnings.append({"level": "warning", "msg": f"Peak C required ~{c_required_hover:.0f}C — ตรวจสอบแบตเตอรี่"})
            if c_required_hover > 50:
                warnings.append({"level": "danger", "msg": f"Very high C required ~{c_required_hover:.0f}C — risk of voltage sag/overheat"})
        # motor health
        if motor_health == "danger":
            warnings.append({"level": "warning", "msg": "มอเตอร์ถูกโหลดสูง — ตรวจสอบอุณหภูมิและ ESC"})
        # flight time
        if est_flight_time_min < 2:
            warnings.append({"level": "danger", "msg": "เวลาบินคาดการณ์น้อยกว่า 2 นาที — ไม่แนะนำขึ้นบิน"})

        out["advanced"] = {
            "power": {
                "cells": cells,
                "battery_mAh_used": batt_mAh,
                "battery_wh": round(batt_wh, 2),
                "est_hover_power_w": round(est_hover_power_w, 1),
                "est_aggressive_power_w": round(est_aggressive_power_w, 1),
                "est_flight_time_min": int(est_flight_time_min),
                "est_flight_time_min_aggressive": int(est_flight_time_min_aggr)
            },
            "thrust_ratio": round(twr, 2),
            "hover_throttle_percent": hover_throttle_pct,
            "efficiency_class": efficiency_class,
            "motor_health": motor_health,
            "battery_health": batt_health,
            "flight_profile": flight_profile,
            "twr_note": twr_note,
            "kv_suggestion": kv_suggestion,
            "prop_notes": prop_notes,
            "warnings_advanced": warnings,
            # internal diagnostics for dev/logging (optional)
            "_diagnostics": {
                "thrust_per_motor_g": thrust_per_motor_g,
                "total_thrust_g": total_thrust_g,
                "est_hover_current_a": round(est_hover_current_a, 2),
                "c_required_hover": round(c_required_hover, 1) if c_required_hover is not None else None
            }
        }
    except Exception as e:
        out["advanced"] = {
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
    return out