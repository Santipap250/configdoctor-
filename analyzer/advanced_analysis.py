# analyzer/advanced_analysis.py
"""
Advanced analysis (v1.x - "Pro") for OBIXConfig Doctor.

Goals:
 - Support battery packs 1S..6S and optional user inputs (battery_mAh, motor_count, prop_thrust_g, payload_g).
 - Produce engineering-focused metrics: pack volts, Wh, est power(W), est current(A),
   required C-rating, hover throttle %, TWR, motor & battery health, KV suggestion, and recommended actions.
 - Defensive: never raise uncaught exceptions; returns structured dict for merging into templates.
 - Warnings have 'level' (info, warning, danger) to make UI coloring simple.

Usage:
    from analyzer.advanced_analysis import make_advanced_report
    report = make_advanced_report(
        size=5.0,
        weight_g=900,
        battery_s='4S',
        prop_result={'effect': {'motor_load': 450, 'noise': 3, 'grip': 'good'}},
        style='freestyle',
        battery_mAh=1500,      # optional
        motor_count=4,         # optional
        prop_thrust_g=None,    # optional measured thrust per motor (g)
        payload_g=0            # optional extra payload besides 'weight_g' if desired
    )

Returned structure:
{
  "advanced": {
     "cells": int,
     "pack_voltage_nominal": float,
     "pack_voltage_full": float,
     "battery_mAh_used": int,
     "battery_wh": float,
     "usable_wh": float,                 # after reserve (to protect battery / sag)
     "est_hover_power_w": float,
     "est_aggressive_power_w": float,
     "avg_power_w": float,
     "est_flight_time_min": int,
     "est_flight_time_min_aggr": int,
     "current_draw_a": float,
     "peak_current_a": float,
     "c_required": float,
     "thrust_ratio": float,
     "hover_throttle_percent": float,
     "efficiency_class": str,
     "motor_health": str,
     "battery_health": str,
     "kv_suggestion": str,
     "recommendations": [str...],
     "prop_notes": [...],
     "warnings_advanced": [{"level":..., "msg":...}, ...],
     "confidence": { "power_estimate": 0.0-1.0, ... }
  }
}

Notes / heuristics:
 - Nominal cell voltage = 3.7 V. Full charge ~4.2 V. Safe reserve is configurable (default 15% usable reduction).
 - Power per kg heuristics are style-driven but blended with TWR & hover throttle to adjust.
 - C-required computed from estimated average power draw and battery capacity.
 - KV suggestions are coarse heuristics based on size, cell count, and style. This function is conservative.
"""

from typing import Dict, Any, Optional, List
import math

# Constants (tunable)
NOMINAL_V_CELL = 3.7
FULL_V_CELL = 4.2
SAFE_MIN_V_CELL = 3.5

# Default percent of battery energy considered usable for flight (reserve to protect battery)
DEFAULT_USABLE_ENERGY_RATIO = 0.85  # keep ~15% as reserve

# Flight style base W/kg (heuristic starting points)
STYLE_W_PER_KG = {
    "freestyle": 550.0,
    "racing": 700.0,
    "longrange": 300.0,
    "cine": 350.0,
    "micro": 450.0,
    # fallback default used when style unknown
    "default": 450.0
}

# Recommended TWR ranges by style (min, max)
STYLE_TWR_RANGES = {
    "freestyle": (1.8, 2.5),
    "racing": (2.0, 3.0),
    "longrange": (0.9, 1.4),
    "cine": (1.0, 1.4),
    "micro": (1.6, 2.6),
    "default": (1.2, 2.2)
}

# Helper functions
def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        return float(a) / float(b) if b else default
    except Exception:
        return default

def parse_cells(battery_s: Any) -> int:
    """Parse battery descriptor to int cells (1..6). Accept '4S', '4', 4.0 etc."""
    try:
        if battery_s is None:
            return 4
        s = str(battery_s).strip().upper().replace(" ", "")
        if s.endswith("S"):
            s = s[:-1]
        val = int(float(s))
        if val < 1:
            return 1
        if val > 6:
            return 6
        return val
    except Exception:
        return 4

