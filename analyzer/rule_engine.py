# analyzer/rule_engine.py — OBIXConfig Doctor v5.0
# ================================================================
# Rule-based tuning engine
# v5 additions: tip speed, ESC sizing, C-rating burst,
#               hover throttle%, KV×cells matrix, motor temp
# ================================================================
from typing import List, Dict, Any

def _get(d, path, default=None):
    try:
        cur = d
        for part in path.split('.'):
            if cur is None: return default
            if isinstance(cur, dict): cur = cur.get(part, default)
            else: return default
        return cur if cur is not None else default
    except Exception:
        return default

def evaluate_rules(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules = []
    def add(rid, level, msg, suggestion="", fields=None):
        rules.append({"id":rid,"level":level,"msg":msg,"suggestion":suggestion,"fields":fields or []})

    style = _get(analysis,"style","").lower()

    # ── 1) TWR ────────────────────────────────────────────────
    twr = _get(analysis,"advanced.thrust_ratio", _get(analysis,"thrust_ratio"))
    try: twr_f = float(twr) if twr is not None else None
    except Exception: twr_f = None
    # Realistic TWR ranges: (min_ok, max_ok, absolute_max_warn)
    # FPV quads are naturally overpowered — freestyle/racing 6-9 TWR is NORMAL
    style_targets = {
        "freestyle": (1.8, 9.0,  11.0),
        "racing":    (2.5, 10.0, 12.0),
        "longrange": (1.0, 5.5,   7.0),
        "cine":      (1.0, 4.5,   6.0),
        "micro":     (2.0, 9.0,  11.0),
    }
    lo, hi, abs_max = style_targets.get(style, (1.2, 7.0, 10.0))
    if twr_f is None:
        add("twr_unknown","info","ไม่สามารถคำนวณ TWR (ข้อมูลไม่ครบ)",
            "เพิ่มข้อมูล motor KV และ prop spec", ["thrust_ratio"])
    elif twr_f < lo:
        add("twr_low","danger",
            f"TWR ต่ำ ({twr_f:.2f}) — ต่ำกว่าแนะนำสำหรับสไตล์ {style or 'ทั่วไป'}",
            "เพิ่มแรงขับ: มอเตอร์แรงขึ้น / ใบพัดที่ thrust มากขึ้น / ลดน้ำหนัก",
            ["thrust_ratio"])
    elif twr_f > abs_max:
        add("twr_very_high","warning",
            f"TWR สูงมาก ({twr_f:.2f}) — เกินขีดปกติสำหรับ {style} build",
            "ลด KV หรือใช้ใบพัดที่ให้ thrust น้อยลง / ตรวจ PID filter",
            ["thrust_ratio"])

    # ── 2) Flight time ────────────────────────────────────────
    est_time = _get(analysis,"advanced.power.est_flight_time_min",
                    _get(analysis,"battery_est"))
    try: est_time_f = float(est_time) if est_time is not None else None
    except Exception: est_time_f = None
    if est_time_f is not None:
        if est_time_f < 2:
            add("short_flight","danger",
                f"เวลาบินคาดการณ์สั้นมาก ({est_time_f:.0f} นาที)",
                "เพิ่มความจุแบตหรือลดน้ำหนัก", ["est_flight_time_min"])
        elif est_time_f < 4:
            add("shortish_flight","warning",
                f"เวลาบินคาดการณ์ต่ำ ({est_time_f:.0f} นาที)",
                "พิจารณาแบตความจุสูงขึ้นหรือ LR style", ["est_flight_time_min"])

    # ── 3) Motor load / prop ──────────────────────────────────
    ml = _get(analysis,"prop_result.effect.motor_load", 0)
    try: ml = float(ml)
    except Exception: ml = 0
    if ml >= 6:
        add("motor_overload","danger",
            f"โหลดมอเตอร์สูงสุด ({ml}/6) — ใบพัดหนัก pitch สูง + 4 ใบ เสี่ยงมอเตอร์ร้อน",
            "ลดขนาด/pitch ของใบพัด หรือมอเตอร์ที่รองรับโหลดสูงขึ้น",
            ["prop_result.effect.motor_load"])
    elif ml >= 4:
        add("motor_heavy","warning",
            f"โหลดมอเตอร์ค่อนข้างสูง ({ml}/6)",
            "ตรวจสอบอุณหภูมิหลังบิน", ["prop_result.effect.motor_load"])

    # ── 4) Noise / vibration ──────────────────────────────────
    noise = _get(analysis,"prop_result.effect.noise", 0)
    try: noise = float(noise)
    except Exception: noise = 0
    if noise >= 5:
        add("noise_high","warning",
            "ระดับเสียง/สัญญาณสั่นสูง — เสี่ยงแบนด์สปริง",
            "Balance ใบพัด และปรับ dterm/gyro lowpass", ["prop_result.effect.noise"])

    # ── 5) Tip speed (NEW v5) ─────────────────────────────────
    tip_speed = _get(analysis,"advanced.tip_speed_mps",
                     _get(analysis,"prop_result.effect.tip_speed_mps"))
    try: tip_f = float(tip_speed) if tip_speed else None
    except Exception: tip_f = None
    if tip_f:
        if tip_f >= 290:
            add("tip_speed_danger","danger",
                f"Tip speed {tip_f} m/s เกินขีดจำกัด 290 m/s — compressibility loss รุนแรง",
                "ลด KV หรือใช้ props เล็กลง/pitch ต่ำลง",
                ["advanced.tip_speed_mps"])
        elif tip_f >= 265:
            add("tip_speed_warn","warning",
                f"Tip speed {tip_f} m/s ใกล้ขีดจำกัด (265 m/s) — efficiency ลดที่ full throttle",
                "พิจารณาลด KV เล็กน้อย หรือเลือก prop pitch ต่ำลง",
                ["advanced.tip_speed_mps"])

    # ── 6) ESC sizing (NEW v5) ────────────────────────────────
    peak_per_motor = _get(analysis,"advanced.peak_per_motor_a",
                          _get(analysis,"advanced.power.peak_per_motor_a"))
    esc_limit = _get(analysis,"esc_current_limit_a")
    esc_recommended = _get(analysis,"advanced.esc_recommended_a",
                           _get(analysis,"advanced.power.esc_recommended_a"))
    try: peak_m_f = float(peak_per_motor) if peak_per_motor else None
    except Exception: peak_m_f = None
    try: esc_lim_f = float(esc_limit) if esc_limit else None
    except Exception: esc_lim_f = None
    if peak_m_f and esc_lim_f and peak_m_f > esc_lim_f:
        add("esc_undersized","danger",
            f"Peak current/motor {peak_m_f:.1f}A เกิน ESC limit {esc_lim_f:.0f}A — เสี่ยง ESC ไหม้!",
            f"ใช้ ESC ≥{esc_recommended or int(peak_m_f*1.3)}A หรือลด prop/KV",
            ["esc_current_limit_a","advanced.peak_per_motor_a"])
    elif peak_m_f and not esc_limit and esc_recommended:
        add("esc_suggestion","info",
            f"ESC แนะนำ ≥{esc_recommended}A continuous ต่อมอเตอร์ (peak ~{peak_m_f:.0f}A)",
            "เลือก ESC ที่ rated continuous ≥ ค่าแนะนำ","[]")

    # ── 7) C-rating burst (NEW v5) ────────────────────────────
    c_burst = _get(analysis,"advanced.c_burst",
                   _get(analysis,"advanced.power.c_burst"))
    c_cont  = _get(analysis,"advanced.c_continuous",
                   _get(analysis,"advanced.power.c_continuous"))
    c_rec   = _get(analysis,"advanced.c_recommended",
                   _get(analysis,"advanced.power.c_recommended"))
    try: c_burst_f = float(c_burst) if c_burst else None
    except Exception: c_burst_f = None
    if c_burst_f:
        if c_burst_f > 80:
            add("c_rating_extreme","danger",
                f"C-rating burst {c_burst_f:.0f}C สูงมาก — แบตร้อน voltage sag รุนแรง",
                f"ใช้แบตที่ rated ≥{c_rec or int(c_burst_f*1.2)}C burst หรือเพิ่ม mAh",
                ["advanced.c_burst"])
        elif c_burst_f > 55:
            add("c_rating_high","warning",
                f"C-rating burst {c_burst_f:.0f}C ค่อนข้างสูง",
                f"แนะนำแบต ≥{c_rec or int(c_burst_f*1.2)}C burst เพื่อ voltage sag น้อยลง",
                ["advanced.c_burst"])

    # ── 8) Hover throttle (NEW v5) ────────────────────────────
    hover_pct = _get(analysis,"advanced.hover_throttle_pct",
                     _get(analysis,"advanced.power.hover_throttle_pct"))
    try: hover_pct_f = float(hover_pct) if hover_pct else None
    except Exception: hover_pct_f = None
    if hover_pct_f:
        if hover_pct_f > 60 and style not in ("longrange","cine"):
            add("hover_throttle_high","warning",
                f"Hover throttle ~{hover_pct_f:.0f}% — สูงมาก แบตและมอเตอร์รับโหลดตลอดเวลา",
                "ลดน้ำหนัก หรือเพิ่ม KV/ใบพัด/แรงดัน",
                ["advanced.hover_throttle_pct"])
        elif hover_pct_f < 20 and style in ("racing","freestyle"):
            add("hover_throttle_low","info",
                f"Hover throttle ~{hover_pct_f:.0f}% — overpowered build",
                "Freestyle/racing: มักต้องการ hover 25–40% เพื่อ control feel ดี",
                ["advanced.hover_throttle_pct"])

    # ── 9) KV × cells matrix ─────────────────────────────────
    kv = _get(analysis,"motor_kv") or _get(analysis,"advanced.kv_suggestion")
    cells = _get(analysis,"advanced.cells")
    try:
        kv_f    = float(kv) if kv and str(kv).replace('.','').isdigit() else None
        cells_f = float(cells) if cells else None
    except Exception: kv_f=cells_f=None
    if kv_f and cells_f:
        kv_v = kv_f * cells_f * 4.2  # eRPM × pole → RPM rough
        if cells_f >= 7 and kv_f > 1600:
            add("kv_high_voltage","danger",
                f"KV {kv_f:.0f} บน {cells_f:.0f}S — RPM สูงมาก ความเสี่ยง ESC/motor พัง",
                "ลด KV ≤ 1500 สำหรับ 7S+, ≤ 1200 สำหรับ 8S",
                ["motor_kv","advanced.cells"])
        elif cells_f <= 3 and kv_f < 2000:
            add("kv_low_cells","warning",
                f"KV {kv_f:.0f} ต่ำบน {cells_f:.0f}S — แรงอาจไม่พอ",
                "3S ควรใช้ KV ≥ 2000 เพื่อ RPM เพียงพอ",
                ["motor_kv"])

    # ── 10) Prop vs frame size ────────────────────────────────
    try:
        frame_size = float(_get(analysis,"size",0))
        prop_size  = _get(analysis,"prop_size")
        if prop_size: prop_size = float(prop_size)
    except Exception: frame_size=0; prop_size=None
    if prop_size and frame_size and prop_size > frame_size + 0.5:
        add("prop_too_big","info",
            f"ใบพัด {prop_size}\" ใหญ่กว่าเฟรม {frame_size}\" — อาจติดเฟรม",
            "ตรวจตำแหน่งมอเตอร์และระยะหวีดของใบพัด",
            ["prop_size","size"])

    # ── 11) Pitch × KV ───────────────────────────────────────
    pitch = _get(analysis,"pitch")
    try: pitch_f = float(pitch) if pitch else None
    except Exception: pitch_f = None
    if pitch_f and kv_f and pitch_f >= 4.5 and kv_f > 2600:
        add("amp_risk","warning",
            f"Pitch {pitch_f} + KV {kv_f:.0f} — เสี่ยงกระแสสูง voltage sag",
            "ลด KV หรือลด pitch หรือแบต C-rating สูงขึ้น",
            ["pitch","motor_kv"])

    # ── 12) D-term vs filter ──────────────────────────────────
    d_roll   = _get(analysis,"pid.roll.d")
    dterm_lpf = _get(analysis,"filter.dterm_lpf1", _get(analysis,"filter_baseline.dterm_lpf1"))
    try:
        d_v  = float(d_roll) if d_roll else None
        dt_v = float(dterm_lpf) if dterm_lpf else None
    except Exception: d_v=dt_v=None
    if d_v and d_v > 60 and dt_v and dt_v < 100:
        add("dterm_filter","warning",
            "D-term สูง แต่ D-term lowpass ต่ำ — เสี่ยง oscillation",
            "เพิ่ม dterm_lpf1 หรือลด D",
            ["pid.roll.d","filter.dterm_lpf1"])

    # ── 13) RPM filter ────────────────────────────────────────
    rpm_filter = _get(analysis,"filter.rpm_filter",_get(analysis,"filter_baseline.rpm_filter"))
    try:
        rpm_on = None if rpm_filter is None else (
            rpm_filter if isinstance(rpm_filter,bool)
            else str(rpm_filter).strip().lower() not in ("false","0","off","none",""))
    except Exception: rpm_on = None
    if rpm_on is False:
        add("rpm_filter_off","warning",
            "RPM Filter ปิดอยู่ — แนะนำเปิดถ้า ESC รองรับ DSHOT Bidir",
            "CLI: set dshot_bidir = ON  (ต้องการ DSHOT300+)",
            ["filter.rpm_filter"])

    # ── 14) Battery capacity vs frame ────────────────────────
    batt_mAh = _get(analysis,"advanced.power.battery_mAh_used",
                    _get(analysis,"advanced.battery_mAh_used"))
    try: batt_mAh_v = int(batt_mAh) if batt_mAh else None
    except Exception: batt_mAh_v = None
    if batt_mAh_v and frame_size:
        if frame_size >= 6 and batt_mAh_v < 1500:
            add("batt_small","warning",
                f"แบต {batt_mAh_v}mAh น้อยสำหรับเฟรม {frame_size}\"",
                "ใช้แบตความจุสูงขึ้น", ["advanced.power.battery_mAh_used","size"])
        if frame_size <= 4 and batt_mAh_v > 2200:
            add("batt_heavy","info",
                f"แบต {batt_mAh_v}mAh ค่อนข้างใหญ่สำหรับ {frame_size}\" — ตรวจน้ำหนัก",
                "ตรวจน้ำหนักรวมและตำแหน่งแบต", ["advanced.power.battery_mAh_used","size"])

    if not rules:
        add("all_good","info","ค่าตรวจสอบเบื้องต้น ปกติดี",
            "ทดสอบบินจริงเพื่อปรับรายละเอียด", [])
    return rules
