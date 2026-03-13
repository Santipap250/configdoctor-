# analyzer/advanced_analysis.py — OBIXConfig Doctor
# ============================================================
# v5.0 — SMART UPGRADE
# ใหม่:
# - Power model ใช้ max_power_per_motor จาก prop_logic (KV+size aware)
# - TWR ใช้ max_thrust จาก prop_logic จริง (ไม่ circular แล้ว)
# - ESC sizing recommendation (A continuous + burst)
# - Hover throttle % estimate
# - C-rating แยก burst vs continuous
# - Per-style สูตร flight time ที่แม่นขึ้น
# - Motor temp / stress ละเอียดขึ้น
# ============================================================
from __future__ import annotations
import math
import json
from typing import Dict, Any, Optional

NOMINAL_CELL_V   = 3.7
MAX_CELL_V       = 4.2
KV_THRESHOLD_HIGH = 1500
HIGH_VOLTAGE_CELLS = 7
DEFAULT_MOTORS   = 4

_DEFAULT_BATT_MAH_BY_SIZE = {
    2.5: {3:450,4:450},
    3.0: {3:550,4:650},
    3.5: {3:650,4:850},
    4.0: {3:850,4:1000},
    5.0: {4:1500,5:1300,6:1100},
    6.0: {4:1800,5:1500,6:1300},
    7.0: {5:2200,6:2200,7:1500},
    8.0: {6:3000,7:2200,8:1800}
}

# W/g hover table — calibrated v5.1 against real-world flight data
# 2.5-3.5": original 0.50/0.35/0.27 overestimated hover power → low flight time
# Corrected: 2.5"=0.187, 3"=0.183, 3.5"=0.243 (matches real Mobula7/toothpick data)
_W_PER_G_TABLE = {
    2.5:0.187, 3.0:0.183, 3.5:0.243, 4.0:0.195,
    4.5:0.175, 5.0:0.150, 5.5:0.160, 6.0:0.185,
    7.0:0.105, 8.0:0.095, 10.0:0.086,
}

# Style × size flight power factor
# Higher style factor = burns more power relative to hover
# Also varies by size (big LR doesn't have same style impact as 5" freestyle)
_STYLE_FACTORS = {
    "freestyle": 1.55, "racing": 2.00,
    "longrange": 1.05, "cine": 1.25,
    "micro": 1.45, "whoop": 1.45,
}


def _cells_from_str(s):
    try:
        c = int(str(s).upper().replace("S","").strip())
        return max(1, min(c,8))  # FIX v5.1: min=3→1 (รองรับ 1S-2S builds)
    except Exception:
        return 4

def _guess_batt_mAh(size_inch, cells):
    keys = sorted(_DEFAULT_BATT_MAH_BY_SIZE.keys())
    closest = min(keys, key=lambda k: abs(k-size_inch))
    table = _DEFAULT_BATT_MAH_BY_SIZE[closest]
    if cells in table: return table[cells]
    available = sorted(table.keys())
    return table[min(available, key=lambda c: abs(c-cells))]

def _hover_w_per_g(size_inch):
    sizes = sorted(_W_PER_G_TABLE.keys())
    if size_inch <= sizes[0]:  return _W_PER_G_TABLE[sizes[0]]
    if size_inch >= sizes[-1]: return _W_PER_G_TABLE[sizes[-1]]
    for i in range(len(sizes)-1):
        lo,hi = sizes[i],sizes[i+1]
        if lo <= size_inch <= hi:
            t = (size_inch-lo)/(hi-lo)
            return _W_PER_G_TABLE[lo] + t*(_W_PER_G_TABLE[hi]-_W_PER_G_TABLE[lo])
    return 0.16

