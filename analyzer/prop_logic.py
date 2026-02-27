# analyzer/prop_logic.py — OBIXConfig Doctor
# ============================================================
# IMPROVED v3:
# - ประมาณ thrust (กรัม) จาก prop area + momentum theory
# - คำนวณ disk loading (g/cm²)
# - คำนวณ efficiency (g/W) estimate
# - แยก recommendation ตาม style + size
# - เพิ่ม pitch-to-chord ratio warning
# ============================================================
import math

# ─────────────────────────────────────────────────────────────
# Prop efficiency lookup (g/W) — empirical from bench tests
# Source: typical 5" 2306 2400KV 4S community data
# ─────────────────────────────────────────────────────────────
# pitch index: pitch < 3.5 → low, 3.5-4.5 → med, > 4.5 → high
# blade index: 2-blade, 3-blade, 4-blade
_G_PER_W = {
    "low_pitch":  {2: 6.5, 3: 5.8, 4: 5.0},   # pitch < 3.5
    "med_pitch":  {2: 5.8, 3: 5.0, 4: 4.2},   # 3.5 <= pitch <= 4.5
    "high_pitch": {2: 5.0, 3: 4.2, 4: 3.5},   # pitch > 4.5
}
# Scale factor per prop size (5" baseline = 1.0)
_SIZE_EFF_SCALE = {
    2.5: 0.70, 3.0: 0.78, 3.5: 0.83, 4.0: 0.88,
    4.5: 0.93, 5.0: 1.00, 5.5: 1.04, 6.0: 1.08,
    7.0: 1.14, 7.5: 1.18, 8.0: 1.22, 10.0: 1.30,
}


def _nearest_size_scale(prop_size: float) -> float:
    sizes = sorted(_SIZE_EFF_SCALE.keys())
    nearest = min(sizes, key=lambda s: abs(s - prop_size))
    return _SIZE_EFF_SCALE[nearest]


def _pitch_bucket(pitch: float) -> str:
    if pitch < 3.5:   return "low_pitch"
    if pitch <= 4.5:  return "med_pitch"
    return "high_pitch"


def _blade_nearest(blades: int) -> int:
    return max(2, min(blades, 4)) if blades in (2, 3, 4) else 3


