# analyzer/thrust_logic.py
"""Thrust & battery estimation helpers."""

from typing import Optional, Dict


def calculate_thrust_weight(thrust_g: float, weight_g: float, motor_count: Optional[int] = None) -> Dict:
    """
    Compute thrust metrics.

    Args:
      thrust_g: total thrust (grams)
      weight_g: total vehicle weight (grams)
      motor_count: optional number of motors

    Returns:
      dict with:
        - thrust_ratio (rounded float)
        - thrust_total_g, weight_g
        - motor_count (if provided)
        - thrust_per_motor_g, required_thrust_per_motor_g,
          per_motor_margin_g, per_motor_margin_pct (if motor_count provided)
        - error (optional string)
    """
    out = {
        "thrust_ratio": 0.0,
        "thrust_total_g": float(thrust_g) if thrust_g is not None else 0.0,
        "weight_g": float(weight_g) if weight_g is not None else 0.0,
    }

    # validate numerics
    try:
        thrust = float(out["thrust_total_g"])
        weight = float(out["weight_g"])
    except Exception:
        out["error"] = "invalid numeric"
        return out

    if weight <= 0:
        out["error"] = "weight must be > 0"
        return out

    thrust_ratio = thrust / weight
    out["thrust_ratio"] = round(thrust_ratio, 2)

    if motor_count:
        try:
            m = int(motor_count)
            if m > 0:
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
                    "per_motor_margin_pct": round(per_motor_margin_pct, 1) if per_motor_margin_pct is not None else None,
                })
        except Exception:
            # keep result without motor details
            pass

    return out


def estimate_battery_runtime_wh(consumption_w: float, battery_wh: float) -> float:
    """
    Simple runtime estimate in minutes: battery_wh / consumption_w * 60
    (caller should compute consumption_w or use heuristic)
    """
    try:
        c = float(consumption_w)
        b = float(battery_wh)
    except Exception:
        return 0.0
    if c <= 0:
        return 0.0
    return round((b / c) * 60.0, 1)