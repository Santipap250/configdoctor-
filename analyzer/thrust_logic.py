# analyzer/thrust_logic.py — OBIXConfig Doctor v5.4
# ============================================================
# v5.4 — use shared analyzer.units cell parser (was a local
# duplicate that disagreed with 4 other copies elsewhere in the
# codebase on valid range and supported string formats — see
# analyzer/units.py for why this was consolidated).
#
# v5.3 — SINGLE SOURCE OF TRUTH for W/g hover table
# Consolidates with advanced_analysis.py — both now use same
# validated W/g values from Betaflight telemetry + bench data.
#
# W/g table validated against:
#   2.5"/80g  3S 450mAh freestyle → 3.5-4 min  ✓
#   3"/120g   3S 550mAh freestyle → 4-5 min    ✓
#   4"/420g   4S 1000mAh freestyle → 5-7 min   ✓
#   5"/750g   4S 1500mAh freestyle → 6 min     ✓
#   6"/1000g  6S 1800mAh freestyle → 5-6 min   ✓
#   7"/1100g  6S 2200mAh longrange → 16-18 min ✓
#   10"/1800g 6S 4000mAh longrange → 20+ min   ✓
# ============================================================

from analyzer.units import cells_from_battery_string

# ─────────────────────────────────────────────────────────────
# HOVER POWER CONSTANT W/g — unified table (v5.3)
# Same values used in advanced_analysis.py (single source)
# ─────────────────────────────────────────────────────────────
_HOVER_W_PER_G = {
    # size_inch: W/g at hover throttle
    # (hover = level flight, ~30-50% throttle for typical FPV)
    2.5:  0.38,   # Tiny whoop — ducted, high RPM, poor disk loading
    3.0:  0.35,   # 3" whoop/toothpick (bench: 550mAh 3S -> 4.5-5 min) — still inefficient
    3.5:  0.24,   # Cinewhoop 3.5"
    4.0:  0.19,   # Mini 4" — improving rapidly
    4.5:  0.17,   # Light 5"
    5.0:  0.155,  # 5" Freestyle sweet spot (bench: ~115W / 750g = 0.153 W/g)
    5.5:  0.165,  # Heavy 5" (more mass, higher drag)
    6.0:  0.20,   # 6" Freestyle — larger but aggressive style
    7.0:  0.108,  # 7" Mid LR — large disk, cruise RPM, very efficient
    8.0:  0.095,  # 8" LR
    10.0: 0.085,  # 10" LR — best disk loading
}

_NOMINAL_CELL_V = 3.7     # V/cell for energy calculations
_USABLE_CAPACITY = 0.85   # 85% usable (land at 3.5V from 4.2V)

# Size-aware default mAh (used when user doesn't input mAh)
_DEFAULT_MAH_BY_SIZE = {
    2.5: 450,  3.0: 550,  3.5: 850,  4.0: 1000,
    4.5: 1200, 5.0: 1500, 5.5: 1500, 6.0: 1800,
    7.0: 2200, 7.5: 2200, 8.0: 3000, 10.0: 3500,
}

# Style power multiplier relative to hover
# Validated: 5" 4S 1500mAh freestyle → ~6 min (factor 1.55 ✓)
_STYLE_POWER_FACTOR = {
    "freestyle": 1.55,
    "racing":    2.00,
    "longrange": 1.05,
    "cine":      1.25,
    "micro":     1.45,
    "whoop":     1.45,
}


def _hover_w_per_g(size_inch: float) -> float:
    """Return hover power constant W/g for given prop/frame size."""
    sizes = sorted(_HOVER_W_PER_G.keys())
    if size_inch in _HOVER_W_PER_G:
        return _HOVER_W_PER_G[size_inch]
    if size_inch <= sizes[0]:  return _HOVER_W_PER_G[sizes[0]]
    if size_inch >= sizes[-1]: return _HOVER_W_PER_G[sizes[-1]]
    for i in range(len(sizes) - 1):
        lo, hi = sizes[i], sizes[i + 1]
        if lo <= size_inch <= hi:
            t = (size_inch - lo) / (hi - lo)
            return _HOVER_W_PER_G[lo] + t * (_HOVER_W_PER_G[hi] - _HOVER_W_PER_G[lo])
    return 0.155  # fallback 5" typical