def _guess_batt_mAh(size_inch: Optional[float]) -> int:
    """Heuristic guess for battery capacity based on frame size (inches)."""
    try:
        s = float(size_inch) if size_inch else 5.0
    except Exception:
        s = 5.0
    mapping = {2.5: 450, 3.0: 550, 3.5: 650, 4.0: 850, 5.0: 1500, 6.0: 1800, 7.0: 2200, 8.0: 3000}
    keys = sorted(mapping.keys())
    closest = min(keys, key=lambda k: abs(k - s))
    return mapping.get(closest, 1500)

def _kv_suggestion(size_inch: float, cells: int, style: str) -> str:
    """Return a coarse KV range string based on size and cell count."""
    try:
        s = float(size_inch)
    except Exception:
        s = 5.0
    # Big picture: higher cells => lower KV for same RPM
    if s <= 3.5:
        return "2300-4200" if cells <= 4 else "2000-3500"
    if s <= 5.0:
        return "1500-2800" if cells <= 4 else "900-1800"
    if s <= 6.0:
        return "1200-2000" if cells <= 4 else "800-1500"
    return "700-1400" if cells <= 4 else "500-1000"

def _classify_efficiency(hover_frac: float) -> str:
    if hover_frac < 0.30:
        return "excellent"
    if hover_frac < 0.45:
        return "good"
    if hover_frac < 0.60:
        return "poor"
    return "danger"

def _motor_health_from_thrust(thrust_g: float) -> str:
    if thrust_g <= 0:
        return "unknown"
    if thrust_g < 200:
        return "safe"
    if thrust_g < 350:
        return "high_load"
    return "danger"

def _battery_health_from_c(c_required: float) -> str:
    if c_required <= 0:
        return "unknown"
    if c_required < 20:
        return "safe"
    if c_required < 35:
        return "high_load"
    return "danger"

def _compose_warning(level: str, msg: str) -> Dict[str, str]:
    return {"level": level, "msg": msg}

