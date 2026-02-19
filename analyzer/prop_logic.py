def analyze_propeller(prop_size, prop_pitch, blade_count, style):
    result = {}

    noise_score = 0
    motor_load = 0
    efficiency = "กลาง"

    # วิเคราะห์ Pitch
    if prop_pitch >= 4.5:
        noise_score += 3
        motor_load += 3
        efficiency = "แรงจัด กินไฟ"
    elif prop_pitch >= 4.0:
        noise_score += 2
        motor_load += 2
        efficiency = "สมดุล"
    else:
        noise_score += 1
        motor_load += 1
        efficiency = "ประหยัด นุ่ม"

    # วิเคราะห์จำนวนใบ
    if blade_count == 4:
        noise_score += 3
        motor_load += 3
        grip = "หนึบมาก"
    elif blade_count == 3:
        noise_score += 2
        motor_load += 2
        grip = "หนึบดี"
    else:
        noise_score += 1
        motor_load += 1
        grip = "นุ่ม ลอย"

    # วิเคราะห์ตามสไตล์
    if style == "racing":
        recommend = "เหมาะกับ Racing ตอบสนองไว"
    elif style == "longrange":
        recommend = "เหมาะกับ Long Range, Smooth"
    else:
        recommend = "เหมาะกับ Freestyle, สมดุล"

    # สรุปผล
    result["summary"] = (
        f"ใบพัด {prop_size} นิ้ว {blade_count} ใบ Pitch {prop_pitch} | "
        f"Grip: {grip} | Efficiency: {efficiency}"
    )
    result["effect"] = {
        "noise": noise_score,
        "motor_load": motor_load,
        "efficiency": efficiency,
        "grip": grip
    }
    result["recommendation"] = recommend

# quick heuristic estimate (per-prop thrust in grams)
try:
    # tuning constant; ปรับค่า C ให้ตรงกับข้อมูลจริงของคุณ
    C = 8.0
    blade_factor = 1.0 if blade_count == 2 else (0.95 if blade_count == 3 else 0.9)
    thrust_per_prop_g = (C * (prop_size ** 2) * prop_pitch) * blade_factor
    result["thrust_per_prop_g"] = float(round(thrust_per_prop_g, 2))
    result["thrust_total_g"] = float(round(thrust_per_prop_g * result.get("motor_count", 4), 2))
except Exception:
    result["thrust_per_prop_g"] = 0.0
    result["thrust_total_g"] = 0.0
def estimate_thrust_per_prop(prop_diameter_mm, prop_pitch_mm, rpm, blade_count=2):
    """
    Heuristic estimate of thrust per prop in grams.
    This is a simple empirical formula for quick estimates.
    Replace with measured lookup table if available.
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

    # Tunable constant — adjust with measured data. Lower -> less thrust.
    # The functional form uses diameter^2 * pitch * rpm^2 (common scaling)
    C = 0.00004  # tuned to produce grams for typical props; adjust later
    blade_factor = 1.0
    if b == 3:
        blade_factor = 0.92
    elif b >= 4:
        blade_factor = 0.85

    thrust_per_prop = C * (d ** 2) * p * (rpm_norm ** 2) * blade_factor * 1000.0
    # last *1000 to convert to grams scale as C is small; we keep units heuristic
    return float(round(max(thrust_per_prop, 0.0), 2))


# Example: at the end of analyze_propeller(...) before return result:
# compute and attach thrust estimates
try:
    prop_diameter_mm = result.get("prop_diameter_mm") or result.get("prop_size_mm") or 0
    prop_pitch_mm = result.get("prop_pitch_mm") or result.get("pitch_mm") or 0
    rpm = result.get("rpm") or result.get("estimated_rpm") or 6000
    blade_count = result.get("blade_count") or result.get("blades") or 2
    thrust_per_prop_g = estimate_thrust_per_prop(prop_diameter_mm, prop_pitch_mm, rpm, blade_count)
    result["thrust_per_prop_g"] = float(thrust_per_prop_g)
    motor_count = int(result.get("motor_count", 4))
    result["thrust_total_g"] = float(round(thrust_per_prop_g * motor_count, 2))
except Exception:
    result["thrust_per_prop_g"] = 0.0
    result["thrust_total_g"] = 0.0

    return result
