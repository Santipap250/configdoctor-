# analyzer/advanced_analysis.py
"""
Advanced analysis helper for OBIXConfig Doctor v1.0
Supports battery cells 1S..6S, optional battery_mAh, motor_count, prop_thrust_g (measured thrust per motor).
Returns a dict with key "advanced" to be merged into the main analysis.
"""

from typing import Dict, Any

# constants
NOMINAL_V_CELL = 3.7
FULL_V_CELL = 4.2
SAFE_MIN_V_CELL = 3.5

def parse_cells(battery_s: str) -> int:
    """Parse battery string like '4S', '4', '4 s' into integer cells (1..6)."""
    if battery_s is None:
        return 4
    try:
        s = str(battery_s).strip().upper()
        s = s.replace(" ", "")
        if s.endswith("S"):
            s = s[:-1]
        val = int(float(s))
        return max(1, min(6, val))
    except Exception:
        return 4

def _safe_div(a, b, default=0.0):
    try:
        return a / b if b else default
    except Exception:
        return default

def _guess_batt_mAh(size: float):
    """Fallback battery mAh guess based on frame size (inches)."""
    mapping = {2.5:450, 3.0:550, 3.5:650, 4.0:850, 5.0:1500, 6.0:1800, 7.0:2200, 8.0:3000}
    keys = sorted(mapping.keys())
    closest = min(keys, key=lambda k: abs(k - (size or 5.0)))
    return mapping.get(closest, 1500)