def analyze(size_inch=5.0, cell_input=4, batt_mAh=None, motor_kv=None,
            weight_g=1000.0, motors=DEFAULT_MOTORS, hover_throttle=None,
            thrust_per_motor_g=None):
    """Core analysis (backward compat)."""
    cells = _cells_from_str(str(cell_input))
    if batt_mAh is None: batt_mAh = _guess_batt_mAh(size_inch, cells)
    pack_voltage_nominal = round(cells * NOMINAL_CELL_V, 2)
    pack_voltage_max     = round(cells * MAX_CELL_V, 2)
    # FIX v5.1: guard motors ≤ 0 to prevent ZeroDivisionError
    safe_motors = max(1, int(motors or DEFAULT_MOTORS))
    if thrust_per_motor_g is None:
        hover_thrust_total_g = weight_g * 2.0
        thrust_per_motor_g   = hover_thrust_total_g / float(safe_motors)
    sizes = sorted(_W_PER_G_TABLE.keys())
    _s = float(size_inch or 5.0)
    if _s <= sizes[0]:  W_PER_GRAM = _W_PER_G_TABLE[sizes[0]]
    elif _s >= sizes[-1]: W_PER_GRAM = _W_PER_G_TABLE[sizes[-1]]
    else:
        W_PER_GRAM = 0.16
        for _i in range(len(sizes)-1):
            _lo,_hi = sizes[_i],sizes[_i+1]
            if _lo <= _s <= _hi:
                _t = (_s-_lo)/(_hi-_lo)
                W_PER_GRAM = _W_PER_G_TABLE[_lo] + _t*(_W_PER_G_TABLE[_hi]-_W_PER_G_TABLE[_lo])
                break
    total_power_w = W_PER_GRAM * weight_g
    power_per_motor_w = total_power_w / float(safe_motors)
    current_a = total_power_w / pack_voltage_nominal if pack_voltage_nominal > 0 else 0.0
    c_rating  = (current_a * 1000.0) / batt_mAh if batt_mAh > 0 else float('inf')
    warnings  = []
    if cells >= HIGH_VOLTAGE_CELLS:
        warnings.append({"level":"warning","msg":"แรงดันสูง (7S–8S) — ตรวจสอบ ESC, capacitor และ motor KV"})
    if motor_kv:
        if cells >= 7 and motor_kv > KV_THRESHOLD_HIGH:
            warnings.append({"level":"danger","msg":f"Motor KV {motor_kv} สูงเกินไปสำหรับ {cells}S"})
        elif cells <= 3 and motor_kv < KV_THRESHOLD_HIGH:
            warnings.append({"level":"warning","msg":f"Motor KV {motor_kv} ต่ำสำหรับ {cells}S"})
    stress_score = 0; stress_reasons = []
    if current_a > 30: stress_score += 1; stress_reasons.append(f"Current {current_a:.1f}A > 30A")
    if motor_kv and cells >= 7 and motor_kv > KV_THRESHOLD_HIGH: stress_score += 1
    if c_rating > 60: stress_score += 0.8; stress_reasons.append(f"C-rating {c_rating:.1f}C สูง")
    motor_esc_stress = "high" if stress_score>=2 else ("moderate" if stress_score>=1 else "low")
    efficiency_class = "nominal"
    if hover_throttle:
        if cells<=3 and hover_throttle>0.6: efficiency_class="danger_low_voltage"
        elif cells>=7 and hover_throttle<0.25: efficiency_class="overpowered"
    return {
        "input":{"size_inch":size_inch,"cells":cells,"batt_mAh":batt_mAh,"motor_kv":motor_kv,
                 "weight_g":weight_g,"motors":motors,"hover_throttle":hover_throttle},
        "computed":{"pack_voltage_nominal":pack_voltage_nominal,"pack_voltage_max":pack_voltage_max,
                    "power_w":round(total_power_w,1),"current_a":round(current_a,2),
                    "implied_c_rating":round(c_rating,1) if math.isfinite(c_rating) else None},
        "motor_esc_stress":motor_esc_stress, "stress_reasons":stress_reasons,
        "efficiency_class":efficiency_class,
        "warnings":warnings,
        "diagnostics":{"battery_cells":cells,"battery_voltage_nominal":pack_voltage_nominal,
                       "battery_voltage_max":pack_voltage_max,"battery_mAh_used":batt_mAh,
                       "estimated_hover_thrust_per_motor_g":round(thrust_per_motor_g,1),
                       "motors":motors},
    }