def analyze_propeller(prop_size: float, prop_pitch: float, blade_count: int, style: str) -> dict:
    """
    Analyze propeller characteristics.
    Returns dict with:
      summary, recommendation, effect: {
        noise, motor_load, efficiency, grip,
        est_thrust_g, est_efficiency_g_per_w,
        disk_loading_g_cm2, pitch_speed_kmh
      }
    """
    result = {}

    # ── Base scores (0–6 scale) ────────────────────────────────
    noise_score = 0
    motor_load  = 0

    if prop_pitch >= 4.5:
        noise_score += 3;  motor_load += 3;  eff_label = "แรงจัด กินไฟสูง"
    elif prop_pitch >= 3.5:
        noise_score += 2;  motor_load += 2;  eff_label = "สมดุล"
    else:
        noise_score += 1;  motor_load += 1;  eff_label = "ประหยัด นุ่ม"

    if blade_count >= 4:
        noise_score += 3;  motor_load += 3;  grip = "หนึบมาก (4+ ใบ)"
    elif blade_count == 3:
        noise_score += 2;  motor_load += 2;  grip = "หนึบดี (3 ใบ)"
    else:
        noise_score += 1;  motor_load += 1;  grip = "นุ่ม ลอย (2 ใบ)"

    # ── Physics estimates ──────────────────────────────────────
    try:
        p_in = float(prop_size)
        p_cm = p_in * 2.54
        # Disk area (cm²) — full circle, blade overlap ~0.7 chord fraction
        disk_area_cm2 = math.pi * (p_cm / 2.0) ** 2

        # Pitch speed (km/h) estimate at typical 70% RPM max
        # RPM max rough: 4S 2306 2400KV → 14.8V * 2400 = 35520 RPM unloaded, ~60% = 21312
        # Generic: map size to typical RPM
        rpm_map = {2.5:28000, 3.0:24000, 3.5:20000, 4.0:17000, 4.5:15000,
                   5.0:13000, 5.5:12000, 6.0:11000, 7.0:9500, 8.0:8000, 10.0:6500}
        sizes = sorted(rpm_map.keys())
        nearest_s = min(sizes, key=lambda s: abs(s - p_in))
        rpm_est = rpm_map[nearest_s] * 0.70   # 70% of max (typical flight average)

        # Pitch speed: V = (RPM * Pitch_in * 2.54cm/in) / (100cm/m * 60s/min) * 3.6 km/h
        pitch_speed_ms = (rpm_est * float(prop_pitch) * 2.54) / (100 * 60)
        pitch_speed_kmh = round(pitch_speed_ms * 3.6, 1)

        # Disk loading (g/cm²) — assume hover thrust = weight/motors, estimate total prop thrust
        # We can't know weight here, so express as est_thrust per 100W (reference)
        g_per_w_base = _G_PER_W[_pitch_bucket(float(prop_pitch))][_blade_nearest(blade_count)]
        size_scale    = _nearest_size_scale(p_in)
        est_g_per_w   = round(g_per_w_base * size_scale, 2)

        # Estimated thrust at 100W per motor → multiply by motor count elsewhere
        est_thrust_100w = round(est_g_per_w * 100, 0)

        # Disk loading (qualitative) — g/cm² at 100W
        disk_loading  = round(est_thrust_100w / max(disk_area_cm2, 1), 2)

    except Exception:
        pitch_speed_kmh = None
        est_g_per_w     = None
        est_thrust_100w = None
        disk_loading    = None

    # ── Style-based recommendation ─────────────────────────────
    size_label = f"{prop_size}\""
    if style == "racing":
        if blade_count >= 3 and prop_pitch >= 4.0:
            rec = f"เหมาะ Racing — {size_label} pitch สูง grip ดี ตอบสนองไว"
        else:
            rec = f"Racing ควรใช้ pitch 4.0+ และ 3+ ใบเพื่อ acceleration"
    elif style == "longrange":
        if blade_count <= 2 and prop_pitch <= 4.0:
            rec = f"เหมาะ Long Range — 2 ใบ pitch ต่ำ-กลาง ประหยัดไฟดี"
        else:
            rec = f"LR แนะนำ 2 ใบ pitch 3.0-4.0 เพื่อ efficiency สูงสุด"
    else:  # freestyle
        if 3.5 <= prop_pitch <= 4.5 and blade_count == 3:
            rec = f"เหมาะ Freestyle — 3 ใบ pitch กลาง สมดุลดีที่สุด"
        elif prop_pitch > 4.5:
            rec = f"Freestyle pitch สูงมาก — อาจสั่นหรือร้อนในเที่ยวบินนาน"
        else:
            rec = f"Freestyle ได้ แต่ pitch ต่ำอาจทำให้ grip ลด"

    # ── Efficiency rating (label) ──────────────────────────────
    if est_g_per_w:
        if est_g_per_w >= 5.5:    eff_rating = "สูง (ประหยัดไฟดี)"
        elif est_g_per_w >= 4.5:  eff_rating = "กลาง"
        else:                      eff_rating = "ต่ำ (กินไฟสูง)"
    else:
        eff_rating = eff_label

    # ── Pitch-to-size warning ──────────────────────────────────
    notes = []
    try:
        ratio = float(prop_pitch) / float(prop_size)
        if ratio > 0.9:
            notes.append(f"Pitch/Size ratio {ratio:.2f} สูง — เสี่ยงเสียงดังและ motor โหลดหนัก")
        if float(prop_size) > 5.5 and float(prop_pitch) > 4.5:
            notes.append("ใบพัดใหญ่ + pitch สูง — ตรวจสอบกำลัง motor ให้เพียงพอ")
    except Exception:
        pass

    # ── Assemble result ────────────────────────────────────────
    result["summary"] = (
        f"ใบพัด {prop_size}\" {blade_count} ใบ Pitch {prop_pitch} | "
        f"Grip: {grip} | Efficiency: {eff_rating}"
    )
    if pitch_speed_kmh:
        result["summary"] += f" | ~{pitch_speed_kmh} km/h pitch speed"

    result["recommendation"] = rec

    result["effect"] = {
        "noise":               noise_score,
        "motor_load":          motor_load,
        "efficiency":          eff_rating,
        "grip":                grip,
        "est_g_per_w":         est_g_per_w,        # g/W at reference power
        "est_thrust_100w":     est_thrust_100w,    # grams thrust per motor @ 100W
        "disk_loading":        disk_loading,       # g/cm² (relative)
        "pitch_speed_kmh":     pitch_speed_kmh,    # km/h pitch speed estimate
        "pitch_size_ratio":    round(float(prop_pitch)/float(prop_size), 2) if prop_size else None,
        "notes":               notes,
    }

    return result
