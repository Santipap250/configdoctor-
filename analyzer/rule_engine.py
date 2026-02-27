# analyzer/rule_engine.py
"""
Rule-based tuning engine for OBIXConfig Doctor.
Input: analysis (dict) produced by existing logic + optional advanced section.
Output: list of rule dicts:
  {
    "id": "twr_low",
    "level": "danger"|"warning"|"info",
    "msg": "ข้อความสั้นอธิบายปัญหา",
    "suggestion": "ข้อเสนอแนะเชิงปฏิบัติ",
    "fields": ["thrust_ratio","prop_result.effect.motor_load"]  # related fields
  }
"""

from typing import List, Dict, Any

def _get(d: Dict, path: str, default=None):
    """safely get nested values by dot path, e.g. 'advanced.power.est_hover_power_w'"""
    try:
        cur = d
        for part in path.split('.'):
            if cur is None:
                return default
            if isinstance(cur, dict):
                cur = cur.get(part, default)
            else:
                return default
        return cur if cur is not None else default
    except Exception:
        return default

def evaluate_rules(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules = []

    # helper to add rule
    def add(rule_id, level, msg, suggestion="", fields=None):
        rules.append({
            "id": rule_id,
            "level": level,
            "msg": msg,
            "suggestion": suggestion,
            "fields": fields or []
        })

    # 1) TWR checks (prefer using advanced.thrust_ratio if available)
    twr = _get(analysis, "advanced.thrust_ratio", _get(analysis, "thrust_ratio", None))
    style = _get(analysis, "style", "").lower()
    try:
        twr_f = float(twr) if twr is not None else None
    except Exception:
        twr_f = None

    # desired ranges per style
    style_targets = {
        "freestyle": (1.8, 2.5),
        "racing": (2.0, 3.5),
        "longrange": (0.9, 1.4),
        "cine": (1.0, 1.4),
        "micro": (1.6, 2.6)
    }
    low, high = style_targets.get(style, (1.2, 2.2))

    if twr_f is None:
        add("twr_unknown", "info", "ไม่สามารถคำนวณ TWR (ข้อมูลไม่ครบ)", "เพิ่มข้อมูล thrust หรือ motor/prop spec", ["thrust_ratio"])
    else:
        if twr_f < low:
            add("twr_low", "danger",
                f"TWR ต่ำ ({twr_f:.2f}) — ต่ำกว่าแนะนำสำหรับสไตล์ {style or 'ทั่วไป'}",
                "เพิ่มแรงขับ (มอเตอร์แรงขึ้น/ใบพัดที่ให้ thrust มากขึ้น หรือลดน้ำหนัก)",
                ["thrust_ratio"])
        elif twr_f > high * 1.6:
            # super high thrust — may cause oscillations or battery drain
            add("twr_too_high", "warning",
                f"TWR สูงมาก ({twr_f:.2f}) — อาจสิ้นเปลืองพลังงานหรือทำให้ระบบสั่น",
                "ลด KV หรือลองใบพัดที่ให้แรงขับน้อยลง / เช็ค PID & filter",
                ["thrust_ratio"])

    # 2) Flight time too low
    est_time = _get(analysis, "advanced.power.est_flight_time_min", _get(analysis, "battery_est", None))
    try:
        est_time_f = float(est_time) if est_time is not None else None
    except Exception:
        est_time_f = None

    if est_time_f is not None:
        if est_time_f < 2:
            add("short_flight", "danger",
                f"เวลาบินคาดการณ์สั้น ({est_time_f:.0f} นาที) — อันตรายต่อการบินจริง",
                "เพิ่มความจุแบตหรือลดน้ำหนัก/โหลด",
                ["advanced.power.est_flight_time_min", "battery_est"])
        elif est_time_f < 4:
            add("shortish_flight", "warning",
                f"เวลาบินคาดการณ์ต่ำ ({est_time_f:.0f} นาที)",
                "ถ้าต้องการบินนานขึ้น พิจารณาแบตความจุสูงขึ้นหรือปรับสไตล์การบิน",
                ["advanced.power.est_flight_time_min"])

    # 3) Motor load / prop warnings
    motor_load = _get(analysis, "prop_result.effect.motor_load", _get(analysis, "prop_result.effect.motor_load", 0))
    try:
        ml = float(motor_load)
    except Exception:
        ml = 0
    if ml >= 6:  # motor_load max score from prop_logic is 6
        add("motor_overload", "danger",
            f"โหลดมอเตอร์สูงสุด ({ml}/6) — ใบพัดหนัก pitch สูง+4ใบ เสี่ยงมอเตอร์ร้อน",
            "ลดขนาด/pitch ของใบพัด หรือเลือกมอเตอร์ที่รองรับโหลดสูงขึ้น",
            ["prop_result.effect.motor_load"])
    elif ml >= 4:  # score 4-5 out of 6 = moderately loaded
        add("motor_heavy", "warning",
            f"โหลดมอเตอร์ค่อนข้างสูง ({ml}/6)",
            "ตรวจสอบอุณหภูมิหลังบิน และพิจารณาใบพัด/มอเตอร์ที่เหมาะสม",
            ["prop_result.effect.motor_load"])

    # 4) Noise -> vibration risk
    noise = _get(analysis, "prop_result.effect.noise", 0)
    try:
        noise_v = float(noise)
    except Exception:
        noise_v = 0
    if noise_v >= 7:
        add("noise_high", "warning",
            "ระดับเสียง/สัญญาณสั่นสูง — อาจเกิดแบนด์สปริงหรืออาการสั่น",
            "ตรวจสอบการ balance ใบพัด และปรับ filter (dterm/gyro lowpass)",
            ["prop_result.effect.noise"])

    # 5) Prop size vs frame size (simple sanity)
    size = _get(analysis, "size", None) or _get(analysis, "preset_used", None)
    prop_size = _get(analysis, "prop_result.summary", "")
    # quick check: if prop_result summary contains inches we might check, otherwise skip
    # This is conservative: we only warn if prop_size seems larger than frame
    try:
        frame_size = float(_get(analysis, "size", 0))
        # attempt to parse prop size from analysis.prop_result.summary if available, else skip
        import re
        m = re.search(r'(\d+(?:\.\d+)?)"', str(_get(analysis, "prop_size", "")))
        if m:
            pval = float(m.group(1))
        else:
            pval = _get(analysis, "prop_size", None)
            if pval is not None:
                pval = float(pval)
    except Exception:
        pval = None
        frame_size = None

    if pval and frame_size:
        if pval > frame_size + 0.5:
            add("prop_too_big", "info",
                f"ขนาดใบพัด ({pval}\") ใหญ่กว่าเฟรม ({frame_size}\") — อาจติดเฟรม",
                "ตรวจใบพัด/ตำแหน่งมอเตอร์ หรือใช้เฟรมใหญ่ขึ้น",
                ["prop_size", "size"])

    # 6) Pitch vs KV rough heuristic (high pitch + high KV -> high amps)
    pitch = _get(analysis, "prop_result.pitch", _get(analysis, "pitch", None))
    kv = _get(analysis, "motor_kv", None) or _get(analysis, "detected_kv", None)
    try:
        pitch_v = float(pitch) if pitch is not None else None
    except Exception:
        pitch_v = None
    try:
        kv_v = float(kv) if kv is not None else None
    except Exception:
        kv_v = None

    if pitch_v and kv_v:
        if pitch_v >= 4.5 and kv_v > 2600:
            add("amp_risk", "warning",
                f"ใบพัด Pitch {pitch_v} กับ KV {kv_v} — เสี่ยงกระแสสูง",
                "ลด KV หรือลด pitch หรือใช้แบตที่รองรับกระแสสูงขึ้น",
                ["pitch", "motor_kv"])

    # 7) PID / Filter sanity checks (if present)
    # Example: if D high but D-term filter low -> possible oscillation
    d_roll = _get(analysis, "pid.roll.d", _get(analysis, "pid.roll.d", None))
    dterm_lpf = _get(analysis, "filter.dterm_lpf1", _get(analysis, "filter_baseline.dterm_lowpass", None))
    try:
        d_roll_v = float(d_roll) if d_roll is not None else None
        dterm_v = float(dterm_lpf) if dterm_lpf is not None else None
    except Exception:
        d_roll_v = None
        dterm_v = None

    if d_roll_v and d_roll_v > 60 and dterm_v and dterm_v < 100:
        add("dterm_filter", "warning",
            "D-term สูง แต่ lowpass ต่ำ — เสี่ยงเกิดโอซซิลเลชัน",
            "เพิ่มค่า D-term filter หรือลด D ถ้ายังเกิดอาการสั่น",
            ["pid.roll.d", "filter.dterm_lpf1"])

    # 8) Battery capacity sanity against size
    # FIX: battery_est คือ "นาที" ไม่ใช่ mAh — ต้องอ่านจาก advanced.power.battery_mAh_used เท่านั้น
    batt_mAh = _get(analysis, "advanced.power.battery_mAh_used",
                    _get(analysis, "advanced.battery_mAh_used", None))
    try:
        batt_mAh_v = int(batt_mAh) if batt_mAh is not None else None
    except Exception:
        batt_mAh_v = None

    if batt_mAh_v:
        # simple thresholds by frame size
        if frame_size:
            if frame_size >= 6 and batt_mAh_v < 1500:
                add("batt_small_for_frame", "warning",
                    f"แบต {batt_mAh_v}mAh น้อยสำหรับเฟรม {frame_size}\" — อาจเวลาบินสั้น",
                    "ใช้แบตความจุสูงขึ้นหรือลดน้ำหนัก",
                    ["advanced.power.battery_mAh_used", "size"])
            if frame_size <= 4 and batt_mAh_v > 2200:
                add("batt_unusual", "info",
                    f"แบต {batt_mAh_v}mAh ค่อนข้างใหญ่สำหรับเฟรม {frame_size}\" — ตรวจสอบน้ำหนัก",
                    "ตรวจสอบความเข้ากันของรูปทรงและสายไฟ/ตำแหน่งแบต",
                    ["advanced.power.battery_mAh_used", "size"])

    # final: if no rules triggered, friendly info
    if not rules:
        add("all_good", "info", "ค่าตรวจสอบเบื้องต้น ปกติดี", "ทดสอบบินจริงเพื่อตรวจสอบรายละเอียดเพิ่มเติม", [])

    return rules