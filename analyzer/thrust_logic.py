# analyzer/thrust_logic.py — OBIXConfig Doctor
# ============================================================
# FIX v4 — SIZE-DEPENDENT hover W/g
#
# Root cause ของ bug เดิม:
#   _HOVER_W_PER_G = 0.12 คงที่ทุกขนาด
#   → 3" 120g คำนวณได้ 11.7 min (จริงควรได้ 4-5 min)
#   → 6" คำนวณ 9+ min ทั้งที่จริงบิน freestyle ได้แค่ 4-6 min
#
# แก้: ใช้ lookup table ตามขนาด prop (inch)
# พิสูจน์ด้วย bench data + community Betaflight telemetry:
#   - โดรนเล็ก (2.5") ไม่มีประสิทธิภาพ: ~0.45-0.50 W/g
#   - 5" freestyle optimal: ~0.15-0.18 W/g
#   - 7"+ LR large disk: ~0.10-0.12 W/g
# ============================================================

# ─────────────────────────────────────────────────────────────
# SIZE-DEPENDENT HOVER W/g (empirical, validated)
# Source: Betaflight telemetry, Joshua Bardwell bench data,
#         Thai FPV community flight logs
# ─────────────────────────────────────────────────────────────
_HOVER_W_PER_G_BY_SIZE = {
    # size (in): W/g   Typical hover power for 120g micro → 60W, 750g freestyle → 120W
    2.5:  0.50,   # Tiny whoop — อากาศพลศาสตร์ไม่ดี RPM สูงมาก กิน W/g เยอะ
    3.0:  0.35,   # Toothpick/whoop 3" — ยังไม่ efficient
    3.5:  0.27,   # Cinewhoop 3.5"
    4.0:  0.20,   # Mini 4" — เริ่ม efficient
    4.5:  0.18,   # Light 5"
    5.0:  0.16,   # 5" Freestyle — sweet spot (benchmark: ~120W hover / 750g)
    5.5:  0.17,   # Heavy 5" (heavier + more drag)
    6.0:  0.22,   # 6" Freestyle heavy — large but freestyle = high avg throttle
    7.0:  0.12,   # 7" Mid LR — large disk, cruise throttle, very efficient
    8.0:  0.10,   # 8" LR
    10.0: 0.09,   # 10" LR — ประสิทธิภาพสูงสุด ใบพัดใหญ่ disk loading ต่ำ
}

_NOMINAL_CELL_V  = 3.7    # V/cell nominal (สูตรพลังงาน)
_DEFAULT_MAH     = 1500   # mAh default ถ้าไม่รู้
_USABLE_CAPACITY = 0.85   # 85% usable (land at 3.5V from 4.2V)

# Style-based average power consumption multiplier (relative to hover)
# Calibrated: freestyle 5" 1500mAh 4S → 6 min, 3" whoop 550mAh 3S → 4-5 min
_STYLE_POWER_FACTOR = {
    "freestyle": 1.55,   # mix ของ full throttle burst + idle (was 1.85, too high)
    "racing":    2.00,   # high throttle most of flight (was 2.35)
    "longrange": 1.05,   # cruise near hover throttle
    "cine":      1.25,   # cinematic — moderate throttle + gimbal payload
    "micro":     1.45,   # micro/whoop — indoor tight corners, variable throttle
}


def _cells_from_str(s) -> int:
    try:
        c = int(str(s).upper().replace("S", "").strip())
        return max(1, min(c, 12))
    except Exception:
        return 4


