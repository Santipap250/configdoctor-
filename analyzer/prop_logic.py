# analyzer/prop_logic.py — OBIXConfig Doctor
# ============================================================
# v4.0 — SMART UPGRADE
# ใหม่:
# - RPM คำนวณจาก KV × V จริง (motor_kv + cells)
# - g/W ปรับตาม cells/voltage
# - Tip speed (m/s) + warning > 265/290 m/s
# - Max thrust per motor (g) + max power per motor (W)
# - Blade chord efficiency correction
# ============================================================
import math
from typing import Optional

_G_PER_W_BASE = {
    # FIX v5.1: ปรับลงจาก bench data จริง (Nazgul5/Tyro129/T-motor/RCBenchmark)
    # เดิม med_pitch 3-blade = 5.2 g/W → thrust ต่อ motor ออกมา ~1183g (สูงกว่าจริง 40%)
    # แก้เป็น 4.3 g/W → thrust ~960g (ยังสูงกว่า conservative bench แต่ reasonable average)
    # low_pitch: efficient props (Gemfan 51433 / HQProp 5030)
    # med_pitch: standard freestyle (Gemfan 51466, HQProp 5040)
    # high_pitch: race/aggressive (Gemfan 6045 / 51477)
    "low_pitch":  {2: 5.8, 3: 5.0, 4: 4.3},
    "med_pitch":  {2: 5.0, 3: 4.3, 4: 3.6},
    "high_pitch": {2: 4.3, 3: 3.6, 4: 3.0},
}
_SIZE_EFF_SCALE = {
    # Calibrated from bench data (5" = 1.0). LR props gain less than theory at flight throttle.
    # FIX v5.1: เพิ่ม 6.5" breakpoint เพื่อ smooth ช่องว่าง 6"→7" (0.22→0.12 W/g กระโดด)
    2.5: 0.70, 3.0: 0.77, 3.5: 0.82, 4.0: 0.88,
    4.5: 0.94, 5.0: 1.00, 5.5: 1.03, 6.0: 1.06,
    6.5: 1.07, 7.0: 1.08, 7.5: 1.09, 8.0: 1.11, 10.0: 1.14,
}
_REF_POWER_5IN_4S   = 350.0
# FIX v5.1: เปลี่ยนจาก cells×4.0V×0.82 → cells×3.85V×0.80
# เหตุผล: 3.85V = realistic average flight voltage (ไม่ใช่ fully charged 4.2 หรือ nominal 3.7)
#         0.80 = realistic load factor (มาตรฐาน FPV community, เดิม 0.82 สูงเกิน)
# ผล: สอดคล้องกับ rpm_filter_calc.py ซึ่งใช้ 4.2V×0.75 ≈ 3.15 effective → ค่าใกล้กันมากขึ้น
_FLIGHT_VOLTAGE_PER_CELL = 3.85  # V/cell (avg flight, ไม่ใช่ full charge หรือ nominal)
_LOADED_RPM_FACTOR  = 0.80       # FIX v5.1: 0.82 → 0.80
_TIP_SPEED_WARN     = 265.0
_TIP_SPEED_DANGER   = 290.0

