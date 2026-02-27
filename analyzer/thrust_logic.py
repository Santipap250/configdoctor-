# analyzer/thrust_logic.py — OBIXConfig Doctor
# ============================================================
# IMPROVED v3:
# - Style-based power factor (freestyle กิน 1.85x hover)
# - 85% usable battery capacity (land at 3.5V/cell)
# - คืน dict พร้อม normal + aggressive flight time
# - estimate_thrust_from_prop() ใหม่ใช้ข้อมูลจาก prop_logic
# ============================================================

_NOMINAL_CELL_V  = 3.7    # V/cell nominal (สูตรพลังงาน)
_DEFAULT_MAH     = 1500   # mAh default ถ้าไม่รู้
_USABLE_CAPACITY = 0.85   # 85% usable (land at 3.5V from 4.2V)

# Style-based average power consumption multiplier (relative to hover)
# Hover = 1.0 (0.12 W/g)
# Freestyle = 1.85 (mix ของ full throttle burst + idle)
# Racing = 2.35 (high throttle most of flight)
# Longrange = 0.95 (cruise near hover throttle)
_STYLE_POWER_FACTOR = {
    "freestyle": 1.85,
    "racing":    2.35,
    "longrange": 1.05,
}
_HOVER_W_PER_G = 0.12   # empirical hover: 0.12 W/g (well-validated for multirotor)


def _cells_from_str(s) -> int:
    try:
        c = int(str(s).upper().replace("S", "").strip())
        return max(1, min(c, 12))
    except Exception:
        return 4


def calculate_thrust_weight(motor_load, weight):
    """
    Rough TWR estimate from motor_load score (0–6).
    Returns None if data insufficient.
    advanced_analysis.py overrides this with real data when available.
    """
    try:
        w  = float(weight)
        ml = float(motor_load)
        if w <= 0 or ml <= 0:
            return None
        # score 0-6 → TWR 0-3.0 (rough)
        return round((ml / 6.0) * 3.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def estimate_battery_runtime(weight, battery, battery_mAh=None, style="freestyle"):
    """
    Estimate realistic flight time (minutes) with style-based power consumption.

    Formula:
      usable_Wh = (mAh / 1000) * (cells * 3.7V) * 0.85
      avg_power  = hover_power * style_factor
      time_min   = (usable_Wh / avg_power) * 60

    Returns float (minutes) for backward compatibility.
    Call estimate_battery_runtime_detail() for full dict.
    """
    detail = estimate_battery_runtime_detail(weight, battery, battery_mAh, style)
    return detail.get("avg_flight_min", 0)


def estimate_battery_runtime_detail(weight, battery, battery_mAh=None, style="freestyle"):
    """
    Full flight time calculation with style-based model.
    Returns dict:
      {
        avg_flight_min:       float  (realistic average for style)
        hover_flight_min:     float  (theoretical max at hover throttle only)
        aggressive_flight_min:float  (absolute minimum aggressive flight)
        hover_power_w:        float
        avg_power_w:          float
        usable_wh:            float
        style_factor:         float
      }
    """
    try:
        w     = float(weight)
        cells = _cells_from_str(battery)
        mAh   = float(battery_mAh) if battery_mAh else _DEFAULT_MAH

        voltage      = cells * _NOMINAL_CELL_V
        total_wh     = (mAh / 1000.0) * voltage
        usable_wh    = total_wh * _USABLE_CAPACITY

        hover_power_w = _HOVER_W_PER_G * w
        if hover_power_w <= 0:
            return {"avg_flight_min": 0}

        style_factor  = _STYLE_POWER_FACTOR.get(style, _STYLE_POWER_FACTOR["freestyle"])
        avg_power_w   = hover_power_w * style_factor
        aggr_factor   = style_factor * 1.4   # aggressive = 140% of avg

        hover_min  = round(max(0.0, (usable_wh / hover_power_w) * 60.0), 1)
        avg_min    = round(max(0.0, (usable_wh / avg_power_w)   * 60.0), 1)
        aggr_min   = round(max(0.0, (usable_wh / (hover_power_w * aggr_factor)) * 60.0), 1)

        return {
            "avg_flight_min":        avg_min,
            "hover_flight_min":      hover_min,
            "aggressive_flight_min": aggr_min,
            "hover_power_w":         round(hover_power_w, 1),
            "avg_power_w":           round(avg_power_w, 1),
            "usable_wh":             round(usable_wh, 2),
            "style_factor":          style_factor,
        }
    except Exception:
        return {"avg_flight_min": 0}


def estimate_thrust_from_motors(
    motor_count: int,
    motor_kv: int,
    cells: int,
    prop_g_per_w: float,
    prop_size: float,
) -> dict:
    """
    Estimate max thrust (g) and hover TWR given motor/prop/battery specs.
    Uses g_per_w efficiency from prop_logic.

    Args:
        motor_count:  number of motors
        motor_kv:     motor KV
        cells:        battery cells
        prop_g_per_w: from prop_logic.effect.est_g_per_w
        prop_size:    prop diameter (inches)

    Returns dict: {
        est_max_thrust_g, est_hover_thrust_g,
        est_max_power_w, est_hover_power_w,
        notes
    }
    """
    try:
        # Max voltage (fully charged)
        v_max = cells * 4.2
        # Max RPM (unloaded) — approximate
        rpm_max = motor_kv * v_max
        # RPM under load ~80%
        rpm_load = rpm_max * 0.80
        # Power per motor at full throttle — empirical for typical build
        # P = k * RPM^2 (simplified) — we use prop_g_per_w as efficiency proxy
        # Typical max power per motor: for 5" 2306 2400KV 4S ≈ 250-350W max
        # Scale by prop size: 5" → 300W ref
        ref_power_per_motor = 60.0 * (prop_size / 5.0) ** 2.2 * (cells / 4.0)
        max_power_per_motor = min(ref_power_per_motor, 500.0)

        # Max thrust per motor
        max_thrust_per_motor = max_power_per_motor * prop_g_per_w
        max_thrust_total     = max_thrust_per_motor * motor_count

        # Hover: ~25-35% of max thrust
        hover_thrust_total   = max_thrust_total * 0.35
        hover_power_total    = max_power_per_motor * motor_count * 0.35

        notes = []
        if cells >= 7 and motor_kv > 1600:
            notes.append("KV สูงบน 7S+ — เสี่ยงมอเตอร์ร้อน ควรใช้ KV ≤ 1500")
        if prop_size >= 7 and motor_kv > 2000:
            notes.append("Prop ใหญ่ + KV สูง — โหลดหนักมาก ควรใช้ KV ต่ำลง")

        return {
            "est_max_thrust_g":    round(max_thrust_total),
            "est_hover_thrust_g":  round(hover_thrust_total),
            "est_max_power_w":     round(max_power_per_motor * motor_count, 1),
            "est_hover_power_w":   round(hover_power_total, 1),
            "notes":               notes,
        }
    except Exception:
        return {}