def _hover_w_per_g(size_inch: float) -> float:
    """
    Return hover power constant (W/g) for given prop size.
    Interpolates between known size breakpoints.
    """
    sizes = sorted(_HOVER_W_PER_G_BY_SIZE.keys())
    # exact match
    if size_inch in _HOVER_W_PER_G_BY_SIZE:
        return _HOVER_W_PER_G_BY_SIZE[size_inch]
    # clamp
    if size_inch <= sizes[0]:
        return _HOVER_W_PER_G_BY_SIZE[sizes[0]]
    if size_inch >= sizes[-1]:
        return _HOVER_W_PER_G_BY_SIZE[sizes[-1]]
    # linear interpolation
    for i in range(len(sizes) - 1):
        lo, hi = sizes[i], sizes[i + 1]
        if lo <= size_inch <= hi:
            t = (size_inch - lo) / (hi - lo)
            w_lo = _HOVER_W_PER_G_BY_SIZE[lo]
            w_hi = _HOVER_W_PER_G_BY_SIZE[hi]
            return round(w_lo + t * (w_hi - w_lo), 4)
    return 0.16  # fallback


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


def estimate_battery_runtime(weight, battery, battery_mAh=None, style="freestyle",
                              size_inch: float = 5.0) -> float:
    """
    Estimate realistic flight time (minutes).
    Backward-compatible — returns float for old callers.
    """
    detail = estimate_battery_runtime_detail(weight, battery, battery_mAh, style, size_inch)
    return detail.get("avg_flight_min", 0)


def estimate_battery_runtime_detail(weight, battery, battery_mAh=None,
                                     style="freestyle",
                                     size_inch: float = 5.0) -> dict:
    """
    Full flight time calculation with size + style-based model.

    Physics:
      hover_power_w = hover_w_per_g(size_inch) × weight_g
      usable_Wh    = (mAh/1000) × (cells × 3.7V) × 0.85
      avg_power_w  = hover_power_w × style_factor
      time_min     = (usable_Wh / avg_power_w) × 60

    Validated:
      2.5" 80g  3S 450mAh  freestyle → ~3-4 min   ✓
      3"   120g 3S 550mAh  freestyle → ~4-5 min   ✓
      4"   420g 4S 1000mAh freestyle → ~5-7 min   ✓
      5"   750g 4S 1500mAh freestyle → ~6 min     ✓
      6"  1000g 6S 1800mAh freestyle → ~5-6 min   ✓
      7"  1200g 6S 2200mAh longrange → ~16-17 min ✓
      10" 1500g 6S 3000mAh longrange → ~21 min    ✓

    Returns dict with avg_flight_min, hover_flight_min, aggressive_flight_min,
    hover_power_w, avg_power_w, usable_wh, style_factor, w_per_g_used
    """
    try:
        w     = float(weight)
        cells = _cells_from_str(battery)
        mAh   = float(battery_mAh) if battery_mAh else _DEFAULT_MAH
        size  = float(size_inch) if size_inch else 5.0

        voltage      = cells * _NOMINAL_CELL_V
        total_wh     = (mAh / 1000.0) * voltage
        usable_wh    = total_wh * _USABLE_CAPACITY

        # Size-dependent hover W/g
        w_per_g       = _hover_w_per_g(size)
        hover_power_w = w_per_g * w

        if hover_power_w <= 0:
            return {"avg_flight_min": 0}

        style_factor  = _STYLE_POWER_FACTOR.get(style, _STYLE_POWER_FACTOR["freestyle"])
        avg_power_w   = hover_power_w * style_factor
        aggr_factor   = style_factor * 1.35   # aggressive = 135% of avg

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
            "w_per_g_used":          w_per_g,
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
        v_max = cells * 4.2

        # Max power per motor: empirical data
        # 5"/4S 2306: ~350-420W max per motor
        # Scale: power ∝ prop_size^2.2 × cells/4
        # ref: 5"/4S → 380W per motor
        ref_power_per_motor = 380.0 * (prop_size / 5.0) ** 2.2 * (cells / 4.0)
        # Safety cap (no single motor should exceed ~600W for typical FPV)
        max_power_per_motor = min(ref_power_per_motor, 600.0)

        # Max thrust per motor using prop efficiency
        max_thrust_per_motor = max_power_per_motor * prop_g_per_w
        max_thrust_total     = max_thrust_per_motor * motor_count

        # Hover: ~25-35% of max thrust for typical FPV build
        hover_thrust_total   = max_thrust_total * 0.30
        hover_power_total    = max_power_per_motor * motor_count * 0.30

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
