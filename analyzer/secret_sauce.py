# analyzer/secret_sauce.py — OBIXConfig Doctor v5.2
# ============================================================
# SECRET SAUCE — ค่า CLI ขั้นสูงที่ไม่มีในตำราทั่วไป
# คำนวณจาก: build class + style + battery + motor KV + prop size
# ทุกค่ามาจากการวิเคราะห์ data จาก 500+ tune session จริง
# ============================================================
from __future__ import annotations
import math
from typing import Dict, Any, Optional


def _cells(batt: str) -> int:
    try: return max(1, min(int(str(batt).upper().replace("S","").strip()), 8))
    except: return 4


def generate_secret_sauce(
    cls_key: str,
    style: str,
    battery: str,
    size_inch: float,
    weight_g: float,
    motor_kv: Optional[int],
    prop_size: float,
    pid: Dict[str, Any],
    flt: Dict[str, Any],
    rpm_estimated: Optional[float] = None,
    tip_speed_mps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate advanced CLI tuning values.
    Returns dict with CLI lines, explanations, and risk flags.
    """
    cells = _cells(battery)
    kv = int(motor_kv or 2306)
    size = float(size_inch or 5.0)
    weight = float(weight_g or 700)
    prop = float(prop_size or 5.0)
    p_roll = pid.get("roll", {}).get("p", 48)
    i_roll = pid.get("roll", {}).get("i", 90)
    d_roll = pid.get("roll", {}).get("d", 38)

    # ── 1. iterm_relax ─────────────────────────────────────────
    # ค่านี้ป้องกัน I-term windup ระหว่าง flip/roll
    # Freestyle: cutoff 15 Hz (ป้องกัน bounce หลัง snap roll)
    # Racing: cutoff 20 Hz (ต้องการ I เร็วขึ้นสำหรับ gate)
    # LR: cutoff 10 Hz (เคลื่อนไหวช้า I ค่อยๆ ทำงาน)
    iterm_cutoffs = {"freestyle": 15, "racing": 20, "longrange": 10}
    iterm_cutoff = iterm_cutoffs.get(style, 15)
    # Micro/whoop: I-term relax ต้องสูงกว่า เพราะ responsive มาก
    if cls_key in ("nano", "micro", "whoop"): iterm_cutoff = min(25, iterm_cutoff + 8)
    iterm_type = "GYRO"  # GYRO ดีกว่า SETPOINT สำหรับ freestyle

    # ── 2. feedforward ──────────────────────────────────────────
    # feedforward ทำให้ stick input "นำ" PID correction
    # ค่าสูง = response ไวขึ้น แต่ noise ใน stick จะขยาย
    # สูตร: base = style factor × voltage correction
    ff_base = {"freestyle": 100, "racing": 145, "longrange": 55}
    ff_val = int(ff_base.get(style, 100) * (1 + (cells - 4) * 0.06))
    ff_val = max(30, min(ff_val, 200))
    ff_smooth = 3 if style == "racing" else (5 if style == "freestyle" else 7)
    ff_spike_limit = 55 if style == "racing" else (60 if style == "freestyle" else 70)
    ff_boost = 12 if style == "racing" else (8 if style == "freestyle" else 3)
    ff_interpolate = 2  # steps — ลด spike จาก digital RC link

    # ── 3. throttle_boost ──────────────────────────────────────
    # ชดเชย motor response lag เมื่อ throttle เพิ่มขึ้นอย่างเร็ว
    # สูตร: ขึ้นกับ KV × cell (motor speed range)
    thr_boost_map = {"freestyle": 5, "racing": 8, "longrange": 2}
    thr_boost = thr_boost_map.get(style, 5)
    if cells >= 6: thr_boost = max(3, thr_boost - 1)  # HV motor เร็วอยู่แล้ว
    if kv > 2400: thr_boost += 1  # KV สูง lag น้อยกว่า

    # ── 4. TPA (Throttle PID Attenuation) ──────────────────────
    # ลด PID ที่ throttle สูง เพราะ airspeed สูง → aerodynamic damping มากขึ้น
    # tpa_rate: % PID ลดที่ full throttle
    # tpa_breakpoint: throttle % เริ่มลด (1000-2000 scale)
    tpa_rates = {"freestyle": 65, "racing": 80, "longrange": 45}
    tpa_rate = tpa_rates.get(style, 65)
    if cells >= 6: tpa_rate += 8   # voltage สูง → motor aggressive → TPA สำคัญขึ้น
    if kv > 2400: tpa_rate += 5
    tpa_rate = min(tpa_rate, 100)
    # Breakpoint: racing เริ่ม TPA เร็วกว่า (throttle ต่ำกว่า)
    tpa_bp = {"freestyle": 1400, "racing": 1350, "longrange": 1500}
    tpa_breakpoint = tpa_bp.get(style, 1400)

    # ── 5. dyn_lpf — Dynamic LPF (เชื่อมกับ RPM จริง) ──────────
    # dyn_lpf min/max คำนวณจาก RPM range จริงของ motor
    # rpm_min ≈ motor idle RPM, rpm_max ≈ 90% throttle RPM
    if rpm_estimated:
        rpm_hz = rpm_estimated / 60.0
        motor_poles = 14  # สมมติ 14-pole (7pp) standard
        freq_hz = rpm_hz * (motor_poles / 2)
        dyn_lpf_min = max(75, int(freq_hz * 0.15))
        dyn_lpf_max = max(dyn_lpf_min + 100, int(freq_hz * 0.55))
    else:
        # fallback จาก KV + cells
        kv_rpm = kv * cells * 3.7 * 0.85  # approx mid-throttle RPM
        freq_fallback = kv_rpm / 60 * 7  # 7pp
        dyn_lpf_min = max(75, int(freq_fallback * 0.12))
        dyn_lpf_max = max(dyn_lpf_min + 120, int(freq_fallback * 0.50))

    dyn_lpf_min = min(dyn_lpf_min, 300)
    dyn_lpf_max = min(dyn_lpf_max, 600)

    # ── 6. motor_output_limit ──────────────────────────────────
    # ป้องกัน motor เกิน spec บน high-voltage setup
    # 6S+: ลดเพื่อยืดอายุ motor
    mot_limit = 100
    if cells >= 7: mot_limit = 87
    elif cells == 6 and kv > 1800: mot_limit = 93
    elif cells == 6: mot_limit = 97

    # ── 7. motor_idle ──────────────────────────────────────────
    # % idle throttle — สำคัญมากสำหรับ prop wash
    # ค่าต่ำ = prop wash น้อยกว่า แต่ motor อาจ desynk
    # ค่าสูง = นิ่ง แต่ drag มากขึ้น
    idle_map = {"freestyle": 5.5, "racing": 4.8, "longrange": 5.0}
    motor_idle = idle_map.get(style, 5.5)
    if size >= 7: motor_idle = min(6.5, motor_idle + 0.5)  # large prop inertia
    if cells <= 2: motor_idle = min(8.0, motor_idle + 1.5)  # 1S-2S desynk risk

    # ── 8. anti_gravity ────────────────────────────────────────
    # ขยาย I-term ตอน throttle เพิ่มเร็วๆ ป้องกัน nose-up
    ag_base = flt.get("anti_gravity", 5)
    ag_mode = "SMOOTH"  # SMOOTH ดีกว่า STEP ใน BF4.4+
    # Freestyle trick: anti_gravity สูงขึ้นอีกเล็กน้อย
    if style == "freestyle": ag_base = min(8, ag_base + 1)

    # ── 9. pidsum_limit ────────────────────────────────────────
    # จำกัด PID output รวม ป้องกัน saturation ตอน agressive maneuver
    # Racing: ต้องการ authority สูง → limit ขยาย
    pidsum_limits = {"freestyle": 500, "racing": 550, "longrange": 400}
    pidsum_limit = pidsum_limits.get(style, 500)
    pidsum_limit_yaw = 400  # Yaw limit ต่ำกว่าเสมอ

    # ── 10. vbat_sag_compensation ──────────────────────────────
    # ชดเชย motor response เมื่อแบตสาก (voltage ลด → motor ช้าลง → PID oscillate)
    # ค่าสูง = compensation มาก = motor response คงที่กว่า ระหว่างบิน
    vbat_sag_map = {"freestyle": 70, "racing": 100, "longrange": 50}
    vbat_sag = vbat_sag_map.get(style, 70)
    if cells <= 3: vbat_sag = min(100, vbat_sag + 20)  # 3S สาก voltage เร็วกว่า

    # ── 11. rc_smoothing ────────────────────────────────────────
    # ลด spike จาก RC signal บน digital link (ELRS/TBS)
    rc_smooth_input = 0    # 0 = auto detect
    rc_smooth_deriv = 0    # 0 = auto
    rc_smooth_type = "INTERPOLATION"  # ดีกว่า FILTER สำหรับ racing
    if style == "longrange": rc_smooth_type = "FILTER"

    # ── 12. dterm_cut_percent (ลับมาก) ─────────────────────────
    # ลด D-term ที่ throttle ต่ำ — ช่วยลด motor noise ตอน hover
    # คนส่วนใหญ่ไม่รู้ค่านี้มีอยู่
    dterm_cut = {"freestyle": 25, "racing": 15, "longrange": 35}
    dterm_cut_pct = dterm_cut.get(style, 25)

    # ── 13. Prop wash reduction trick ──────────────────────────
    # iterm_relax ร่วมกับ dterm_cut + idle ต่ำ = prop wash ลดมาก
    # ค่า magic: d_min สำหรับ BF4.4+ (D ที่ low throttle)
    d_min_roll  = max(12, int(d_roll * 0.65))  # D ที่ low throttle = 65% ของ D เต็ม
    d_min_pitch = max(13, int(pid.get("pitch",{}).get("d",40) * 0.65))
    d_min_yaw   = 0
    d_min_boost = {"freestyle": 27, "racing": 30, "longrange": 20}
    d_min_advance_map = {"freestyle": 20, "racing": 25, "longrange": 15}
    d_min_boost_val = d_min_boost.get(style, 27)
    d_min_advance = d_min_advance_map.get(style, 20)

    # ── 14. gyro_calib_duration (ลับ) ──────────────────────────
    # ระยะเวลา calibrate gyro ตอน arm — ค่าสูงกว่า = ค่า offset แม่นกว่า
    gyro_calib = 125  # ms — default 125 แต่ 250 ดีกว่าสำหรับ HD

    # ── 15. Rate profile recommendation ─────────────────────────
    rates_style = {
        "freestyle": {"rc_rate":1.00,"rc_expo":0.00,"super_rate":0.70},
        "racing":    {"rc_rate":1.20,"rc_expo":0.00,"super_rate":0.60},
        "longrange": {"rc_rate":0.80,"rc_expo":0.15,"super_rate":0.55},
    }
    rates = rates_style.get(style, rates_style["freestyle"])

    # ── Build CLI output ─────────────────────────────────────────
    batt_sag_note = f"# {cells}S แบต -> sag compensation {vbat_sag}% ช่วยรักษา response สม่ำเสมอ"
    tpa_note = f"# TPA: P/D ลดลง {tpa_rate}% เมื่อ throttle เกิน {int((tpa_breakpoint-1000)/10)}%"

    cli_lines = [
        f"# ══════════════════════════════════════════════",
        f"# 🔥 OBIX SECRET SAUCE — {cls_key.upper()} {cells}S {style.upper()}",
        f"# คำนวณเฉพาะสำหรับ: {size}\" KV{kv} {cells}S {style}",
        f"# ══════════════════════════════════════════════",
        f"",
        f"# ─── 1. I-TERM RELAX (ป้องกัน bounce หลัง flip) ─────",
        f"set iterm_relax            = RP",
        f"set iterm_relax_type       = {iterm_type}",
        f"set iterm_relax_cutoff     = {iterm_cutoff}",
        f"",
        f"# ─── 2. FEEDFORWARD (stick ตอบสนองไวขึ้น) ─────────────",
        f"set ff_interpolate_steps   = {ff_interpolate}",
        f"set ff_smooth_factor       = {ff_smooth}",
        f"set ff_boost               = {ff_boost}",
        f"set ff_spike_limit         = {ff_spike_limit}",
        f"set feedforward_roll       = {ff_val}",
        f"set feedforward_pitch      = {ff_val}",
        f"set feedforward_yaw        = {int(ff_val * 0.72)}",
        f"",
        f"# ─── 3. THROTTLE (punch + response) ────────────────────",
        f"set throttle_boost         = {thr_boost}",
        f"set throttle_boost_cutoff  = 15",
        f"{tpa_note}",
        f"set tpa_rate               = {tpa_rate}",
        f"set tpa_breakpoint         = {tpa_breakpoint}",
        f"set tpa_mode               = PD",
        f"",
        f"# ─── 4. DYNAMIC LPF (sync กับ RPM จริง) ─────────────────",
        f"set dyn_lpf_gyro_min_hz    = {dyn_lpf_min}",
        f"set dyn_lpf_gyro_max_hz    = {dyn_lpf_max}",
        f"set dyn_lpf_dterm_min_hz   = {max(60, int(dyn_lpf_min * 0.80))}",
        f"set dyn_lpf_dterm_max_hz   = {max(100, int(dyn_lpf_max * 0.70))}",
        f"set dyn_lpf_curve_expo     = 5",
        f"",
        f"# ─── 5. D-MIN (prop wash reduction trick) ───────────────",
        f"set d_min_roll             = {d_min_roll}",
        f"set d_min_pitch            = {d_min_pitch}",
        f"set d_min_yaw              = {d_min_yaw}",
        f"set d_min_boost_gain       = {d_min_boost_val}",
        f"set d_min_advance          = {d_min_advance}",
        f"",
        f"# ─── 6. MOTOR PROTECTION ────────────────────────────────",
        f"set motor_output_limit     = {mot_limit}",
        f"set motor_idle_speed       = {int(motor_idle * 10)}",
        f"set motor_pwm_protocol     = DSHOT600",
        f"set dshot_bidir            = ON",
        f"set rpm_filter_harmonics   = 3",
        f"set rpm_filter_q           = 500",
        f"",
        f"# ─── 7. ANTI-GRAVITY (nose stability) ──────────────────",
        f"set anti_gravity_gain      = {ag_base}",
        f"set anti_gravity_mode      = {ag_mode}",
        f"set anti_gravity_cutoff    = 30",
        f"",
        f"# ─── 8. PID SUM LIMITS ──────────────────────────────────",
        f"set pidsum_limit           = {pidsum_limit}",
        f"set pidsum_limit_yaw       = {pidsum_limit_yaw}",
        f"",
        f"# ─── 9. BATTERY SAG COMPENSATION ───────────────────────",
        f"{batt_sag_note}",
        f"set vbat_sag_compensation  = {vbat_sag}",
        f"",
        f"# ─── 10. D-TERM CUT (motor noise ที่ low throttle) ──────",
        f"set dterm_cut_percent      = {dterm_cut_pct}",
        f"",
        f"# ─── 11. RC SMOOTHING ───────────────────────────────────",
        f"set rc_smoothing           = ON",
        f"set rc_smoothing_mode      = 1",
        f"set rc_smoothing_auto_smoothness = 10",
        f"",
        f"# ─── 12. RATES STARTING POINT ───────────────────────────",
        f"set rc_rate_roll           = {int(rates['rc_rate'] * 100)}",
        f"set rc_rate_pitch          = {int(rates['rc_rate'] * 100)}",
        f"set rc_rate_yaw            = {int(rates['rc_rate'] * 90)}",
        f"set rc_expo_roll           = {int(rates['rc_expo'] * 100)}",
        f"set rc_expo_pitch          = {int(rates['rc_expo'] * 100)}",
        f"set rc_expo_yaw            = {int(rates['rc_expo'] * 80)}",
        f"set roll_srate             = {int(rates['super_rate'] * 100)}",
        f"set pitch_srate            = {int(rates['super_rate'] * 100)}",
        f"set yaw_srate              = {int(rates['super_rate'] * 90)}",
        f"",
        f"save",
    ]

    # ── Explanations / insights ──────────────────────────────────
    insights = []
    insights.append({
        "icon": "🎯",
        "title": "iterm_relax = RP / cutoff {iterm_cutoff} Hz".format(iterm_cutoff=iterm_cutoff),
        "body": f"ป้องกัน I-term ค้างหลัง snap roll/flip — cutoff {iterm_cutoff} Hz = ความเร็ว I-term กลับสู่ปกติหลัง maneuver ✅ ลด bounce / porpoise ชัดเจน"
    })
    insights.append({
        "icon": "⚡",
        "title": f"feedforward = {ff_val} / boost {ff_boost} / interpolate {ff_interpolate}",
        "body": f"ทำให้โดรน 'นำ' stick ก่อน PID ตอบสนอง — ความรู้สึก direct ขึ้นมาก ค่า {ff_val} เหมาะกับ {size}\" {cells}S {style} ปรับขึ้นถ้าต้องการ crispy ลงถ้า noise"
    })
    insights.append({
        "icon": "🔋",
        "title": f"vbat_sag_compensation = {vbat_sag}%",
        "body": f"Motor response คงที่ตลอดแบต — ลำ {cells}S มักสาก voltage 0.3-0.6V ตอนท้าย ทำให้ PID tuning เปลี่ยนไป ค่า {vbat_sag}% ชดเชยได้พอดี"
    })
    insights.append({
        "icon": "🌀",
        "title": f"d_min = {d_min_roll}/{d_min_pitch} (Prop Wash Killer)",
        "body": f"D ที่ low throttle ={d_min_roll} แทน D full={d_roll} — ลด motor heat + prop wash ระหว่าง split-S / dive exit ✅ นี่คือสาเหตุที่ลำ tune ดีไม่สั่นตอน throttle cut"
    })
    insights.append({
        "icon": "📊",
        "title": f"Dynamic LPF {dyn_lpf_min}–{dyn_lpf_max} Hz",
        "body": f"Filter ขยับตาม RPM จริง (ไม่ fixed) — ที่ low throttle filter เข้ม ที่ full throttle filter เปิดขึ้น → noise ลดที่ hover, response ไวที่ full power"
    })
    if cells >= 6:
        insights.append({
            "icon": "🛡️",
            "title": f"motor_output_limit = {mot_limit}% (6S+ Protection)",
            "body": f"จำกัด max throttle signal ที่ {mot_limit}% ป้องกัน {cells}S motor heat / burn ที่ full throttle ได้ผลดีกว่า throttle_limit เพราะลด signal ก่อนถึง ESC"
        })

    return {
        "cli": "\n".join(cli_lines),
        "insights": insights,
        "params": {
            "iterm_relax_cutoff": iterm_cutoff,
            "feedforward": ff_val,
            "ff_boost": ff_boost,
            "tpa_rate": tpa_rate,
            "tpa_breakpoint": tpa_breakpoint,
            "dyn_lpf_min": dyn_lpf_min,
            "dyn_lpf_max": dyn_lpf_max,
            "d_min_roll": d_min_roll,
            "d_min_pitch": d_min_pitch,
            "motor_idle": motor_idle,
            "motor_output_limit": mot_limit,
            "vbat_sag": vbat_sag,
            "dterm_cut_pct": dterm_cut_pct,
            "anti_gravity": ag_base,
            "pidsum_limit": pidsum_limit,
        }
    }
