"""
analyzer/prop_logic.py

Propeller analysis utilities for ConfigDoctor.

หลักการ:
- analyze_propeller(...) คืน dict ที่สรุปผลการประเมินใบพัด (summary, effect, recommendation)
- estimate_thrust_per_prop(...) ให้ค่า thrust แบบ heuristic (grams) โดยรับค่าเป็น mm / rpm
- ฟังก์ชันทั้งหมดปลอดภัยต่อข้อผิดพลาด input และไม่มีโค้ดระดับโมดูลที่ทำ return
"""

from typing import Dict, Any


def estimate_thrust_per_prop(prop_diameter_mm: float, prop_pitch_mm: float, rpm: float, blade_count: int = 2) -> float:
    """Heuristic estimate of thrust per prop in grams.
    - prop_diameter_mm: diameter in mm
    - prop_pitch_mm: pitch in mm (convert from inches if needed)
    - rpm: motor RPM
    - blade_count: number of blades
    Returns rounded float (grams). Returns 0.0 on invalid input.
    """
    try:
        d = float(prop_diameter_mm)
        p = float(prop_pitch_mm)
        r = float(rpm)
        b = int(blade_count)
    except Exception:
        return 0.0

    # Normalize RPM as fraction of 1000 RPM
    rpm_norm = max(r / 1000.0, 0.0001)

    # Tunable constant — adjust with measured data.
    # The functional form uses diameter^2 * pitch * rpm^2 (common scaling)
    C = 0.00004
    blade_factor = 1.0
    if b == 3:
        blade_factor = 0.92
    elif b >= 4:
        blade_factor = 0.85

    thrust_per_prop = C * (d ** 2) * p * (rpm_norm ** 2) * blade_factor * 1000.0
    return float(round(max(thrust_per_prop, 0.0), 2))


def analyze_propeller(prop_size: float, prop_pitch: float, blade_count: int, style: str,
                      motor_count: int = 4, rpm: int = 6000) -> Dict[str, Any]:
    """
    Analyze propeller characteristics.
    - prop_size: diameter in inches (typical input like 5.0)
    - prop_pitch: pitch in inches (typical input like 4.0)
    - blade_count: number of blades (2,3,4...)
    - style: 'racing', 'longrange', 'freestyle', etc.
    - motor_count: optional number of motors (default 4)
    - rpm: optional RPM to use for refined thrust estimate (default 6000)
    Returns dict with keys: summary, effect, recommendation, thrust_per_prop_g, thrust_total_g
    """
    result: Dict[str, Any] = {}

    # Defensive conversions
    try:
        prop_size_f = float(prop_size)
    except Exception:
        prop_size_f = 0.0

    try:
        prop_pitch_f = float(prop_pitch)
    except Exception:
        prop_pitch_f = 0.0

    try:
        blades_i = int(blade_count)
    except Exception:
        blades_i = 2

    style_s = (style or "").lower()

    # Initialize scoring
    noise_score = 0
    motor_load = 0
    efficiency = "กลาง"

    # Pitch analysis
    try:
        if prop_pitch_f >= 4.5:
            noise_score += 3
            motor_load += 3
            efficiency = "แรงจัด กินไฟ"
        elif prop_pitch_f >= 4.0:
            noise_score += 2
            motor_load += 2
            efficiency = "สมดุล"
        else:
            noise_score += 1
            motor_load += 1
            efficiency = "ประหยัด นุ่ม"
    except Exception:
        pass

    # Blade count analysis
    if blades_i >= 4:
        noise_score += 3
        motor_load += 3
        grip = "หนึบมาก"
    elif blades_i == 3:
        noise_score += 2
        motor_load += 2
        grip = "หนึบดี"
    else:
        noise_score += 1
        motor_load += 1
        grip = "นุ่ม ลอย"

    # Style recommendation
    if style_s == "racing":
        recommend = "เหมาะกับ Racing ตอบสนองไว"
    elif style_s == "longrange" or style_s == "long_range":
        recommend = "เหมาะกับ Long Range, Smooth"
    elif style_s == "cine":
        recommend = "เหมาะกับ Cine / Smooth cinematic"
    else:
        recommend = "เหมาะกับ Freestyle, สมดุล"

    # Summary / effect
    result["summary"] = (
        f"ใบพัด {prop_size_f} นิ้ว {blades_i} ใบ Pitch {prop_pitch_f} | Grip: {grip} | Efficiency: {efficiency}"
    )
    result["effect"] = {
        "noise": noise_score,
        "motor_load": motor_load,
        "efficiency": efficiency,
        "grip": grip
    }
    result["recommendation"] = recommend

    # --- Thrust estimators ---
    # 1) Simple heuristic (keeps legacy behavior)
    try:
        C_simple = 8.0
        blade_factor_simple = 1.0 if blades_i == 2 else (0.95 if blades_i == 3 else 0.9)
        thrust_simple = (C_simple * (prop_size_f ** 2) * prop_pitch_f) * blade_factor_simple
        thrust_simple = float(round(thrust_simple, 2))
    except Exception:
        thrust_simple = 0.0

    # 2) Refined estimator using mm + rpm
    try:
        prop_diameter_mm = prop_size_f * 25.4  # inch -> mm
        prop_pitch_mm = prop_pitch_f * 25.4    # inch -> mm
        thrust_refined = estimate_thrust_per_prop(prop_diameter_mm, prop_pitch_mm, rpm, blades_i)
    except Exception:
        thrust_refined = 0.0

    # Prefer refined if it returns a positive number; else fallback to simple heuristic
    if thrust_refined and thrust_refined > 0.0:
        result["thrust_per_prop_g"] = float(round(thrust_refined, 2))
    else:
        result["thrust_per_prop_g"] = float(round(thrust_simple, 2))

    # total thrust (use motor_count safe conversion)
    try:
        mcount = int(motor_count) if motor_count and int(motor_count) > 0 else 4
    except Exception:
        mcount = 4

    try:
        result["thrust_total_g"] = float(round(result["thrust_per_prop_g"] * mcount, 2))
    except Exception:
        result["thrust_total_g"] = 0.0

    # attach some diagnostics (optional)
    result["_diagnostics"] = {
        "prop_size_in": prop_size_f,
        "prop_pitch_in": prop_pitch_f,
        "blade_count": blades_i,
        "motor_count": mcount,
        "rpm_used": rpm,
        "thrust_refined_g": thrust_refined,
        "thrust_simple_g": thrust_simple
    }

    return result
