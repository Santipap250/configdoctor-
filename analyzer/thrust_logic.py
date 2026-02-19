# analyzer/thrust_logic.py (REPLACE)
def calculate_thrust_weight(thrust_g, weight_g, motor_count=None):
    """
    Return dictionary with thrust metrics.
      - thrust_ratio: thrust_total_g / weight_g (unitless)
      - thrust_total_g, weight_g
      - if motor_count provided: thrust_per_motor_g, required_per_motor_g, per_motor_margin_g, per_motor_margin_pct
    """
    try:
        thrust = float(thrust_g)
        weight = float(weight_g)
    except Exception:
        return {"thrust_ratio": 0.0, "error": "invalid numeric"}

    if weight <= 0:
        return {"thrust_ratio": 0.0, "error": "weight must be > 0"}

    thrust_ratio = thrust / weight

    out = {
        "thrust_ratio": round(thrust_ratio, 2),
        "thrust_total_g": float(thrust),
        "weight_g": float(weight),
    }

    if motor_count:
        try:
            m = int(motor_count)
            if m > 0:
                thrust_per_motor = thrust / m
                required_per_motor = weight / m
                per_motor_margin_g = thrust_per_motor - required_per_motor
                per_motor_margin_pct = (per_motor_margin_g / required_per_motor) * 100.0 if required_per_motor != 0 else None
                out.update({
                    "motor_count": m,
                    "thrust_per_motor_g": round(thrust_per_motor, 2),
                    "required_thrust_per_motor_g": round(required_per_motor, 2),
                    "per_motor_margin_g": round(per_motor_margin_g, 2),
                    "per_motor_margin_pct": round(per_motor_margin_pct, 1) if per_motor_margin_pct is not None else None,
                })
        except Exception:
            pass

    return out


def estimate_battery_runtime(weight, battery):
    # keep existing coarse heuristic or improve later
    base = 3.5
    if battery == "4S":
        return round(base * (1500/1000) / (weight if weight>0 else 1) * 4, 1)
    elif battery == "6S":
        return round(base * (1500/1000) / (weight if weight>0 else 1) * 6, 1)
    else:
        return 0