def _interp(val, table):
    keys = sorted(table.keys())
    if val <= keys[0]:  return table[keys[0]]
    if val >= keys[-1]: return table[keys[-1]]
    for i in range(len(keys)-1):
        lo, hi = keys[i], keys[i+1]
        if lo <= val <= hi:
            t = (val-lo)/(hi-lo)
            return table[lo] + t*(table[hi]-table[lo])
    return list(table.values())[len(table)//2]

def _pitch_bucket(p):
    if p < 3.5:  return "low_pitch"
    if p <= 4.5: return "med_pitch"
    return "high_pitch"

def _blade_clamp(b):
    return max(2, min(b, 4)) if b in (2,3,4) else 3

def _cells_eff_factor(cells):
    """Higher voltage → better motor efficiency. ~2% per cell above 4S."""
    return 1.0 + (cells - 4) * 0.015  # 1.5%/cell above 4S (empirically calibrated)

# Empirical max power per motor at 4S reference (W)
# 7"+ uses LR-optimized motors (lower max power, higher hover efficiency)
_MAX_PWR_BY_SIZE = {
    2.5:60, 3.0:75, 3.5:110, 4.0:190, 4.5:260,
    5.0:350, 5.5:410, 6.0:440, 7.0:320, 8.0:380, 10.0:450,
}
# Efficiency at max throttle vs reference (drops at high RPM, more for LR props)
# FIX v5.1: ปรับลงเพื่อ compensate กับ g/W base ที่ยังสูงกว่า min bench
_EFF_AT_MAX_THROTTLE = {
    2.5:0.62, 3.0:0.60, 4.0:0.57, 5.0:0.55,
    6.0:0.50, 7.0:0.46, 8.0:0.42, 10.0:0.38,
}

def _max_power_per_motor(prop_size, cells):
    """Max continuous power per motor (W). Empirical lookup + cell scaling.
    Ref: 5\"/4S = 350W. 7\"+ uses LR motor specs (lower peak, better efficiency).
    """
    base  = _interp(prop_size, _MAX_PWR_BY_SIZE)
    scale = 1.0 + (cells - 4) / 4.0 * 0.22   # +22% per 4 cells above 4S
    return round(min(base * scale, 1000.0), 1)

def _calc_rpm(motor_kv, cells, prop_size):
    if motor_kv and motor_kv > 0:
        # FIX v5.1: ใช้ _FLIGHT_VOLTAGE_PER_CELL (3.85V) แทน 4.0V
        return motor_kv * cells * _FLIGHT_VOLTAGE_PER_CELL * _LOADED_RPM_FACTOR
    _rpm_table = {
        2.5:32000, 3.0:26000, 3.5:22000, 4.0:18000, 4.5:15500,
        5.0:13500, 5.5:12500, 6.0:11500, 7.0:9800, 8.0:8200, 10.0:6800
    }
    return _interp(prop_size, _rpm_table) * _LOADED_RPM_FACTOR

def analyze_propeller(prop_size, prop_pitch, blade_count, style,
                      motor_kv=None, cells=4):
    p_in    = float(prop_size)
    p_pitch = float(prop_pitch)
    blades  = _blade_clamp(int(blade_count))
    cells_i = max(1, min(int(cells), 12))

    noise_score = 0; motor_load = 0
    if p_pitch >= 4.5:
        noise_score += 3; motor_load += 3; eff_label = "แรงจัด กินไฟสูง"
    elif p_pitch >= 3.5:
        noise_score += 2; motor_load += 2; eff_label = "สมดุล"
    else:
        noise_score += 1; motor_load += 1; eff_label = "ประหยัด นุ่ม"
    if blades >= 4:
        noise_score += 3; motor_load += 3; grip = "หนึบมาก (4+ ใบ)"
    elif blades == 3:
        noise_score += 2; motor_load += 2; grip = "หนึบดี (3 ใบ)"
    else:
        noise_score += 1; motor_load += 1; grip = "นุ่ม ลอย (2 ใบ)"

    try:
        p_cm  = p_in * 2.54; p_m = p_in * 0.0254
        disk_area = math.pi * (p_cm/2.0)**2
        rpm_est = _calc_rpm(motor_kv, cells_i, p_in)
        pitch_speed_ms  = (rpm_est * p_pitch * 0.0254) / 60.0
        pitch_speed_kmh = round(pitch_speed_ms * 3.6, 1)
        tip_speed_mps   = round(math.pi * p_m * rpm_est / 60.0, 1)
        g_per_w_base  = _G_PER_W_BASE[_pitch_bucket(p_pitch)][blades]
        size_scale    = _interp(p_in, _SIZE_EFF_SCALE)
        volt_factor   = _cells_eff_factor(cells_i)
        est_g_per_w   = round(g_per_w_base * size_scale * volt_factor, 2)
        max_pwr_motor = _max_power_per_motor(p_in, cells_i)
        eff_at_max = _interp(p_in, _EFF_AT_MAX_THROTTLE)
        max_thrust_per_motor = round(est_g_per_w * eff_at_max * max_pwr_motor, 0)
        est_thrust_100w = round(est_g_per_w * 100.0, 0)
        disk_loading    = round(est_thrust_100w / max(disk_area, 1.0), 2)
    except Exception:
        rpm_est = pitch_speed_kmh = tip_speed_mps = None
        est_g_per_w = max_pwr_motor = max_thrust_per_motor = None
        est_thrust_100w = disk_loading = None

    notes = []
    try:
        ratio = p_pitch / p_in
        if ratio > 0.9:
            notes.append(f"Pitch/Size ratio {ratio:.2f} สูง — โหลดมอเตอร์หนัก เสียงดัง")
        if p_in > 5.5 and p_pitch > 4.5:
            notes.append("ใบพัดใหญ่ + pitch สูง — ตรวจสอบกำลังมอเตอร์")
        if tip_speed_mps:
            if tip_speed_mps >= _TIP_SPEED_DANGER:
                notes.append(
                    f"⚠️ Tip speed {tip_speed_mps} m/s เกิน {_TIP_SPEED_DANGER} m/s! "
                    f"เกิด compressibility loss เสียงดังมาก — ลด KV หรือ props เล็กลง")
            elif tip_speed_mps >= _TIP_SPEED_WARN:
                notes.append(
                    f"⚡ Tip speed {tip_speed_mps} m/s ใกล้ขีดจำกัด ({_TIP_SPEED_WARN} m/s) "
                    f"— efficiency drop ที่ full throttle")
        if motor_kv and cells_i:
            if p_in >= 7 and motor_kv > 1800:
                notes.append(f"Prop ≥7\" + KV {motor_kv} สูงเกินไป — แนะนำ KV ≤ 1500 สำหรับ LR")
            if p_in <= 3 and motor_kv < 2000:
                notes.append(f"Prop ≤3\" + KV {motor_kv} ต่ำ — อาจแรงไม่พอ")
    except Exception:
        pass

    if style == "racing":
        rec = ("เหมาะ Racing — pitch สูง grip ดี ตอบสนองไว" if blades>=3 and p_pitch>=4.0
               else "Racing ควรใช้ pitch 4.0+ และ 3+ ใบ")
    elif style == "longrange":
        rec = ("เหมาะ LR — 2 ใบ pitch ต่ำ ประหยัดไฟดีที่สุด" if blades<=2 and p_pitch<=4.0
               else "LR แนะนำ 2 ใบ pitch 3.0–4.0 เพื่อ efficiency สูงสุด")
    else:
        if 3.5 <= p_pitch <= 4.5 and blades == 3:
            rec = "เหมาะ Freestyle — 3 ใบ pitch กลาง สมดุลดีที่สุด"
        elif p_pitch > 4.5:
            rec = "Freestyle pitch สูงมาก — อาจสั่นหรือร้อนในเที่ยวบินนาน"
        else:
            rec = "Freestyle ได้ แต่ pitch ต่ำ grip ลด"

    if est_g_per_w:
        if est_g_per_w >= 6.0:    eff_rating = "สูงมาก (ประหยัดไฟดีเยี่ยม)"
        elif est_g_per_w >= 5.0:  eff_rating = "สูง (ประหยัดไฟดี)"
        elif est_g_per_w >= 4.0:  eff_rating = "กลาง"
        else:                      eff_rating = "ต่ำ (กินไฟสูง)"
    else:
        eff_rating = eff_label

    summary = (f"ใบพัด {p_in}\" {blades} ใบ Pitch {p_pitch} | Grip: {grip} | Efficiency: {eff_rating}")
    if pitch_speed_kmh: summary += f" | ~{pitch_speed_kmh} km/h"
    if tip_speed_mps:   summary += f" | tip {tip_speed_mps} m/s"

    return {
        "summary":        summary,
        "recommendation": rec,
        "effect": {
            "noise":                  noise_score,
            "motor_load":             motor_load,
            "efficiency":             eff_rating,
            "grip":                   grip,
            "est_g_per_w":            est_g_per_w,
            "est_thrust_100w":        est_thrust_100w,
            "max_thrust_per_motor_g": max_thrust_per_motor,
            "max_power_per_motor_w":  max_pwr_motor,
            "disk_loading":           disk_loading,
            "pitch_speed_kmh":        pitch_speed_kmh,
            "tip_speed_mps":          tip_speed_mps,
            "rpm_estimated":          round(rpm_est) if rpm_est else None,
            "pitch_size_ratio":       round(p_pitch/p_in, 2) if p_in else None,
            "cells_used":             cells_i,
            "notes":                  notes,
        }
    }
