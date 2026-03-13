# analyzer/secret_sauce.py — OBIXConfig Doctor v5.2
# ============================================================
# SECRET SAUCE — Advanced CLI ที่ไม่มีในตำราทั่วไป
# คำนวณจาก: build class + style + battery S + motor KV + prop
# ทุกค่า derived จาก physics + community tuning data จริง
# ============================================================
from __future__ import annotations
import math
from typing import Dict, Any, Optional


def _cells(batt: str) -> int:
    try: return max(1, min(int(str(batt).upper().replace("S","").strip()), 8))
    except (ValueError, TypeError): return 4


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

    cells  = _cells(battery)
    kv     = int(motor_kv or 2306)
    size   = float(size_inch or 5.0)
    weight = float(weight_g or 700)
    prop   = float(prop_size or 5.0)
    p_roll = pid.get("roll", {}).get("p", 48)
    d_roll = pid.get("roll", {}).get("d", 38)
    d_pitch = pid.get("pitch", {}).get("d", 40)

    # ── 1. iterm_relax ─────────────────────────────────────────
    # ป้องกัน I-term windup ระหว่าง flip/roll
    # GYRO type ดีกว่า SETPOINT เพราะทำงานบน gyro rate จริง
    # cutoff ต่ำ = I กลับช้า = bounce น้อย (freestyle)
    # cutoff สูง = I กลับเร็ว = response ไว (racing/gate)
    iterm_cutoffs = {"freestyle": 15, "racing": 22, "longrange": 8}
    iterm_cutoff  = iterm_cutoffs.get(style, 15)
    if cls_key in ("nano","micro","whoop"):
        iterm_cutoff = min(28, iterm_cutoff + 10)  # tiny frame oscillates fast
    elif size >= 7:
        iterm_cutoff = max(5, iterm_cutoff - 3)    # large prop inertia — slower I

    # ── 2. feedforward ─────────────────────────────────────────
    # ทำให้ stick input "นำ" PID — ลด latency ที่รู้สึกได้
    # voltage factor: แรงดันสูงขึ้น → motor ตอบสนองเร็วขึ้น
    # → feedforward ต้องลดลงเพื่อไม่ให้ overshoot
    ff_base = {"freestyle": 100, "racing": 148, "longrange": 50}
    voltage_factor = 1.0 - (cells - 4) * 0.055  # 4S=1.0, 5S=0.945, 6S=0.89
    ff_val  = int(ff_base.get(style, 100) * max(0.6, voltage_factor))
    ff_val  = max(30, min(ff_val, 200))
    ff_smooth      = 3 if style == "racing" else (5 if style == "freestyle" else 8)
    ff_spike_limit = 50 if style == "racing" else (60 if style == "freestyle" else 75)
    ff_boost       = 15 if style == "racing" else (10 if style == "freestyle" else 4)
    ff_interpolate = 2  # ลด spike จาก digital RC (ELRS/Crossfire)

    # ── 3. throttle_boost ──────────────────────────────────────
    # ชดเชย motor lag เมื่อ throttle เพิ่มเร็ว
    # HV (6S+) motor spin-up เร็วกว่า → boost น้อยลง
    thr_base = {"freestyle": 5, "racing": 8, "longrange": 2}
    thr_boost = thr_base.get(style, 5)
    if cells >= 6: thr_boost = max(2, thr_boost - 2)
    if kv > 2400:  thr_boost = min(thr_boost + 1, 9)

    # ── 4. TPA (Throttle PID Attenuation) ──────────────────────
    # ที่ full throttle airspeed สูง → aerodynamic damping เพิ่ม
    # → PID ต้องลดลงมิฉะนั้น oscillate ที่ high speed
    tpa_base = {"freestyle": 65, "racing": 82, "longrange": 40}
    tpa_rate = tpa_base.get(style, 65)
    tpa_rate += (cells - 4) * 7   # HV: TPA สำคัญขึ้น
    if kv > 2400: tpa_rate += 5
    tpa_rate = max(30, min(tpa_rate, 100))
    tpa_bp = {"freestyle": 1400, "racing": 1330, "longrange": 1500}
    tpa_breakpoint = tpa_bp.get(style, 1400)

    # ── 5. Dynamic LPF (sync กับ RPM จริง) ────────────────────
    # Filter ขยับตาม throttle/RPM — ไม่ใช่ fixed cutoff
    # คำนวณจาก motor fundamental frequency จริง
    motor_poles = 14  # standard FPV motor 14-pole (7 pole pairs)
    if rpm_estimated and rpm_estimated > 0:
        fund_hz = (rpm_estimated / 60.0) * (motor_poles / 2)
        dyn_min = max(70, int(fund_hz * 0.14))
        dyn_max = max(dyn_min + 100, int(fund_hz * 0.52))
    else:
        # fallback: KV × Vcell × 85% efficiency / 60 × pole_pairs
        rpm_est = kv * cells * 3.7 * 0.82
        fund_hz = (rpm_est / 60.0) * (motor_poles / 2)
        dyn_min = max(70, int(fund_hz * 0.13))
        dyn_max = max(dyn_min + 120, int(fund_hz * 0.48))
    dyn_min = min(dyn_min, 350)
    dyn_max = min(dyn_max, 650)
    dterm_dyn_min = max(55, int(dyn_min * 0.78))
    dterm_dyn_max = max(90,  int(dyn_max * 0.68))

    # ── 6. D-min (Prop Wash Reduction) ─────────────────────────
    # D ที่ low throttle = fraction of D ที่ full
    # ลด motor heat + prop wash หลัง dive / split-S
    # BF4.4+ D_min + D_min_boost = prop wash killer
    d_min_roll  = max(10, int(d_roll  * 0.62))
    d_min_pitch = max(11, int(d_pitch * 0.62))
    d_min_yaw   = 0
    boost_map   = {"freestyle": 27, "racing": 32, "longrange": 18}
    adv_map     = {"freestyle": 20, "racing": 26, "longrange": 12}
    d_boost     = boost_map.get(style, 27)
    d_advance   = adv_map.get(style, 20)
    if size >= 7: d_boost = max(15, d_boost - 5)  # large prop — softer boost

    # ── 7. motor_output_limit ──────────────────────────────────
    # ป้องกัน motor เกิน spec ที่ HV setup
    mot_limit = 100
    if   cells >= 7:               mot_limit = 85
    elif cells == 6 and kv > 1900: mot_limit = 91
    elif cells == 6:               mot_limit = 96
    elif cells == 5 and kv > 2200: mot_limit = 97

    # ── 8. motor_idle ──────────────────────────────────────────
    # Low idle = prop wash ลด แต่ desynk risk ขึ้น
    # 1S-2S quad เสี่ยง desynk มาก → idle สูงกว่า
    idle_map = {"freestyle": 5.5, "racing": 4.8, "longrange": 5.0}
    motor_idle = idle_map.get(style, 5.5)
    if size >= 7: motor_idle += 0.5   # large prop inertia
    if cells <= 2: motor_idle += 1.8   # 1S-2S desynk protection
    elif cells == 3: motor_idle += 0.5

    # ── 9. anti_gravity ────────────────────────────────────────
    ag_base = flt.get("anti_gravity", 5)
    ag_mode = "SMOOTH"  # BF4.4+ SMOOTH ดีกว่า STEP เสมอ
    if style == "freestyle":   ag_base = min(8, ag_base + 1)
    if cls_key in ("nano","micro","whoop"): ag_base = max(3, ag_base - 1)

    # ── 10. vbat_sag_compensation ──────────────────────────────
    # Motor response คงที่ตลอดแบต ไม่ว่าแบตจะสาก
    # 3S: sag มาก (voltage range ต่ำ) → compensation สูง
    # 6S: sag สัมพัทธ์น้อยกว่า
    vbat_map = {"freestyle": 70, "racing": 100, "longrange": 50}
    vbat_sag = vbat_map.get(style, 70)
    if   cells <= 2: vbat_sag = min(100, vbat_sag + 25)
    elif cells == 3: vbat_sag = min(100, vbat_sag + 18)
    elif cells >= 6: vbat_sag = max(30,  vbat_sag - 15)

    # ── 11. pidsum_limit ───────────────────────────────────────
    pidsum_map = {"freestyle": 500, "racing": 550, "longrange": 400}
    pidsum     = pidsum_map.get(style, 500)

    # ── 12. dterm_cut_percent ──────────────────────────────────
    # ลด D ที่ low throttle — ลด motor noise ตอน hover/landing
    # คนส่วนใหญ่ไม่รู้ว่าค่านี้มีอยู่ใน BF4.4+
    dcut_map = {"freestyle": 25, "racing": 18, "longrange": 35}
    dterm_cut = dcut_map.get(style, 25)

    # ── 13. rc_smoothing ───────────────────────────────────────
    rc_smooth_type = "FILTER" if style == "longrange" else "INTERPOLATION"

    # ── 14. Rates starting point ───────────────────────────────
    rates = {
        "freestyle": {"rc":1.00, "expo":0.00, "sr":0.70},
        "racing":    {"rc":1.20, "expo":0.00, "sr":0.60},
        "longrange": {"rc":0.78, "expo":0.18, "sr":0.55},
    }.get(style, {"rc":1.00,"expo":0.00,"sr":0.70})

    # ── 15. Crash recovery ─────────────────────────────────────
    crash_recovery = "ON" if style == "freestyle" else "OFF"

    # ─── Build CLI lines ────────────────────────────────────────
    cli = "\n".join([
        f"# ══════════════════════════════════════════════",
        f"# 🔥 OBIX SECRET SAUCE v5.2",
        f"# {cls_key.upper()} · {cells}S · KV{kv} · {size}\" · {style.upper()}",
        f"# คำนวณเฉพาะ build นี้ — ไม่ใช่ค่า generic",
        f"# ══════════════════════════════════════════════",
        f"",
        f"# ─── 1. I-TERM RELAX ────────────────────────────",
        f"# ป้องกัน bounce หลัง snap roll/flip",
        f"set iterm_relax            = RP",
        f"set iterm_relax_type       = GYRO",
        f"set iterm_relax_cutoff     = {iterm_cutoff}",
        f"",
        f"# ─── 2. FEEDFORWARD ─────────────────────────────",
        f"# stick ตอบสนองไวขึ้น / ลด latency ที่รู้สึกได้",
        f"set ff_interpolate_steps   = {ff_interpolate}",
        f"set ff_smooth_factor       = {ff_smooth}",
        f"set ff_boost               = {ff_boost}",
        f"set ff_spike_limit         = {ff_spike_limit}",
        f"set feedforward_roll       = {ff_val}",
        f"set feedforward_pitch      = {ff_val}",
        f"set feedforward_yaw        = {int(ff_val * 0.70)}",
        f"",
        f"# ─── 3. THROTTLE ─────────────────────────────────",
        f"set throttle_boost         = {thr_boost}",
        f"set throttle_boost_cutoff  = 15",
        f"# TPA: PID ลด {tpa_rate}% เมื่อ throttle >{int((tpa_breakpoint-1000)/10)}%",
        f"set tpa_rate               = {tpa_rate}",
        f"set tpa_breakpoint         = {tpa_breakpoint}",
        f"set tpa_mode               = PD",
        f"",
        f"# ─── 4. DYNAMIC LPF (sync กับ RPM จริง) ─────────",
        f"set dyn_lpf_gyro_min_hz    = {dyn_min}",
        f"set dyn_lpf_gyro_max_hz    = {dyn_max}",
        f"set dyn_lpf_dterm_min_hz   = {dterm_dyn_min}",
        f"set dyn_lpf_dterm_max_hz   = {dterm_dyn_max}",
        f"set dyn_lpf_curve_expo     = 5",
        f"",
        f"# ─── 5. D-MIN (prop wash killer) ─────────────────",
        f"set d_min_roll             = {d_min_roll}",
        f"set d_min_pitch            = {d_min_pitch}",
        f"set d_min_yaw              = {d_min_yaw}",
        f"set d_min_boost_gain       = {d_boost}",
        f"set d_min_advance          = {d_advance}",
        f"",
        f"# ─── 6. MOTOR PROTECTION ─────────────────────────",
        f"set motor_output_limit     = {mot_limit}",
        f"set motor_idle_speed       = {int(motor_idle * 10)}",
        f"set rpm_filter_q           = 500",
        f"",
        f"# ─── 7. ANTI-GRAVITY ─────────────────────────────",
        f"set anti_gravity_gain      = {ag_base}",
        f"set anti_gravity_mode      = {ag_mode}",
        f"set anti_gravity_cutoff    = 30",
        f"",
        f"# ─── 8. PID SUM LIMITS ───────────────────────────",
        f"set pidsum_limit           = {pidsum}",
        f"set pidsum_limit_yaw       = 400",
        f"",
        f"# ─── 9. BATTERY SAG COMPENSATION ────────────────",
        f"# {cells}S: ชดเชย voltage sag {vbat_sag}%",
        f"set vbat_sag_compensation  = {vbat_sag}",
        f"",
        f"# ─── 10. D-TERM CUT (noise ที่ low throttle) ────",
        f"set dterm_cut_percent      = {dterm_cut}",
        f"",
        f"# ─── 11. RC SMOOTHING ────────────────────────────",
        f"set rc_smoothing           = ON",
        f"set rc_smoothing_mode      = 1",
        f"set rc_smoothing_auto_smoothness = 10",
        f"",
        f"# ─── 12. CRASH RECOVERY ──────────────────────────",
        f"set crash_recovery         = {crash_recovery}",
        f"",
        f"# ─── 13. RATES STARTING POINT ───────────────────",
        f"set rc_rate_roll           = {int(rates['rc']*100)}",
        f"set rc_rate_pitch          = {int(rates['rc']*100)}",
        f"set rc_rate_yaw            = {int(rates['rc']*90)}",
        f"set rc_expo_roll           = {int(rates['expo']*100)}",
        f"set rc_expo_pitch          = {int(rates['expo']*100)}",
        f"set rc_expo_yaw            = {int(rates['expo']*80)}",
        f"set roll_srate             = {int(rates['sr']*100)}",
        f"set pitch_srate            = {int(rates['sr']*100)}",
        f"set yaw_srate              = {int(rates['sr']*90)}",
        f"",
        f"save",
    ])

    # ─── Insights (Thai, FPV-specific) ──────────────────────────
    insights = []

    insights.append({
        "icon": "🎯",
        "title": f"iterm_relax cutoff = {iterm_cutoff} Hz — Bounce Eliminator",
        "body": (
            f"I-term relax ป้องกัน 'bounce' / 'porpoise' หลัง snap roll หรือ flip "
            f"โดย relax I-term เมื่อ stick เคลื่อนไหวเร็ว — "
            f"cutoff {iterm_cutoff} Hz เหมาะกับ {size}\" {cls_key} {style} "
            f"ค่าสูง = I กลับเร็ว (racing crispy) / ค่าต่ำ = I กลับช้า (ป้องกัน bounce ได้ดีกว่า)"
        )
    })

    insights.append({
        "icon": "⚡",
        "title": f"feedforward = {ff_val} — Stick-to-Drone Direct Feel",
        "body": (
            f"feedforward ทำให้โดรน 'รู้สึก' stick โดยตรงก่อนที่ PID จะตามทัน "
            f"ลด delay ที่รู้สึกได้ชัดโดยเฉพาะตอน quick snap / direction change "
            f"ค่า {ff_val} สำหรับ {cells}S {style} — "
            f"ปรับขึ้น 10-15 ถ้าอยากได้ crispy / ลงถ้า stick มี noise"
        )
    })

    insights.append({
        "icon": "🌀",
        "title": f"D-min = {d_min_roll}/{d_min_pitch} — Prop Wash Killer",
        "body": (
            f"D ที่ low throttle = {d_min_roll} (แทน D full = {d_roll}) "
            f"D ลดลงตาม throttle — ลด motor heat + prop wash ระหว่าง dive exit / split-S "
            f"d_min_boost = {d_boost} ทำให้ D เพิ่มกลับเมื่อมี gyro rate สูง "
            f"✅ นี่คือเหตุผลที่ build tune ดีไม่ฟันน้ำลายตอน throttle cut"
        )
    })

    insights.append({
        "icon": "📊",
        "title": f"Dynamic LPF {dyn_min}–{dyn_max} Hz — Filter ที่ฉลาดกว่า Fixed",
        "body": (
            f"Filter ขยับตาม RPM จริง — ที่ low throttle (RPM ต่ำ) filter เข้มขึ้น "
            f"ที่ full throttle filter เปิดออก → noise ลดที่ hover / response ไวที่ full power "
            f"คำนวณจาก KV{kv} × {cells}S fundamental freq ≈ {int((kv*cells*3.7*0.82/60)*(motor_poles//2))} Hz"
        )
    })

    insights.append({
        "icon": "🔋",
        "title": f"vbat_sag_compensation = {vbat_sag}% — Motor คงที่ตลอดแบต",
        "body": (
            f"ชดเชย motor response ที่เปลี่ยนไปเมื่อแบต {cells}S สาก "
            f"แบต {cells}S มักสาก ~0.2–0.5V ต่อ cell ในระหว่างบิน → motor ช้าลง → PID เพี้ยน "
            f"ค่า {vbat_sag}% ทำให้ feel ของโดรนคงที่ตั้งแต่ต้นจนจบแบต"
        )
    })

    if cells >= 5:
        insights.append({
            "icon": "🛡️",
            "title": f"motor_output_limit = {mot_limit}% — HV Motor Protection",
            "body": (
                f"{cells}S = แรงดัน max {cells * 4.2:.1f}V → motor/ESC เสี่ยง overload ที่ full throttle "
                f"จำกัด output ที่ {mot_limit}% ป้องกัน motor heat / demagnetize "
                f"ยังได้ power เกือบเต็ม แต่ motor อายุยืนขึ้นชัดเจน"
            )
        })

    if style == "racing":
        insights.append({
            "icon": "🏁",
            "title": f"TPA {tpa_rate}% @ {int((tpa_breakpoint-1000)/10)}% throttle — Race Gate Tune",
            "body": (
                f"TPA ลด PID ที่ throttle สูง เพราะ airspeed เพิ่ม aerodynamic damping ให้โดรนเอง "
                f"Racing: TPA สูง ({tpa_rate}%) + breakpoint ต่ำ ({int((tpa_breakpoint-1000)/10)}%) "
                f"= PID active เต็มที่ที่ low throttle (gate approach) / ลดที่ full power (straight line)"
            )
        })

    if style == "longrange":
        insights.append({
            "icon": "🌏",
            "title": f"RC Smoothing = FILTER — LR Wind Rejection",
            "body": (
                f"Long Range บิน slow + constant throttle — RC Smoothing แบบ FILTER ดีกว่า INTERPOLATION "
                f"เพราะลด stick noise มากกว่าสำหรับ long gentle inputs "
                f"ร่วมกับ iterm_relax cutoff {iterm_cutoff} Hz = wind rejection ที่ระยะไกลดีขึ้นชัดเจน"
            )
        })

    params = {
        "iterm_relax_cutoff": iterm_cutoff,
        "feedforward": ff_val,
        "ff_boost": ff_boost,
        "ff_spike_limit": ff_spike_limit,
        "tpa_rate": tpa_rate,
        "tpa_breakpoint": tpa_breakpoint,
        "dyn_lpf_gyro_min": dyn_min,
        "dyn_lpf_gyro_max": dyn_max,
        "d_min_roll": d_min_roll,
        "d_min_pitch": d_min_pitch,
        "d_min_boost": d_boost,
        "motor_idle": f"{motor_idle:.1f}%",
        "motor_output_limit": f"{mot_limit}%",
        "vbat_sag": f"{vbat_sag}%",
        "anti_gravity": ag_base,
        "dterm_cut": f"{dterm_cut}%",
    }

    return {"cli": cli, "insights": insights, "params": params}
