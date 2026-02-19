# analyzer/thrust_logic.py
"""
Thrust & TWR utilities.
Functions here accept thrust in grams and weight in grams.
Returns detailed dicts for UI and logic.
"""

from typing import Optional

def calculate_thrust_weight(thrust_g: float, weight_g: float, motor_count: Optional[int] = None) -> dict:
    """
    Calculate thrust metrics.

    Inputs:
      - thrust_g: total thrust (grams)
      - weight_g: total vehicle weight (grams)
      - motor_count: number of motors (optional)

    Returns dict:
      - thrust_ratio (float) = thrust_total / weight_total (unitless)
      - thrust_total_g, weight_g
      - if motor_count provided: thrust_per_motor_g, required_thrust_per_motor_g, per_motor_margin_g, per_motor_margin_pct
      - error (str) optional on invalid input
    """
    out = {
        "thrust_ratio": 0.0,
        "thrust_total_g": 0.0,
        "weight_g": 0.0
    }

    # sanitize inputs
    try:
        thrust = float(thrust_g)
        weight = float(weight_g)
    except Exception as e:
        out["error"] = f"invalid numeric: {e}"
        return out

    out["thrust_total_g"] = round(thrust, 2)
    out["weight_g"] = round(weight, 2)

    if weight <= 0:
        out["error"] = "weight must be > 0"
        return out

    # core metric
    thrust_ratio = thrust / weight
    out["thrust_ratio"] = round(thrust_ratio, 3)

    # per-motor breakdown if requested
    if motor_count is not None:
        try:
            m = int(motor_count)
            if m <= 0:
                raise ValueError("motor_count must be > 0")
            thrust_per_motor = thrust / m
            required_per_motor = weight / m
            per_motor_margin_g = thrust_per_motor - required_per_motor
            per_motor_margin_pct = None
            if required_per_motor != 0:
                per_motor_margin_pct = (per_motor_margin_g / required_per_motor) * 100.0

            out.update({
                "motor_count": m,
                "thrust_per_motor_g": round(thrust_per_motor, 2),
                "required_thrust_per_motor_g": round(required_per_motor, 2),
                "per_motor_margin_g": round(per_motor_margin_g, 2),
                "per_motor_margin_pct": round(per_motor_margin_pct, 1) if per_motor_margin_pct is not None else None
            })
        except Exception as e:
            out["error"] = f"motor_count invalid: {e}"

    return out


def estimate_battery_runtime_kw_estimate(total_weight_g: float, battery_cells: Optional[int] = None, avg_consumption_w: Optional[float]=None) -> dict:
    """
    Simple battery runtime heuristic.
    - total_weight_g: grams
    - battery_cells: 4, 6, 8 (S)
    - avg_consumption_w: optional override
    Returns dict with estimation in minutes (approx).
    NOTE: This is heuristic — replace with measured flight current when available.
    """
    res = {"estimated_minutes": 0.0}
    try:
        weight = float(total_weight_g)
    except Exception:
        res["error"] = "invalid weight"
        return res

    # default energy per cell (approx Wh per 1500mAh cell depending on S and mAh)
    # simple model: energy_wh = cell_voltage * capacity_ah * cells
    # assume 1500 mAh standard for small multirotors for baseline
    cap_ah = 1.5  # baseline 1500mAh
    cell_voltage = 3.7
    if battery_cells is None:
        battery_cells = 4

    try:
        cells = int(battery_cells)
    except Exception:
        cells = 4

    energy_wh = cell_voltage * cap_ah * cells

    # default average power consumption guess (W). Use a small model that grows with weight.
    if avg_consumption_w is None:
        # baseline consumption (W) per gram scaled — these constants are heuristic
        avg_consumption_w = max(50.0, (weight / 1000.0) * 150.0)

    # runtime minutes = (energy_wh / avg_consumption_w) * 60
    if avg_consumption_w <= 0:
        res["estimated_minutes"] = 0.0
    else:
        minutes = (energy_wh / avg_consumption_w) * 60.0
        res["estimated_minutes"] = round(minutes, 1)
        res["energy_wh"] = round(energy_wh, 2)
        res["avg_consumption_w"] = round(avg_consumption_w, 1)

    return res
