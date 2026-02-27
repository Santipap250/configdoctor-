# analyzer/advanced_analysis.py
"""
Rule-based FPV battery/motor/ESC analyzer (3S-8S)
Copy-paste ready.

CLI example:
  python advanced_analysis.py --size 5.0 --cells 7 --motor-kv 1600 --weight 1200 --motors 4 --hover-throttle 0.28

Returns human-readable summary + JSON diagnostics.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, Any, Optional

# --- Constants ---
NOMINAL_CELL_V = 3.7
MAX_CELL_V = 4.2
KV_THRESHOLD_HIGH = 1500  # KV above which high-voltage builds are risky
HIGH_VOLTAGE_CELLS = 7
DEFAULT_MOTORS = 4

# Default mAh table (nested by prop size -> cells -> typical mAh)
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

# --- Helpers ---

def _cells_from_str(s: str) -> int:
    """Parse cell count from string like '4S' or integer string.
    Clamp to range 3..8. Return default 4 on error.
    """
    try:
        cells = int(str(s).upper().replace("S", "").strip())
        if cells < 3:
            return 3
        if cells > 8:
            return 8
        return cells
    except Exception:
        return 4


def _guess_batt_mAh(size_inch: float, cells: int) -> int:
    """Pick a default batt mAh given prop/airframe size and cells.
    Strategy: find the closest size key, check table for exact cell; if missing, pick nearest available cell value.
    """
    keys = sorted(_DEFAULT_BATT_MAH_BY_SIZE.keys())
    closest = min(keys, key=lambda k: abs(k - size_inch))
    table = _DEFAULT_BATT_MAH_BY_SIZE[closest]
    if cells in table:
        return table[cells]
    # nearest available cell in that table
    available_cells = sorted(table.keys())
    nearest_cell = min(available_cells, key=lambda c: abs(c - cells))
    return table[nearest_cell]


def _format_amp(a: float) -> str:
    return f"{a:.2f} A"


def _format_watt(w: float) -> str:
    return f"{w:.1f} W"


# --- Core analysis ---

def analyze(
    size_inch: float = 5.0,
    cell_input: str | int = 4,
    batt_mAh: int | None = None,
    motor_kv: int | None = None,
    weight_g: float = 1000.0,
    motors: int = DEFAULT_MOTORS,
    hover_throttle: float = 0.5,
    thrust_per_motor_g: float | None = None,
) -> Dict[str, Any]:
    """Return analysis dict with computed metrics, warnings, and diagnostics.

    Heuristics (rule-based):
    - If thrust_per_motor_g not provided, assume hover thrust = weight * 2 margin, split across motors
    - Power estimate: empirical ratio W_per_gram = 0.12 W/g (multicopter hover heuristic)
    - Current = power / pack_voltage
    - C-rating = (current * 1000) / batt_mAh
    """
    # Normalize cells
    cells = _cells_from_str(str(cell_input))

    # Battery defaults
    if batt_mAh is None:
        batt_mAh = _guess_batt_mAh(size_inch, cells)

    # Voltages
    pack_voltage_nominal = round(cells * NOMINAL_CELL_V, 2)
    pack_voltage_max = round(cells * MAX_CELL_V, 2)

    # thrust estimate
    if thrust_per_motor_g is None:
        # assume hover thrust needed = weight * 2 (50% throttle margin), distributed across motors
        hover_thrust_total_g = weight_g * 2.0
        thrust_per_motor_g = hover_thrust_total_g / float(motors)

    # Empirical power estimate per motor (rule-based)
    # Use heuristic W_per_gram = 0.12 W/g (common multicopter hover heuristic)
    W_PER_GRAM = 0.12
    power_per_motor_w = thrust_per_motor_g * W_PER_GRAM
    total_power_w = power_per_motor_w * motors

    # Current and C-rating
    current_a = total_power_w / pack_voltage_nominal if pack_voltage_nominal > 0 else 0.0
    c_rating = (current_a * 1000.0) / batt_mAh if batt_mAh > 0 else float('inf')

    # Rule-based warnings and classes
    warnings = []

    # High voltage warning
    if cells >= HIGH_VOLTAGE_CELLS:
        warnings.append({
            "level": "warning",
            "msg": "แรงดันสูง (7S–8S) — ตรวจสอบ ESC, capacitor และ motor KV ให้รองรับ"
        })

    # KV vs cell rules
    if motor_kv is not None:
        if cells >= 7 and motor_kv > KV_THRESHOLD_HIGH:
            warnings.append({
                "level": "danger",
                "msg": f"Motor KV {motor_kv} สูงเกินไปสำหรับ {cells}S — เสี่ยง ESC/motor พัง"
            })
        elif cells <= 3 and motor_kv < KV_THRESHOLD_HIGH:
            warnings.append({
                "level": "warning",
                "msg": f"Motor KV {motor_kv} ต่ำเกินไปสำหรับ {cells}S — อาจแรงไม่พอ"
            })

    # Throttle efficiency class
    efficiency_class = "nominal"
    if hover_throttle is not None:
        if cells <= 3 and hover_throttle > 0.6:
            efficiency_class = "danger_low_voltage"
            warnings.append({
                "level": "danger",
                "msg": "Low-voltage build with high hover throttle — battery and motors under stress"
            })
        elif cells >= 7 and hover_throttle < 0.25:
            efficiency_class = "overpowered"
            warnings.append({
                "level": "info",
                "msg": "High-voltage build with very low hover throttle — overpowered for typical hover"
            })

    # Motor/ESC stress estimation (rule-based scoring)
    stress_score = 0.0
    stress_reasons = []
    # High current relative to typical ESC continuous rating
    typical_esc_continuous_a = 30.0  # rule-of-thumb
    if current_a > typical_esc_continuous_a:
        stress_score += 1.0
        stress_reasons.append(f"Estimated current {current_a:.1f}A exceeds typical ESC continuous {typical_esc_continuous_a}A")

    # High KV on high cells
    if motor_kv is not None and cells >= 7 and motor_kv > KV_THRESHOLD_HIGH:
        stress_score += 1.0
        stress_reasons.append("High KV on high-voltage pack increases motor/ESC stress")

    # C-rating concern
    if c_rating > 60:
        stress_score += 0.8
        stress_reasons.append(f"High implied C-rating {c_rating:.1f}C -> battery stressed")

    # Motor/ESC stress classification
    if stress_score >= 2.0:
        motor_esc_stress = "high"
    elif stress_score >= 1.0:
        motor_esc_stress = "moderate"
    else:
        motor_esc_stress = "low"

    # Flight profile suggestion
    if cells >= 7:
        flight_profile = "High voltage performance build"
    elif cells == 3:
        flight_profile = "Low voltage efficiency build"
    else:
        flight_profile = "Balanced build"

    diagnostics = {
        "battery_cells": cells,
        "battery_voltage_nominal": pack_voltage_nominal,
        "battery_voltage_max": pack_voltage_max,
        "battery_mAh_used": batt_mAh,
        "estimated_hover_thrust_per_motor_g": round(thrust_per_motor_g, 1),
        "motors": motors,
    }

    result = {
        "input": {
            "size_inch": size_inch,
            "cells": cells,
            "batt_mAh": batt_mAh,
            "motor_kv": motor_kv,
            "weight_g": weight_g,
            "motors": motors,
            "hover_throttle": hover_throttle,
        },
        "computed": {
            "pack_voltage_nominal": pack_voltage_nominal,
            "pack_voltage_max": pack_voltage_max,
            "power_w": round(total_power_w, 1),
            "current_a": round(current_a, 2),
            "implied_c_rating": round(c_rating, 1) if math.isfinite(c_rating) else None,
        },
        "motor_esc_stress": motor_esc_stress,
        "stress_reasons": stress_reasons,
        "efficiency_class": efficiency_class,
        "flight_profile": flight_profile,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }

    return result


# --- CLI / Pretty print ---

def _human_summary(res: Dict[str, Any]) -> str:
    c = res["computed"]
    diag = res["diagnostics"]
    lines = []
    lines.append("=== FPV Advanced Analysis (Rule-based) ===")
    lines.append(f"Cells: {res['input']['cells']}S | Nominal V: {c['pack_voltage_nominal']} V | Max V: {diag['battery_voltage_max']} V")
    lines.append(f"Battery mAh (used): {diag['battery_mAh_used']} mAh")
    implied_c = c.get("implied_c_rating")
    implied_c_str = f"{implied_c:.1f} C" if implied_c is not None else "n/a"
    lines.append(f"Estimated total power: {_format_watt(c['power_w'])} | Estimated current: {_format_amp(c['current_a'])} | Implied C-rating: {implied_c_str}")
    lines.append(f"Motor/ESC stress: {res['motor_esc_stress']}" )
    if res['stress_reasons']:
        lines.append("Stress reasons:")
        for r in res['stress_reasons']:
            lines.append(f" - {r}")
    if res['warnings']:
        lines.append("Warnings:")
        for w in res['warnings']:
            lines.append(f" [{w['level'].upper()}] {w['msg']}")
    lines.append(f"Efficiency class: {res['efficiency_class']}")
    lines.append(f"Flight profile suggestion: {res['flight_profile']}")
    lines.append("Diagnostics:")
    for k, v in res['diagnostics'].items():
        lines.append(f"  {k}: {v}")

    return "\n".join(lines)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="advanced_analysis.py - rule-based FPV analyzer (3S-8S)")
    p.add_argument("--size", type=float, default=5.0, help="frame/prop nominal size in inches (e.g. 5.0)")
    p.add_argument("--cells", type=str, default="4", help="battery cells (e.g. 4 or 4S)")
    p.add_argument("--batt-mAh", type=int, default=None, help="battery capacity in mAh (optional) -- if omitted guess from size+cells")
    p.add_argument("--motor-kv", type=int, default=None, help="motor KV (optional)")
    p.add_argument("--weight", type=float, default=1000.0, help="aircraft takeoff weight in grams")
    p.add_argument("--motors", type=int, default=DEFAULT_MOTORS, help="number of motors")
    p.add_argument("--hover-throttle", type=float, default=0.5, help="hover throttle (0..1)")
    p.add_argument("--thrust-per-motor-g", type=float, default=None, help="override thrust per motor in grams (optional)")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    cells = _cells_from_str(str(args.cells))
    res = analyze(
        size_inch=args.size,
        cell_input=cells,
        batt_mAh=args.batt_mAh,
        motor_kv=args.motor_kv,
        weight_g=args.weight,
        motors=args.motors,
        hover_throttle=args.hover_throttle,
        thrust_per_motor_g=args.thrust_per_motor_g,
    )

    # Print human summary and JSON
    print(_human_summary(res))
    print('\n--- JSON output (machine friendly) ---')
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

# --- Wrapper so app.py can call make_advanced_report(...) ---
def make_advanced_report(
    size: float,
    weight_g: float,
    battery_s: str,
    prop_result: Dict[str, Any],
    style: str,
    battery_mAh: Optional[int] = None,
    motor_count: int = DEFAULT_MOTORS,
    measured_thrust_per_motor_g: Optional[float] = None,
    motor_kv: Optional[int] = None,
    esc_current_limit_a: Optional[float] = None,
    blades: Optional[int] = None,
    payload_g: Optional[float] = None
) -> Dict[str, Any]:
    """
    Compatibility wrapper:
    - Calls analyze(...) (existing) and maps its output into the {'advanced': {...}} shape
      expected by app.py templates.
    - Provides reasonable defaults when some inputs are missing.
    """
    try:
        # normalize inputs
        cells = _cells_from_str(str(battery_s))
        total_weight_g = float((weight_g or 0) + (payload_g or 0))

        # Call existing analyze() but adapt parameter names:
        analysis = analyze(
            size_inch=float(size or 5.0),
            cell_input=cells,
            batt_mAh=battery_mAh,
            motor_kv=motor_kv,
            weight_g=total_weight_g,
            motors=int(motor_count or DEFAULT_MOTORS),
            hover_throttle=None,  # analyze uses hover_throttle only for classification warnings; we don't have measured value
            thrust_per_motor_g=measured_thrust_per_motor_g
        )

        # Pull commonly needed values (fall back sensibly)
        comp = analysis.get("computed", {})
        diag = analysis.get("diagnostics", {})
        input_block = analysis.get("input", {})

        total_power_w = float(comp.get("power_w", 0.0))
        pack_voltage = float(comp.get("pack_voltage_nominal", cells * NOMINAL_CELL_V))
        batt_mAh_used = int(input_block.get("batt_mAh") or battery_mAh or _guess_batt_mAh(float(size or 5.0), cells))
        # battery energy (Wh)
        battery_wh = round((batt_mAh_used / 1000.0) * pack_voltage, 2)

        # estimate flight time (minutes): use total_power_w (W). Avoid divide-by-zero.
        if total_power_w > 0:
            est_flight_time_min = int(max(0, round((battery_wh / total_power_w) * 60.0)))
            # aggressive uses a simple multiplier (higher power)
            est_flight_time_min_aggressive = int(max(0, round((battery_wh / (total_power_w * 1.8)) * 60.0)))
        else:
            est_flight_time_min = 0
            est_flight_time_min_aggressive = 0

        # thrust ratio: try to take from analysis if present else compute from thrust estimate
        thrust_ratio = None
        if "thrust_ratio" in analysis:
            try:
                thrust_ratio = analysis["thrust_ratio"]
            except Exception:
                thrust_ratio = None
        else:
            # compute if we have estimated thrust per motor in diagnostics
            est_thrust_per_motor = diag.get("estimated_hover_thrust_per_motor_g") or input_block.get("thrust_per_motor_g")
            if est_thrust_per_motor:
                try:
                    total_thrust_g = float(est_thrust_per_motor) * int(input_block.get("motors", motor_count))
                    thrust_ratio = round(total_thrust_g / (total_weight_g or 1.0), 2)
                except Exception:
                    thrust_ratio = None

        # BUG FIX: warnings เดิมถูก flatten เป็น list of strings
        # แต่ template ใช้ w.level / w.msg → ต้องเก็บเป็น list of dicts
        warnings_as_dicts = []
        for w in analysis.get("warnings", []):
            if isinstance(w, dict):
                warnings_as_dicts.append(w)
            else:
                warnings_as_dicts.append({"level": "warning", "msg": str(w)})

        # ---- คำนวณ fields เพิ่มเติมที่ template ต้องการแต่ยังไม่มีใน advanced dict ----
        pack_voltage_nominal = float(comp.get("pack_voltage_nominal", cells * NOMINAL_CELL_V))
        current_draw_a = round(total_power_w / pack_voltage_nominal, 2) if pack_voltage_nominal > 0 else 0
        peak_current_a = round(current_draw_a * 1.8, 2)
        c_required = round((current_draw_a * 1000) / batt_mAh_used, 1) if batt_mAh_used > 0 else None

        stress = analysis.get("motor_esc_stress", "low")
        motor_health = {"high": "⚠️ สูง", "moderate": "⚡ ปานกลาง", "low": "✅ ปกติ"}.get(stress, stress)
        battery_health = "⚠️ ระวัง" if (c_required or 0) > 60 else ("✅ ดี" if (c_required or 0) < 30 else "⚡ ปกติ")

        efficiency_class = analysis.get("efficiency_class", "nominal")

        # KV suggestion
        if motor_kv:
            kv_display = f"{motor_kv} KV (input)"
        elif (size or 5) >= 7:
            kv_display = "900–1500 KV"
        elif (size or 5) >= 5:
            kv_display = "1200–2800 KV"
        else:
            kv_display = "1500–3500 KV"

        # recommendations from warnings
        recs = [w.get("msg", str(w)) for w in warnings_as_dicts] or ["ค่าพื้นฐานดูปกติ — ทดสอบบินจริงเพื่อปรับจูน"]

        # BUG FIX: thrust_ratio เดิม fallback คืน motor_esc_stress string แทนที่จะเป็น number/None
        thrust_ratio_safe = thrust_ratio if isinstance(thrust_ratio, (int, float)) else None

        # Build the advanced dict — รวม flat fields (section 1) + nested power (section 2)
        advanced = {
            # ---- flat fields สำหรับ template section 1 ----
            "cells": int(cells),
            "pack_voltage_nominal": pack_voltage_nominal,
            "battery_mAh_used": int(batt_mAh_used),
            "battery_wh": battery_wh,
            "est_flight_time_min": int(est_flight_time_min),
            "est_flight_time_min_aggr": int(est_flight_time_min_aggressive),
            "avg_power_w": round(total_power_w, 1),
            "current_draw_a": current_draw_a,
            "peak_current_a": peak_current_a,
            "c_required": c_required,
            "thrust_ratio": thrust_ratio_safe,
            "hover_throttle_percent": None,
            "efficiency_class": efficiency_class,
            "motor_health": motor_health,
            "battery_health": battery_health,
            "kv_suggestion": kv_display,
            "recommendations": recs,
            "twr_note": analysis.get("twr_note", ""),
            "prop_notes": prop_result.get("effect", {}).get("notes", []) if isinstance(prop_result, dict) else [],
            "warnings_advanced": warnings_as_dicts,
            # ---- nested power สำหรับ template section 2 ----
            "power": {
                "cells": int(cells),
                "battery_mAh_used": int(batt_mAh_used),
                "battery_wh": battery_wh,
                "est_hover_power_w": round(total_power_w, 1),
                "est_aggressive_power_w": round(total_power_w * 1.8, 1),
                "est_flight_time_min": int(est_flight_time_min),
                "est_flight_time_min_aggressive": int(est_flight_time_min_aggressive),
            },
            "_diagnostics": {
                "raw_analysis": analysis
            }
        }

        return {"advanced": advanced}

    except Exception as e:
        # never raise here — return safe structure
        return {
            "advanced": {
                "power": {},
                "thrust_ratio": 0,
                "twr_note": "",
                "kv_suggestion": "",
                "prop_notes": [],
                "warnings_advanced": [f"advanced wrapper error: {e}"],
                "_diagnostics": {}
            }
        }

# expose both names (compatibility)
__all__ = ["analyze", "make_advanced_report"]