def make_advanced_report(size: float,
                         weight_g: float,
                         battery_s: str,
                         prop_result: Dict[str, Any],
                         style: str,
                         battery_mAh: int = None,
                         motor_count: int = 4,
                         prop_thrust_g: float = None) -> Dict[str, Any]:
    """
    Produce advanced analysis report.

    Parameters:
      - size: float (inches)
      - weight_g: float (grams)
      - battery_s: str like '4S' or '4'
      - prop_result: dict from prop analyzer (should contain effect.motor_load, noise, grip, etc.)
      - style: 'freestyle' | 'racing' | 'longrange' | ...
      - battery_mAh: optional int provided by user (overrides guess)
      - motor_count: optional int (defaults to 4)
      - prop_thrust_g: optional float measured thrust per motor in grams (preferred over prop_result.effect.motor_load)

    Returns:
      dict with key "advanced" containing measured metrics and recommendations.
    """
    out = {"advanced": {}}
    try:
        # pack info
        cells = parse_cells(battery_s)
        pack_v_nom = round(cells * NOMINAL_V_CELL, 2)
        pack_v_full = round(cells * FULL_V_CELL, 2)

        # battery capacity: user-supplied wins, otherwise guess from size
        if battery_mAh and isinstance(battery_mAh, int) and battery_mAh > 0:
            batt_mAh = int(battery_mAh)
        else:
            batt_mAh = _guess_batt_mAh(size)

        batt_wh = round((batt_mAh / 1000.0) * pack_v_nom, 2)

        # thrust: prefer measured prop_thrust_g, else fall back to prop_result.effect.motor_load
        motor_thrust_g = 0.0
        if prop_thrust_g:
            try:
                motor_thrust_g = float(prop_thrust_g)
            except Exception:
                motor_thrust_g = 0.0
        else:
            try:
                motor_thrust_g = float(prop_result.get("effect", {}).get("motor_load", 0) or 0)
            except Exception:
                motor_thrust_g = 0.0

        motor_count = max(1, int(motor_count or 4))
        total_thrust_g = motor_thrust_g * motor_count
        twr = round(_safe_div(total_thrust_g, weight_g, default=0.0), 2)

        # hover throttle (as fraction of max thrust)
        hover_throttle_frac = _safe_div(weight_g, total_thrust_g, default=1.0)
        hover_throttle_pct = round(hover_throttle_frac * 100.0, 1)

        # efficiency class from hover throttle
        if hover_throttle_frac < 0.30:
            efficiency = "excellent"
        elif hover_throttle_frac < 0.45:
            efficiency = "good"
        elif hover_throttle_frac < 0.60:
            efficiency = "poor"
        else:
            efficiency = "danger"

        # style based power per kg (heuristic)
        p_per_kg_map = {
            "freestyle": 550,
            "racing": 700,
            "longrange": 300,
            "cine": 350,
            "micro": 450
        }
        p_per_kg = p_per_kg_map.get(style, 450)
        weight_kg = max(0.001, (weight_g or 0) / 1000.0)
        est_hover_power_w = round(p_per_kg * weight_kg, 1)
        est_aggressive_power_w = round(est_hover_power_w * 1.8, 1)
        avg_power_w = est_hover_power_w * 1.15

        # estimate flight time (minutes)
        est_flight_min = int(max(0, _safe_div(batt_wh, avg_power_w, 0.0) * 60.0))
        est_flight_min_aggr = int(max(0, _safe_div(batt_wh, est_aggressive_power_w, 0.0) * 60.0))

        # current draw & required C-rate
        current_draw_a = round(_safe_div(avg_power_w, pack_v_nom, 0.0), 2)
        c_required = round(_safe_div(current_draw_a, (batt_mAh/1000.0), 0.0), 1)

        # battery health classification by C required (heuristic)
        if c_required < 20:
            battery_health = "safe"
        elif c_required < 35:
            battery_health = "high_load"
        else:
            battery_health = "danger"

        # motor health classification by thrust-per-motor (heuristic)
        if motor_thrust_g <= 0:
            motor_health = "unknown"
        elif motor_thrust_g < 200:
            motor_health = "safe"
        elif motor_thrust_g < 350:
            motor_health = "high_load"
        else:
            motor_health = "danger"

        # KV suggestion (heuristic adapted by size & cells)
        if size is None:
            size = 5.0
        try:
            s = float(size)
        except Exception:
            s = 5.0

        if s <= 3.5:
            kv_range = "2300-4200" if cells <= 4 else "2000-3500"
        elif s <= 5.0:
            kv_range = "1500-2800" if cells <= 4 else "900-1800"
        else:
            kv_range = "800-1400" if cells <= 4 else "500-1000"

        # recommended TWR range by style
        style_targets = {
            "freestyle": (1.8, 2.5),
            "racing": (2.0, 3.0),
            "longrange": (0.9, 1.4),
            "cine": (1.0, 1.4),
            "micro": (1.6, 2.6)
        }
        low_twr, high_twr = style_targets.get(style, (1.2, 2.2))
        twr_note = f"Detected TWR ≈ {twr:.2f} (total thrust {total_thrust_g:.0f} g). Recommended for {style}: {low_twr:.1f}–{high_twr:.1f}."

        # prop notes aggregation
        prop_notes = []
        try:
            # prefer explicit notes if provided
            if isinstance(prop_result.get("notes", []), list):
                prop_notes += prop_result.get("notes", [])
        except Exception:
            pass
        # if recommendation exists and is string or list, append
        rec = prop_result.get("recommendation", "")
        if isinstance(rec, list):
            prop_notes += rec
        elif isinstance(rec, str) and rec:
            prop_notes.append(rec)

        # build warnings list with severity
        warnings_adv = []
        if twr < low_twr:
            warnings_adv.append({"level": "warning", "msg": "TWR ต่ำกว่าช่วงแนะนำ — อาจบังคับยาก"})
        if hover_throttle_pct > 60:
            warnings_adv.append({"level": "danger", "msg": "Hover throttle สูงกว่า 60% — เสี่ยงแบต/มอเตอร์ร้อน"})
        if battery_health == "danger":
            warnings_adv.append({"level": "danger", "msg": f"C-required สูง ({c_required}C) — แบตไม่เหมาะหรือเสี่ยง"})
        if motor_health == "danger":
            warnings_adv.append({"level": "warning", "msg": "โหลดมอเตอร์สูง — ตรวจสอบอุณหภูมิ/ESC"})

        # final advanced payload
        out["advanced"] = {
            "cells": cells,
            "pack_voltage_nominal": pack_v_nom,
            "pack_voltage_full": pack_v_full,
            "battery_mAh_used": batt_mAh,
            "battery_wh": batt_wh,
            "est_hover_power_w": est_hover_power_w,
            "est_aggressive_power_w": est_aggressive_power_w,
            "est_flight_time_min": est_flight_min,
            "est_flight_time_min_aggressive": est_flight_min_aggr,
            "current_draw_a": current_draw_a,
            "c_required": c_required,
            "thrust_ratio": twr,
            "hover_throttle_percent": hover_throttle_pct,
            "efficiency_class": efficiency,
            "motor_health": motor_health,
            "battery_health": battery_health,
            "kv_suggestion": kv_range,
            "twr_note": twr_note,
            "prop_notes": prop_notes,
            "warnings_advanced": warnings_adv
        }

    except Exception as e:
        out["advanced"] = {"error": "advanced analysis failed", "msg": str(e)}
    return out