def make_advanced_report(
    size: float, weight_g: float, battery_s: str,
    prop_result: Dict[str, Any], style: str,
    battery_mAh: Optional[int] = None,
    motor_count: int = DEFAULT_MOTORS,
    measured_thrust_per_motor_g: Optional[float] = None,
    motor_kv: Optional[int] = None,
    esc_current_limit_a: Optional[float] = None,
    blades: Optional[int] = None,
    payload_g: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Smart analysis wrapper — v5.
    Uses prop_result.effect.max_power_per_motor_w and max_thrust_per_motor_g
    from prop_logic v4 for much more accurate TWR, ESC sizing, and flight time.
    """
    try:
        cells = _cells_from_str(str(battery_s))
        total_weight_g = float((weight_g or 0) + (payload_g or 0))
        size_f = float(size or 5.0)

        # ── Battery ───────────────────────────────────────────
        batt_mAh_used = int(battery_mAh or _guess_batt_mAh(size_f, cells))
        pack_voltage  = cells * NOMINAL_CELL_V
        battery_wh    = round((batt_mAh_used / 1000.0) * pack_voltage, 2)
        usable_wh     = battery_wh * 0.85

        # ── Power model (prop-aware) ──────────────────────────
        eff   = prop_result.get("effect", {}) if isinstance(prop_result, dict) else {}
        g_per_w      = eff.get("est_g_per_w")
        max_pwr_m    = eff.get("max_power_per_motor_w")   # NEW from prop_logic v4
        max_thr_m    = eff.get("max_thrust_per_motor_g")  # NEW from prop_logic v4
        tip_speed    = eff.get("tip_speed_mps")
        rpm_est      = eff.get("rpm_estimated")

        # Hover power: W/g × total_weight (size-aware)
        w_per_g      = _hover_w_per_g(size_f)
        hover_power_w = w_per_g * total_weight_g

        # Total max power (all motors)
        if max_pwr_m:
            max_power_total_w = float(max_pwr_m) * int(motor_count or 4)
        else:
            # fallback from analyze()
            max_power_total_w = hover_power_w * 8.0  # rough: hover ≈ 12% of max

        # Style average power
        style_factor = _STYLE_FACTORS.get(str(style).lower(), 1.55)
        avg_power_w  = hover_power_w * style_factor

        # ── Flight time ───────────────────────────────────────
        if avg_power_w > 0:
            est_ft_min      = int(max(0, round((usable_wh / avg_power_w) * 60.0)))
            est_ft_min_aggr = int(max(0, round((usable_wh / (avg_power_w * 1.35)) * 60.0)))
        else:
            est_ft_min = est_ft_min_aggr = 0

        # ── TWR — best available data ─────────────────────────
        thrust_ratio = None
        if measured_thrust_per_motor_g:
            # Best: actual bench data
            total_thr = float(measured_thrust_per_motor_g) * int(motor_count or 4)
            thrust_ratio = round(total_thr / (total_weight_g or 1.0), 2)
        elif max_thr_m:
            # Good: from prop_logic v4 (KV + size aware)
            total_thr = float(max_thr_m) * int(motor_count or 4)
            thrust_ratio = round(total_thr / (total_weight_g or 1.0), 2)
        elif g_per_w:
            # Fallback: g/W × hover_power × 2 (v2.3g method)
            total_thr = float(g_per_w) * hover_power_w * 2.0
            thrust_ratio = round(total_thr / (total_weight_g or 1.0), 2)
        else:
            _style_twr = {"freestyle":2.0,"racing":2.5,"longrange":1.4,"cine":1.2,"micro":2.2}
            thrust_ratio = _style_twr.get(str(style).lower(), 2.0)

        # Sanity clamp: TWR 0.5–6.0 (anything outside is likely a calculation error)
        if thrust_ratio:
            thrust_ratio = round(max(0.5, min(thrust_ratio, 12.0)), 2)

        # ── Hover throttle % (STICK POSITION) ───────────────
        # Thrust ∝ stick²  →  hover_stick = sqrt(1/TWR) × 100
        # Gives actual stick% pilot sees at hover
        hover_throttle_pct = None
        _twr_for_hover = thrust_ratio if isinstance(thrust_ratio,(int,float)) and thrust_ratio > 0 else None
        if _twr_for_hover:
            hover_throttle_pct = round(math.sqrt(1.0/_twr_for_hover)*100.0, 1)
            hover_throttle_pct = max(15.0, min(hover_throttle_pct, 85.0))

        # ── Current calculations ──────────────────────────────
        # Hover current
        hover_current_a = round(hover_power_w / pack_voltage, 2) if pack_voltage > 0 else 0

        # Peak current per motor at full throttle
        if max_pwr_m:
            peak_per_motor_a = round(float(max_pwr_m) / pack_voltage, 1)
        else:
            peak_per_motor_a = round(hover_current_a / int(motor_count or 4) * 4.5, 1)

        peak_current_total_a = round(peak_per_motor_a * int(motor_count or 4), 1)

        # Average current (at style duty cycle)
        avg_current_a = round(avg_power_w / pack_voltage, 2) if pack_voltage > 0 else 0

        # ── C-rating ─────────────────────────────────────────
        # Continuous: based on avg_current
        c_continuous = round((avg_current_a * 1000) / batt_mAh_used, 1) if batt_mAh_used > 0 else None
        # Burst: based on peak_current_total
        c_burst      = round((peak_current_total_a * 1000) / batt_mAh_used, 1) if batt_mAh_used > 0 else None
        # Recommended battery C-rating (burst × safety 1.2)
        c_recommended = round(c_burst * 1.2, 0) if c_burst else None

        # ── ESC sizing ────────────────────────────────────────
        # ESC sizing: 1.5× safety factor + practical minimum by build size
        esc_raw = peak_per_motor_a * 1.5
        _size_esc_min = {2.5:15,3.0:20,3.5:20,4.0:25,5.0:30,6.0:35,7.0:40,10.0:45}
        _esc_keys = sorted(_size_esc_min.keys())
        _sz = float(size or 5.0)
        _min_esc = _size_esc_min[min(_esc_keys, key=lambda k: abs(k-_sz))]
        esc_raw = max(esc_raw, _min_esc)
        _esc_sizes = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 100]
        esc_recommended_a = next((s for s in _esc_sizes if s >= esc_raw), 100)

        # ── KV suggestion ─────────────────────────────────────
        if motor_kv:
            kv_display = f"{motor_kv} KV (input)"
        elif size_f >= 7:  kv_display = "900–1500 KV"
        elif size_f >= 5:  kv_display = "1600–2800 KV"
        else:              kv_display = "2000–3500 KV"

        # ── Stress / health ───────────────────────────────────
        analysis_raw = analyze(size_f, cells, batt_mAh_used, motor_kv, total_weight_g,
                               int(motor_count or 4))
        stress = analysis_raw.get("motor_esc_stress","low")

        # More nuanced health based on actual C-rating
        if c_burst and c_burst > 80:
            motor_health   = "🔥 ร้อนมาก (C-burst สูง)"
            battery_health = "⚠️ แบตรับไม่ไหว"
        elif c_burst and c_burst > 60:
            motor_health   = "⚡ โหลดสูง"
            battery_health = "⚠️ ระวัง"
        elif c_burst and c_burst > 40:
            motor_health   = "⚡ ปานกลาง"
            battery_health = "⚡ ปกติ"
        else:
            motor_health   = {"high":"⚠️ สูง","moderate":"⚡ ปานกลาง","low":"✅ ปกติ"}.get(stress,stress)
            battery_health = "✅ ดี" if (c_burst or 0) < 30 else "⚡ ปกติ"

        # ── Tip speed warning ─────────────────────────────────
        tip_warn = None
        if tip_speed:
            if tip_speed >= 290:
                tip_warn = {"level":"danger","msg":f"Tip speed {tip_speed} m/s เกิน 290 m/s — compressibility loss รุนแรง"}
            elif tip_speed >= 265:
                tip_warn = {"level":"warning","msg":f"Tip speed {tip_speed} m/s ใกล้ขีดจำกัด (265 m/s)"}

        # ── Warnings ─────────────────────────────────────────
        raw_warns = analysis_raw.get("warnings",[])
        warnings_as_dicts = [w if isinstance(w,dict) else {"level":"warning","msg":str(w)} for w in raw_warns]
        if tip_warn: warnings_as_dicts.append(tip_warn)
        if esc_current_limit_a and peak_per_motor_a > esc_current_limit_a:
            warnings_as_dicts.append({"level":"danger",
                "msg":f"Peak current/motor {peak_per_motor_a}A เกิน ESC limit {esc_current_limit_a}A!"})

        recs = [w.get("msg","") for w in warnings_as_dicts] or ["ค่าพื้นฐานดูปกติ — ทดสอบบินจริงเพื่อปรับจูน"]

        # ── Assemble advanced dict ────────────────────────────
        advanced = {
            # Battery
            "cells":              int(cells),
            "pack_voltage_nominal": pack_voltage,
            "battery_mAh_used":   int(batt_mAh_used),
            "battery_wh":         battery_wh,
            "usable_wh":          round(usable_wh, 2),
            # Power
            "avg_power_w":        round(avg_power_w, 1),
            "hover_power_w":      round(hover_power_w, 1),
            "max_power_total_w":  round(max_power_total_w, 1),
            # Current
            "hover_current_a":    hover_current_a,
            "avg_current_a":      avg_current_a,
            "peak_current_a":     peak_current_total_a,
            "peak_per_motor_a":   peak_per_motor_a,
            # C-rating
            "c_continuous":       c_continuous,
            "c_burst":            c_burst,
            "c_recommended":      c_recommended,
            # ESC
            "esc_recommended_a":  esc_recommended_a,
            # Throttle
            "hover_throttle_pct": hover_throttle_pct,
            # Flight time
            "est_flight_time_min":      est_ft_min,
            "est_flight_time_min_aggr": est_ft_min_aggr,
            # TWR
            "thrust_ratio":       thrust_ratio if isinstance(thrust_ratio,(int,float)) else None,
            # Motor
            "motor_health":       motor_health,
            "battery_health":     battery_health,
            "efficiency_class":   analysis_raw.get("efficiency_class","nominal"),
            "kv_suggestion":      kv_display,
            # Prop physics
            "tip_speed_mps":      tip_speed,
            "rpm_estimated":      rpm_est,
            # Recommendations
            "recommendations":    recs,
            "twr_note":           "",
            "prop_notes":         eff.get("notes",[]),
            "warnings_advanced":  warnings_as_dicts,
            # Nested power block (template section 2 compat)
            "power": {
                "cells":                     int(cells),
                "battery_mAh_used":          int(batt_mAh_used),
                "battery_wh":                battery_wh,
                "usable_wh":                 round(usable_wh,2),
                "est_hover_power_w":         round(hover_power_w,1),
                "est_max_power_w":           round(max_power_total_w,1),
                "est_flight_time_min":       est_ft_min,
                "est_flight_time_min_aggressive": est_ft_min_aggr,
                "hover_throttle_pct":        hover_throttle_pct,
                "esc_recommended_a":         esc_recommended_a,
                "c_burst":                   c_burst,
                "c_continuous":              c_continuous,
                "c_recommended":             c_recommended,
            },
            "_diagnostics": {"raw_analysis": analysis_raw}
        }
        return {"advanced": advanced}

    except Exception as e:
        return {"advanced":{
            "power":{},"thrust_ratio":0,"twr_note":"","kv_suggestion":"",
            "prop_notes":[],"warnings_advanced":[f"advanced wrapper error: {e}"],
            "_diagnostics":{}
        }}

__all__ = ["analyze","make_advanced_report"]

# ── CLI entry point (compat) ────────────────────────────────────
def main(argv=None):
    import sys
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--size",type=float,default=5.0)
    p.add_argument("--cells",type=str,default="4")
    p.add_argument("--batt-mAh",type=int,default=None)
    p.add_argument("--motor-kv",type=int,default=None)
    p.add_argument("--weight",type=float,default=1000.0)
    p.add_argument("--motors",type=int,default=DEFAULT_MOTORS)
    args = p.parse_args(argv)
    cells = _cells_from_str(str(args.cells))
    res = analyze(args.size,cells,args.batt_mAh,args.motor_kv,args.weight,args.motors)
    print(json.dumps(res,indent=2,ensure_ascii=False))

if __name__=="__main__":
    import sys
    try: main()
    except KeyboardInterrupt: sys.exit(0)