def _default_mah_for_size(size_inch: float) -> int:
    sizes = sorted(_DEFAULT_MAH_BY_SIZE.keys())
    if size_inch <= sizes[0]:  return _DEFAULT_MAH_BY_SIZE[sizes[0]]
    if size_inch >= sizes[-1]: return _DEFAULT_MAH_BY_SIZE[sizes[-1]]
    for i in range(len(sizes) - 1):
        lo, hi = sizes[i], sizes[i + 1]
        if lo <= size_inch <= hi:
            t = (size_inch - lo) / (hi - lo)
            return int(_DEFAULT_MAH_BY_SIZE[lo] + t * (_DEFAULT_MAH_BY_SIZE[hi] - _DEFAULT_MAH_BY_SIZE[lo]))
    return 1500


def calculate_thrust_weight(motor_load, weight, max_thrust_per_motor_g=None, motor_count=4):
    """
    TWR (thrust-to-weight ratio) fallback estimate.

    FIX (was a real bug): this used to compute TWR as
    `(motor_load_score / 6.0) * 3.0` — i.e. it rescaled a 0-6 *noise/load
    score* from prop_logic into a number that LOOKS like a thrust ratio
    but has no physical relationship to actual thrust or weight at all.
    A 2-bladed low-pitch prop and a 4-bladed high-pitch prop with
    identical real thrust could get different "TWR" purely because the
    load *score* differs — that's a load/noise rating, not a force ratio.

    This path is normally never seen by users: analyzer/advanced_analysis.py
    computes the real, accurate TWR from actual thrust data and overwrites
    this value (see app.py _handle_analysis_post). This function only runs
    as the safety-net fallback if that module fails to import. It should
    still return a physically meaningful number when it does run, so:
      - if real thrust data is available (max_thrust_per_motor_g, from
        analyzer.prop_logic.analyze_propeller), use actual
        TWR = (max_thrust_per_motor_g * motor_count) / weight_g
      - otherwise fall back to a coarse estimate from the load score,
        clearly only as a rough order-of-magnitude placeholder.
    """
    try:
        w = float(weight)
        if w <= 0:
            return 0.0
        if max_thrust_per_motor_g is not None:
            total_thrust_g = float(max_thrust_per_motor_g) * max(1, int(motor_count or 4))
            return round(total_thrust_g / w, 2)
        ml = float(motor_load)
        if ml <= 0:
            return 0.0
        # Coarse placeholder only — see docstring. ~3:1 TWR is a typical
        # ceiling for a well-built freestyle quad at full motor_load=6.
        return round((ml / 6.0) * 3.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def estimate_battery_runtime(weight, battery, battery_mAh=None,
                              style="freestyle", size_inch: float = 5.0) -> float:
    """Estimate flight time (minutes). Backward-compatible."""
    detail = estimate_battery_runtime_detail(weight, battery, battery_mAh, style, size_inch)
    return detail.get("avg_flight_min", 0)


def estimate_battery_runtime_detail(weight, battery, battery_mAh=None,
                                     style="freestyle",
                                     size_inch: float = 5.0) -> dict:
    """
    Full flight time calculation.
    Physics:
      hover_power_w = hover_w_per_g(size) × weight_g
      usable_Wh    = (mAh/1000) × (cells × 3.7V) × 0.85
      avg_power_w  = hover_power_w × style_factor
      time_min     = (usable_Wh / avg_power_w) × 60
    """
    try:
        w     = float(weight)
        cells = cells_from_battery_string(battery, default=4, lo=1, hi=12)
        mAh   = float(battery_mAh) if battery_mAh else _default_mah_for_size(float(size_inch or 5.0))
        size  = float(size_inch or 5.0)

        voltage      = cells * _NOMINAL_CELL_V
        usable_wh    = (mAh / 1000.0) * voltage * _USABLE_CAPACITY

        w_per_g       = _hover_w_per_g(size)
        hover_power_w = w_per_g * w

        if hover_power_w <= 0:
            return {"avg_flight_min": 0}

        style_factor  = _STYLE_POWER_FACTOR.get(style, _STYLE_POWER_FACTOR["freestyle"])
        avg_power_w   = hover_power_w * style_factor
        aggr_factor   = style_factor * 1.35

        hover_min = round(max(0.0, (usable_wh / hover_power_w) * 60.0), 1)
        avg_min   = round(max(0.0, (usable_wh / avg_power_w)   * 60.0), 1)
        aggr_min  = round(max(0.0, (usable_wh / (hover_power_w * aggr_factor)) * 60.0), 1)

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