# Main function
def make_advanced_report(size: Optional[float],
                         weight_g: Optional[float],
                         battery_s: Any,
                         prop_result: Dict[str, Any],
                         style: str = "default",
                         battery_mAh: Optional[int] = None,
                         motor_count: Optional[int] = 4,
                         prop_thrust_g: Optional[float] = None,
                         payload_g: Optional[float] = 0.0,
                         usable_energy_ratio: float = DEFAULT_USABLE_ENERGY_RATIO
                         ) -> Dict[str, Any]:
    """
    Produce an advanced analysis report.

    Parameters:
      - size: inches (float)
      - weight_g: grams (float) - total drone weight INCLUDING payload_g if user prefers; else use payload_g param
      - battery_s: '4S' or int-like
      - prop_result: dict from prop analyzer (expect keys effect.motor_load (g), noise, grip, notes, recommendation)
      - style: flight style (freestyle/racing/longrange/cine/micro)
      - battery_mAh: user-provided capacity (int) optional
      - motor_count: number of motors (int)
      - prop_thrust_g: measured thrust per motor in grams (float) optional -> preferred over prop_result.effect.motor_load
      - payload_g: additional payload mass (g) optional
      - usable_energy_ratio: fraction of battery energy usable during flight for estimates

    Returns:
      dict containing "advanced" key with detailed metrics and lists for UI.
    """
    report: Dict[str, Any] = {"advanced": {}}
    try:
        # Defensive defaults
        cells = parse_cells(battery_s)
        size_inch = (float(size) if size else 5.0)
        weight_g = float(weight_g) if (weight_g is not None and weight_g != "") else 1000.0
        payload_g = float(payload_g) if (payload_g is not None and payload_g != "") else 0.0
        total_mass_g = max(1.0, weight_g + (payload_g or 0.0))

        # Voltages
        pack_voltage_nominal = round(cells * NOMINAL_V_CELL, 2)
        pack_voltage_full = round(cells * FULL_V_CELL, 2)

        # Battery capacity
        if battery_mAh and isinstance(battery_mAh, (int, float)) and battery_mAh > 0:
            batt_mAh = int(battery_mAh)
        else:
            batt_mAh = _guess_batt_mAh(size_inch)

        battery_wh = round((batt_mAh / 1000.0) * pack_voltage_nominal, 2)
        usable_wh = round(battery_wh * float(usable_energy_ratio), 2)

        # Thrust per motor
        motor_count = int(motor_count) if motor_count else 4
        # priority: prop_thrust_g (measured) -> prop_result.effect.motor_load -> fallback by heuristic based on size
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

        # fallback heuristic: if motor_thrust_g is zero, guess from size and blades
        if motor_thrust_g <= 0:
            # approximate: bigger frames use larger props -> more thrust per motor
            if size_inch <= 3.5:
                motor_thrust_g = 180.0
            elif size_inch <= 5.0:
                motor_thrust_g = 450.0
            elif size_inch <= 7.0:
                motor_thrust_g = 900.0
            else:
                motor_thrust_g = 1200.0

        total_thrust_g = motor_thrust_g * max(1, motor_count)
        thrust_ratio = round(_safe_div(total_thrust_g, total_mass_g, default=0.0), 2)

        # Hover throttle fraction (fraction of max thrust used at hover)
        hover_frac = _safe_div(total_mass_g, total_thrust_g, default=1.0)
        hover_pct = round(hover_frac * 100.0, 1)
        efficiency_class = _classify_efficiency(hover_frac)

        # Power estimation
        # Base W/kg from style but adjust with TWR / hover_frac to reflect more/less power usage.
        base_w_per_kg = STYLE_W_PER_KG.get(style, STYLE_W_PER_KG["default"])
        # adjust factor: if hover_frac is small (efficient) reduce w/kg slightly; if large, increase
        adjust_factor = 1.0
        if hover_frac < 0.3:
            adjust_factor = 0.95
        elif hover_frac > 0.6:
            adjust_factor = 1.35
        est_hover_power_w = round(base_w_per_kg * (total_mass_g/1000.0) * adjust_factor, 1)
        est_aggressive_power_w = round(est_hover_power_w * 1.8, 1)
        avg_power_w = round(est_hover_power_w * 1.15, 1)

        # Flight time estimates (minutes)
        est_flight_time_min = int(max(0, _safe_div(usable_wh, avg_power_w, 0.0) * 60.0))
        est_flight_time_min_aggr = int(max(0, _safe_div(usable_wh, est_aggressive_power_w, 0.0) * 60.0))

        # Electricals: current draw (A)
        avg_current_a = round(_safe_div(avg_power_w, pack_voltage_nominal, 0.0), 2)
        peak_current_a = round(_safe_div(est_aggressive_power_w, pack_voltage_nominal, 0.0), 2)
        # required C rating
        c_required = round(_safe_div(peak_current_a, (batt_mAh/1000.0), 0.0), 1)  # using peak current

        battery_health = _battery_health_from_c(c_required)
        motor_health = _motor_health_from_thrust(motor_thrust_g)

        # KV suggestion (coarse)
        kv_range = _kv_suggestion(size_inch, cells, style)

        # Recommendation logic (simple rules)
        recommendations: List[str] = []
        if thrust_ratio < STYLE_TWR_RANGES.get(style, STYLE_TWR_RANGES["default"])[0]:
            recommendations.append("เพิ่มแรงขับ (มอเตอร์/ใบพัด) หรือลดน้ำหนัก เพื่อนำ TWR ขึ้นในช่วงที่แนะนำ")
        if hover_pct > 60:
            recommendations.append("Hover throttle สูง — ลด payload หรือเพิ่ม thrust/เซลล์")
        if battery_health == "danger":
            recommendations.append("C-rating ที่ต้องการสูง — ใช้แบตที่มี C สูงหรือเพิ่มความจุ/เซลล์")
        if motor_health == "danger":
            recommendations.append("โหลดมอเตอร์สูง — พิจารณาใช้มอเตอร์ที่ใหญ่ขึ้นหรือใบพัดที่เบากว่า")

        # Aggregate prop notes
        prop_notes = []
        try:
            pr_notes = prop_result.get("notes", [])
            if isinstance(pr_notes, list):
                prop_notes += pr_notes
            elif isinstance(pr_notes, str) and pr_notes:
                prop_notes.append(pr_notes)
        except Exception:
            pass
        rec = prop_result.get("recommendation", "")
        if isinstance(rec, list):
            prop_notes += rec
        elif isinstance(rec, str) and rec:
            prop_notes.append(rec)

        # Confidence estimate: if user provided battery_mAh and prop_thrust_g -> high confidence.
        confidence = {
            "power_estimate": 0.7,
            "thrust_estimate": 0.5,
            "overall": 0.6
        }
        if battery_mAh and prop_thrust_g:
            confidence = {"power_estimate": 0.95, "thrust_estimate": 0.95, "overall": 0.95}
        elif battery_mAh or prop_thrust_g:
            confidence = {"power_estimate": 0.9 if battery_mAh else 0.6,
                          "thrust_estimate": 0.9 if prop_thrust_g else 0.6,
                          "overall": 0.8}

        # Build warnings with severity
        warnings_adv = []
        # TWR warning
        low_twr, high_twr = STYLE_TWR_RANGES.get(style, STYLE_TWR_RANGES["default"])
        if thrust_ratio < low_twr:
            warnings_adv.append(_compose_warning("warning", f"TWR ต่ำกว่าที่แนะนำ ({thrust_ratio} < {low_twr})"))
        # Hover throttle
        if hover_pct > 60:
            warnings_adv.append(_compose_warning("danger", f"Hover throttle สูง ({hover_pct}%) — เสี่ยงแบต/มอเตอร์ร้อน"))
        # Battery
        if battery_health == "danger":
            warnings_adv.append(_compose_warning("danger", f"C-required สูง ({c_required}C) — เปลี่ยนแบตหรือเพิ่มความจุ/เซลล์"))
        elif battery_health == "high_load":
            warnings_adv.append(_compose_warning("warning", f"C-required สูงปานกลาง ({c_required}C) — ระวังการร่วงของแรงดัน"))
        # Motor
        if motor_health == "danger":
            warnings_adv.append(_compose_warning("warning", f"โหลดมอเตอร์สูง ({motor_thrust_g} g per motor)"))
        # Edge cases
        if batt_mAh < 200:
            warnings_adv.append(_compose_warning("info", "Battery capacity น้อย (คาดว่าจะบินสั้น)"))

        # Final payload
        report["advanced"] = {
            "cells": cells,
            "pack_voltage_nominal": pack_voltage_nominal,
            "pack_voltage_full": pack_voltage_full,
            "battery_mAh_used": batt_mAh,
            "battery_wh": battery_wh,
            "usable_wh": usable_wh,
            "est_hover_power_w": est_hover_power_w,
            "est_aggressive_power_w": est_aggressive_power_w,
            "avg_power_w": avg_power_w,
            "est_flight_time_min": est_flight_time_min,
            "est_flight_time_min_aggr": est_flight_time_min_aggr,
            "current_draw_a": avg_current_a,
            "peak_current_a": peak_current_a,
            "c_required": c_required,
            "thrust_ratio": thrust_ratio,
            "hover_throttle_percent": hover_pct,
            "efficiency_class": efficiency_class,
            "motor_health": motor_health,
            "battery_health": battery_health,
            "kv_suggestion": kv_range,
            "recommendations": recommendations,
            "prop_notes": prop_notes,
            "warnings_advanced": warnings_adv,
            "confidence": confidence,
            # meta for UI / debugging
            "meta": {
                "motor_thrust_g": motor_thrust_g,
                "total_thrust_g": total_thrust_g,
                "mass_g": total_mass_g,
                "style_used": style
            }
        }
    except Exception as e:
        report["advanced"] = {
            "error": "advanced analysis failed",
            "msg": str(e)
        }
    return report