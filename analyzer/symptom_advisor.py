# analyzer/symptom_advisor.py — OBIXConfig Doctor v5 Pro
# ============================================================
# PID Symptom → Fix Advisor — Advanced Edition
#
# v5 Pro additions:
#   - severity: critical / high / medium / low
#   - confidence: how reliable is this diagnosis
#   - related: cross-linked symptoms
#   - bf_version: BF version notes
#   - blackbox_hint: what to look for in logs
#   - axes_affected: which axes matter most
#   - quick_win: fastest single fix to try
#   - 8 new symptoms added
# ============================================================
from __future__ import annotations
from typing import Dict, Any, List

SYMPTOMS: Dict[str, Dict[str, Any]] = {

    # ─── OSCILLATION ──────────────────────────────────────────
    "oscillation_after_flip": {
        "label": "สั่นหลัง Flip / Roll",
        "label_en": "Post-maneuver oscillation",
        "category": "oscillation",
        "severity": "high",
        "confidence": 90,
        "icon": "🌀",
        "color": "#f87171",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "ลด D roll/pitch ลง 3 ก่อน",
        "related": ["propwash", "motor_hot"],
        "diagnosis": (
            "อาการสั่นหลัง flip หรือ roll มักเกิดจาก D-term สูงเกินไป "
            "หรือ D-term filter ต่ำเกินไปจนทำให้ noise กระตุ้น motors ต่อเนื่อง "
            "อาจเกิดจาก P สูงเกินไปด้วยถ้าสั่นทันทีในระหว่างทำ maneuver"
        ),
        "primary_cause": "D-term สูง / D-term filter ต่ำ",
        "blackbox_hint": "ดู D-term trace — จะเห็น spike สูงหลัง flip ถ้า D สูงเกิน",
        "bf_version_note": "BF4.4+: ลอง d_min แยกกันก่อนลด D หลัก",
        "adjustments": [
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "3–5",
             "delta": -4, "axis": "both",
             "reason": "ลด D-term ลดการตอบสนองต่อ noise หลัง maneuver"},
            {"param": "dterm_lpf1_hz", "direction": "ลด", "amount": "10–20 Hz",
             "delta": -15, "axis": "filter",
             "reason": "Filter D-term มากขึ้น ลด noise ที่ amplify"},
            {"param": "p_roll / p_pitch", "direction": "ลดเล็กน้อย", "amount": "2–3",
             "delta": -3, "axis": "both",
             "reason": "ถ้า P สูงเกินก็ส่งเสริม oscillation"},
        ],
        "cli_template": [
            "# Fix: Post-flip oscillation",
            "set d_roll  = {d_roll-3}",
            "set d_pitch = {d_pitch-3}",
            "set dterm_lpf1_static_hz = {dterm_lpf1-15}",
            "save",
        ],
        "tips": [
            "ลด D ทีละ 3 แล้วบินซ้ำ — หยุดเมื่อ propwash เริ่มเพิ่ม",
            "ถ้าลด D แล้ว propwash เพิ่มขึ้น = D ยังต้องการ ปรับ filter แทน",
            "ใช้ Blackbox ดูว่า gyro noise กระโดดสูงตอนไหน",
            "BF4.4+: ลอง d_min_roll/pitch แยกกับ d_roll หลัก",
        ],
    },

    "propwash": {
        "label": "Propwash หลัง Throttle Drop",
        "label_en": "Propwash oscillation",
        "category": "propwash",
        "severity": "high",
        "confidence": 85,
        "icon": "💨",
        "color": "#fb923c",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "เพิ่ม D roll/pitch +4 และเปิด RPM filter",
        "related": ["oscillation_after_flip", "motor_hot"],
        "diagnosis": (
            "Propwash เกิดตอนลด throttle กะทันหันแล้วเพิ่มอีกครั้ง "
            "เป็น chaos ของ airflow ที่ propeller ตัวเองสร้าง "
            "D-term ต่ำ, I-term ต่ำ หรือ P ต่ำ ล้วนทำให้แย่ลง "
        ),
        "primary_cause": "D-term ต่ำ, RPM filter ไม่ดี, I ต่ำ",
        "blackbox_hint": "ดู gyro trace หลัง punch-out — ถ้าสั่น low-freq = propwash จริง",
        "bf_version_note": "BF4.3+: ลอง iterm_relax_cutoff = 10 ช่วย propwash ได้",
        "adjustments": [
            {"param": "d_roll / d_pitch", "direction": "เพิ่ม", "amount": "3–5",
             "delta": 4, "axis": "both",
             "reason": "D-term ช่วย damp propwash ได้ดี"},
            {"param": "anti_gravity_gain", "direction": "เพิ่ม", "amount": "7–10",
             "delta": 3, "axis": "filter",
             "reason": "Anti-gravity เพิ่ม I ชั่วคราวตอน throttle change"},
            {"param": "dshot_bidir + rpm_filter", "direction": "เปิด", "amount": "ON",
             "delta": 0, "axis": "system",
             "reason": "RPM filter ลด motor noise ทำให้ motors smooth"},
            {"param": "i_roll / i_pitch", "direction": "ตรวจสอบ", "amount": "85–95",
             "delta": 5, "axis": "both",
             "reason": "I-term ต่ำทำให้ไม่ lock-in ระหว่าง throttle change"},
        ],
        "cli_template": [
            "# Fix: Propwash",
            "set d_roll  = {d_roll+4}",
            "set d_pitch = {d_pitch+4}",
            "set anti_gravity_gain = 8",
            "set dshot_bidir = ON",
            "set rpm_filter_harmonics = 3",
            "save",
        ],
        "tips": [
            "Propwash แก้ยากที่สุด — ใช้หลายวิธีรวมกัน",
            "RPM filter + D เพิ่ม คือคู่ที่ได้ผลดีที่สุด",
            "ลอง iterm_relax_cutoff = 10 ใน BF4.3+",
            "Balance ใบพัดก่อน — imbalance ทำ propwash รุนแรงขึ้นมาก",
            "ทดสอบด้วย punch-out จาก hover → full throttle → mid",
        ],
    },

    "high_freq_oscillation": {
        "label": "สั่นความถี่สูง (Buzz / High-freq oscillation)",
        "label_en": "High frequency P-term oscillation",
        "category": "oscillation",
        "severity": "critical",
        "confidence": 92,
        "icon": "⚡",
        "color": "#f87171",
        "axes_affected": ["roll", "pitch", "yaw"],
        "quick_win": "ลด P roll/pitch ลง 5 ทันที",
        "related": ["motor_hot", "oscillation_after_flip"],
        "diagnosis": (
            "การสั่นความถี่สูงที่รู้สึกได้ผ่าน frame — เหมือน buzz หรือ vibration "
            "ที่ไม่ลดลงแม้ตอน hover หรือ straight flight "
            "สาเหตุหลัก: P สูงเกินไป ทำให้ FC overcorrect ต่อเนื่อง "
            "อาจเลวร้ายขึ้นถ้า gyro noise สูง (ใบพัด imbalance, motor bearing)"
        ),
        "primary_cause": "P-term สูงเกิน → overcorrection loop",
        "blackbox_hint": "ดู P-term trace — จะเห็น high-freq oscillation ตลอดเวลา ไม่เฉพาะ maneuver",
        "bf_version_note": "BF4.4: ลอง p_roll ลด 5 แล้วบิน 1 แพ็ค ประเมินใหม่",
        "adjustments": [
            {"param": "p_roll / p_pitch", "direction": "ลด", "amount": "5–10",
             "delta": -6, "axis": "both",
             "reason": "P สูงเกินทำให้ FC overcorrect ต่อเนื่อง"},
            {"param": "gyro_lpf1_hz", "direction": "ลด", "amount": "20–30 Hz",
             "delta": -20, "axis": "filter",
             "reason": "กรอง gyro noise ที่ feed กลับเข้า P loop"},
            {"param": "dterm_lpf1_hz", "direction": "ลด", "amount": "10–15 Hz",
             "delta": -12, "axis": "filter",
             "reason": "ลด D ที่ amplify oscillation"},
        ],
        "cli_template": [
            "# Fix: High-freq oscillation",
            "set p_roll  = {p_roll-6}",
            "set p_pitch = {p_pitch-6}",
            "set gyro_lpf1_static_hz = {gyro_lpf1-20}",
            "save",
        ],
        "tips": [
            "ลด P ทีละ 5 — หยุดเมื่อ buzz หายไป",
            "ถ้าลด P มากแล้วยัง buzz อยู่ = ปัญหา hardware (ใบพัด, motor)",
            "ตรวจ motor bearing: หมุนด้วยมือ ต้องราบเรียบ ไม่มีสะดุด",
            "Balance ใบพัดทุกใบก่อน tune PID",
        ],
    },

    "yaw_spin": {
        "label": "หมุน Yaw เอง / Yaw Spin",
        "label_en": "Uncontrolled yaw rotation",
        "category": "yaw",
        "severity": "critical",
        "confidence": 80,
        "icon": "🔄",
        "color": "#f87171",
        "axes_affected": ["yaw"],
        "quick_win": "ตรวจ motor direction และ prop direction ก่อน",
        "related": ["toilet_bowl", "not_arming"],
        "diagnosis": (
            "โดรนหมุน yaw โดยไม่ได้ input มักเกิดจาก: "
            "1) ใบพัดติดผิดทาง หรือ motor หมุนผิดทิศ "
            "2) P_yaw สูงเกินทำให้ oscillate บน yaw axis "
            "3) motor ตัวใดตัวหนึ่งแรงหรืออ่อนกว่าคนอื่น (motor mismatch)"
        ),
        "primary_cause": "Motor direction ผิด / Prop ติดผิด / P_yaw สูง",
        "blackbox_hint": "ดู yaw gyro trace — ถ้า drift ไปทิศเดียวคงที่ = hardware ผิด",
        "bf_version_note": "",
        "adjustments": [
            {"param": "motor direction", "direction": "ตรวจสอบ", "amount": "ตาม motor map",
             "delta": 0, "axis": "system",
             "reason": "Motor ผิดทาง 1 ตัวทำให้ yaw spin รุนแรง"},
            {"param": "p_yaw", "direction": "ลด", "amount": "5–8",
             "delta": -5, "axis": "yaw",
             "reason": "P_yaw สูงทำให้ oscillate บน yaw axis"},
            {"param": "i_yaw", "direction": "ลดเล็กน้อย", "amount": "3–5",
             "delta": -4, "axis": "yaw",
             "reason": "I_yaw สูงเกินทำให้ yaw drift สะสม"},
        ],
        "cli_template": [
            "# Fix: Yaw spin",
            "# 1. ตรวจ motor direction ใน BF Configurator → Motors",
            "# 2. ตรวจ props — ใบพัด CW/CCW ถูกตำแหน่ง?",
            "set p_yaw = {p_yaw-5}",
            "set i_yaw = {i_yaw-4}",
            "save",
        ],
        "tips": [
            "ตรวจ motor direction ก่อนเสมอ — ปัญหา hardware แก้ด้วย PID ไม่ได้",
            "Yaw spin จาก P สูง: จะเห็น oscillation ชัดเมื่อ hover",
            "Motor mismatch: บินแล้ว 1 มอเตอร์ร้อนกว่าคนอื่นมาก = mismatch",
            "ตรวจสอบ ESC calibration: all-at-once calibration ใหม่",
        ],
    },

    "slow_response": {
        "label": "ตอบสนองช้า / Drone เฉื่อย",
        "label_en": "Sluggish / mushy response",
        "category": "response",
        "severity": "medium",
        "confidence": 88,
        "icon": "🐌",
        "color": "#f59e0b",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "เพิ่ม Feedforward roll/pitch +15",
        "related": ["wind_rejection"],
        "diagnosis": (
            "โดรนตอบสนองต่อ stick input ช้าหรือรู้สึก 'mushy' "
            "มักเกิดจาก P ต่ำเกิน, feedforward ต่ำ หรือ filter aggressive เกิน "
            "อาจเกิดจาก rates ต่ำด้วยถ้าความเร็ว rotation ไม่เพียงพอ"
        ),
        "primary_cause": "P ต่ำ / feedforward ต่ำ / filter aggressive",
        "blackbox_hint": "ดู setpoint vs gyro — ถ้า gyro ตามไม่ทัน setpoint = ต้องเพิ่ม P หรือ FF",
        "bf_version_note": "BF4.4+: feedforward_roll/pitch แยกกัน ปรับทีละ axis ได้",
        "adjustments": [
            {"param": "feedforward_roll / pitch", "direction": "เพิ่ม", "amount": "10–20",
             "delta": 15, "axis": "both",
             "reason": "Feedforward ตอบสนองต่อ stick velocity โดยตรง — quickest fix"},
            {"param": "p_roll / p_pitch", "direction": "เพิ่ม", "amount": "3–5",
             "delta": 4, "axis": "both",
             "reason": "P สูงขึ้นทำให้ตอบสนองเร็ว"},
            {"param": "gyro_lpf1_hz", "direction": "เพิ่ม", "amount": "20–30 Hz",
             "delta": 20, "axis": "filter",
             "reason": "Filter น้อยลง = latency ต่ำลง = response เร็วขึ้น"},
        ],
        "cli_template": [
            "# Fix: Slow/sluggish response",
            "set feedforward_roll  = {ff+15}",
            "set feedforward_pitch = {ff+15}",
            "set p_roll  = {p_roll+4}",
            "set p_pitch = {p_pitch+4}",
            "save",
        ],
        "tips": [
            "เพิ่ม Feedforward ก่อน P — FF ตอบสนองเร็วกว่าและ noise น้อยกว่า",
            "ตรวจสอบ rates ก่อน — rates ต่ำทำให้ response ช้าโดยธรรมชาติ",
            "เพิ่ม P ทีละ 3 จนเริ่มสั่น แล้วลดลง 5",
            "BF4.4: feedforward_jitter_factor = 7 ลด RC noise",
        ],
    },

    "propwash_snap": {
        "label": "Snap กลับหลัง Flip (I-term bounce)",
        "label_en": "I-term bounce / snap back",
        "category": "oscillation",
        "severity": "medium",
        "confidence": 82,
        "icon": "↩️",
        "color": "#fb923c",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "เปิด iterm_relax = RPH",
        "related": ["propwash", "wind_rejection"],
        "diagnosis": (
            "โดรน 'snap' กลับหลังจบ flip หรือ roll "
            "เกิดจาก I-term สะสม (wind-up) ระหว่าง maneuver แล้วปล่อยออกทันที "
            "iterm_relax ที่ปิดหรือตั้งค่าผิดทำให้ I ยังทำงานระหว่าง rapid stick input"
        ),
        "primary_cause": "I-term wind-up / iterm_relax ผิด",
        "blackbox_hint": "ดู I-term trace ระหว่าง flip — ถ้า I สะสมสูงแล้วพุ่งกลับ = wind-up",
        "bf_version_note": "BF4.3+: iterm_relax_type = SETPOINT ดีกว่า GYRO สำหรับ freestyle",
        "adjustments": [
            {"param": "iterm_relax", "direction": "เปิด/ตั้งค่า", "amount": "RPH",
             "delta": 0, "axis": "system",
             "reason": "Relax I ระหว่าง rapid input ป้องกัน wind-up"},
            {"param": "iterm_relax_type", "direction": "ตั้ง", "amount": "SETPOINT",
             "delta": 0, "axis": "system",
             "reason": "SETPOINT mode เหมาะกับ freestyle มากกว่า GYRO"},
            {"param": "iterm_relax_cutoff", "direction": "ปรับ", "amount": "10–15",
             "delta": 0, "axis": "system",
             "reason": "Cutoff freq ต่ำ = relax มากขึ้น ระหว่าง rapid maneuver"},
            {"param": "i_roll / i_pitch", "direction": "ลดเล็กน้อย", "amount": "5",
             "delta": -5, "axis": "both",
             "reason": "I ต่ำลงเล็กน้อย ลด magnitude ของ wind-up"},
        ],
        "cli_template": [
            "# Fix: I-term bounce / snap",
            "set iterm_relax        = RPH",
            "set iterm_relax_type   = SETPOINT",
            "set iterm_relax_cutoff = 12",
            "set i_roll  = {i_roll-5}",
            "set i_pitch = {i_pitch-5}",
            "save",
        ],
        "tips": [
            "iterm_relax = RPH คือการตั้งที่ดีที่สุดสำหรับ freestyle",
            "ลด cutoff ลงถ้ายัง snap อยู่ — ลอง 8 แล้ว 5",
            "อย่าลด I มากเกิน — I ต่ำทำให้กันลมไม่ดี",
        ],
    },

    "motor_hot": {
        "label": "มอเตอร์ร้อนหลังบิน",
        "label_en": "Motor overheating after flight",
        "category": "thermal",
        "severity": "high",
        "confidence": 85,
        "icon": "🌡️",
        "color": "#f87171",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "เปิด RPM filter และลด D -3",
        "related": ["high_freq_oscillation", "esc_desync"],
        "diagnosis": (
            "มอเตอร์ร้อนเกินปกติหลังบิน อาจเกิดจาก D-term สูงมากส่งกระแสสูงต่อเนื่อง "
            "ใบพัดหนักเกินสำหรับมอเตอร์ KV นั้น หรือ filter ไม่พอทำให้ motor ทำงานหนัก "
            "รวมถึง ESC desync ที่ทำให้มอเตอร์ stutter"
        ),
        "primary_cause": "D-term สูง / ใบพัดหนัก / filter ไม่ดี / ESC desync",
        "blackbox_hint": "ดู motor output trace — ถ้าสั่น high-freq ตลอด = D หรือ noise ปัญหา",
        "bf_version_note": "RPM filter ต้องใช้ BLHeli_32/AM32 + DSHOT Bidir",
        "adjustments": [
            {"param": "rpm_filter + dshot_bidir", "direction": "เปิด", "amount": "ON",
             "delta": 0, "axis": "system",
             "reason": "RPM filter ลด motor noise มากที่สุด ลด current ripple"},
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "3–5",
             "delta": -4, "axis": "both",
             "reason": "D สูงส่งกระแสสูงต่อเนื่องทำให้ motor ร้อน"},
            {"param": "dterm_lpf1_hz", "direction": "ลด", "amount": "15–20 Hz",
             "delta": -15, "axis": "filter",
             "reason": "Filter D-term มากขึ้น ลด high-freq noise"},
            {"param": "motor_pwm_protocol", "direction": "ตั้ง", "amount": "DSHOT600",
             "delta": 0, "axis": "system",
             "reason": "Digital protocol ลด ESC desync"},
        ],
        "cli_template": [
            "# Fix: Motor overheating",
            "set dshot_bidir          = ON",
            "set motor_pwm_protocol   = DSHOT600",
            "set rpm_filter_harmonics = 3",
            "set d_roll  = {d_roll-4}",
            "set d_pitch = {d_pitch-4}",
            "set dterm_lpf1_static_hz = {dterm_lpf1-15}",
            "save",
        ],
        "tips": [
            "วัดอุณหภูมิมอเตอร์หลังบิน 2 นาที — ควรต่ำกว่า 60°C",
            "ถ้า 1 มอเตอร์ร้อนกว่าอีก 3 ตัว = bearing ใกล้หมดหรือ winding ไหม้",
            "ลองใบพัดขนาดเล็กลงหรือ pitch ต่ำลง",
            "ตรวจ motor screws ไม่แน่นทำให้ vibration มากขึ้น",
        ],
    },

    "wind_rejection": {
        "label": "กันลมไม่อยู่ / Drone ล่องลอย",
        "label_en": "Poor wind rejection / drifting",
        "category": "pid_advanced",
        "severity": "medium",
        "confidence": 87,
        "icon": "🌬️",
        "color": "#f59e0b",
        "axes_affected": ["roll", "pitch", "yaw"],
        "quick_win": "เพิ่ม I roll/pitch +8",
        "related": ["toilet_bowl", "slow_response"],
        "diagnosis": (
            "โดรนไม่สามารถ hold position หรือ attitude ได้ดีเมื่อมีลม "
            "อาการ: โดรนถูกลมพัดไป ต้องใช้ stick ต้านตลอด "
            "สาเหตุหลัก: I-term ต่ำเกินไปทำให้ไม่ reject disturbance"
        ),
        "primary_cause": "I-term ต่ำ / iterm_relax ผิด / anti_gravity ต่ำ",
        "blackbox_hint": "ดู setpoint vs gyro ตอน hover ในลม — ถ้า error สะสม = I ต้องเพิ่ม",
        "bf_version_note": "iterm_relax = RPH ยังคงช่วยลม — I เพิ่มขึ้นได้โดยไม่ snap",
        "adjustments": [
            {"param": "i_roll / i_pitch", "direction": "เพิ่ม", "amount": "5–10",
             "delta": 8, "axis": "both",
             "reason": "I-term สูงขึ้นช่วย reject wind disturbance"},
            {"param": "i_yaw", "direction": "เพิ่ม", "amount": "3–5",
             "delta": 4, "axis": "yaw",
             "reason": "Yaw I ช่วย hold heading ในลม"},
            {"param": "anti_gravity_gain", "direction": "เพิ่ม", "amount": "7–12",
             "delta": 3, "axis": "filter",
             "reason": "Anti-gravity เพิ่ม I ชั่วคราวตอน throttle change ต้านลม"},
            {"param": "iterm_relax", "direction": "ตรวจสอบ", "amount": "RPH",
             "delta": 0, "axis": "system",
             "reason": "iterm_relax = OFF ทำให้ I ไม่สะสมได้ดีตอนบิน"},
        ],
        "cli_template": [
            "# Fix: Poor wind rejection",
            "set i_roll  = {i_roll+8}",
            "set i_pitch = {i_pitch+8}",
            "set i_yaw   = {i_yaw+4}",
            "set iterm_relax        = RPH",
            "set iterm_relax_type   = SETPOINT",
            "set iterm_relax_cutoff = 15",
            "set anti_gravity_gain  = 10",
            "save",
        ],
        "tips": [
            "ทดสอบในลมจริง — เพิ่ม I ทีละ 5 จนโดรน hold ได้ดีขึ้น",
            "Longrange build ควร I สูงกว่า freestyle เพราะต้องต้านลมระยะไกล",
            "ตรวจสอบ CoG — ถ้า CoG ไม่ตรงกลาง โดรนจะ drift แม้ PID ดี",
            "แบตเตอรี่หนักเกินศูนย์กลาง ทำให้ drift ในทิศที่แบตยื่น",
        ],
    },

    "toilet_bowl": {
        "label": "Toilet Bowl / วนเป็นวงกลมตอน Hover",
        "label_en": "Toilet bowl effect",
        "category": "pid_advanced",
        "severity": "medium",
        "confidence": 75,
        "icon": "🌀",
        "color": "#a78bfa",
        "axes_affected": ["yaw", "roll", "pitch"],
        "quick_win": "เพิ่ม I roll/pitch +5",
        "related": ["wind_rejection", "yaw_spin"],
        "diagnosis": (
            "อาการวนเป็นวงกลมขณะ hover มักเกิดจาก I-term ต่ำเกินไปทำให้ไม่ hold position "
            "หรือ yaw drift ร่วมกับ P ที่ไม่สมดุลระหว่าง roll และ pitch "
            "อาจเกิดจาก compass miscalibration ด้วยถ้ามี GPS"
        ),
        "primary_cause": "I-term ต่ำ / yaw drift / compass miscalibration",
        "blackbox_hint": "ดู yaw gyro — ถ้า drift ช้าๆ แบบ circular = toilet bowl จริง",
        "bf_version_note": "",
        "adjustments": [
            {"param": "i_roll / i_pitch", "direction": "เพิ่ม", "amount": "5",
             "delta": 5, "axis": "both",
             "reason": "I สูงขึ้นช่วย reject wind และ hold attitude"},
            {"param": "p_yaw", "direction": "ลดเล็กน้อย", "amount": "3",
             "delta": -3, "axis": "yaw",
             "reason": "ลด yaw response ที่ไวเกินไป"},
        ],
        "cli_template": [
            "# Fix: Toilet bowl",
            "set i_roll  = {i_roll+5}",
            "set i_pitch = {i_pitch+5}",
            "set p_yaw   = {p_yaw-3}",
            "# ถ้ามี GPS: ทำ compass calibration ใหม่",
            "save",
        ],
        "tips": [
            "ทดสอบในสภาพอากาศนิ่งก่อนเพื่อแยกว่าเป็น wind หรือ PID",
            "ตรวจสอบว่า IMU orientation ตั้งค่าถูกต้องใน FC",
            "Motor mismatch ทำให้ toilet bowl ได้ — ตรวจ ESC calibration",
        ],
    },

    "jello_footage": {
        "label": "ภาพ Jello / สั่น Ripple บน Video",
        "label_en": "Jello effect on footage",
        "category": "video",
        "severity": "medium",
        "confidence": 70,
        "icon": "📹",
        "color": "#22d3ee",
        "axes_affected": ["all"],
        "quick_win": "Balance ใบพัด + เพิ่ม damper pad ใต้กล้อง",
        "related": ["high_freq_oscillation", "motor_hot"],
        "diagnosis": (
            "Jello effect บน video footage เกิดจาก vibration ที่ความถี่ใกล้เคียง rolling shutter rate "
            "สาเหตุหลัก: ใบพัด imbalance, frame resonance หรือ motor bearing เสีย "
            "PID ที่ไม่ดีทำให้ oscillation ส่งไปยัง frame มากขึ้น"
        ),
        "primary_cause": "ใบพัด imbalance / motor bearing / frame resonance",
        "blackbox_hint": "ดู gyro spectrum — ถ้ามี spike ที่ความถี่เดิมตลอด = resonance จริง",
        "bf_version_note": "",
        "adjustments": [
            {"param": "gyro_lpf1_hz", "direction": "ลด", "amount": "20–30 Hz",
             "delta": -20, "axis": "filter",
             "reason": "Filter gyro มากขึ้นลด vibration ที่ส่งไป FC"},
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "2–3",
             "delta": -2, "axis": "both",
             "reason": "D ต่ำลงลด motor buzz frequency"},
        ],
        "cli_template": [
            "# Fix: Jello footage",
            "set gyro_lpf1_static_hz = {gyro_lpf1-20}",
            "set d_roll  = {d_roll-2}",
            "set d_pitch = {d_pitch-2}",
            "# Hardware fix (ดีกว่า PID fix):",
            "# 1. Balance ใบพัดทุกใบ",
            "# 2. ติด damper pad ใต้กล้อง",
            "save",
        ],
        "tips": [
            "การแก้ด้วย PID/filter เป็น workaround — แก้ hardware ดีกว่าเสมอ",
            "Balance ใบพัดทุกใบ ใช้เครื่อง balancer หรือ tape ชิ้นเล็กๆ",
            "ติด damper pad (anti-vibration mount) ใต้กล้อง",
            "ตรวจ motor bearing: หมุน motor ด้วยมือ — ควร smooth ไม่สะดุด",
        ],
    },

    "esc_desync": {
        "label": "ESC Desync / มอเตอร์หยุดกลางอากาศ",
        "label_en": "ESC desync / motor stutter",
        "category": "esc",
        "severity": "critical",
        "confidence": 88,
        "icon": "⚠️",
        "color": "#f87171",
        "axes_affected": ["all"],
        "quick_win": "เปลี่ยนเป็น DSHOT600 + เปิด Bidir",
        "related": ["motor_hot", "not_arming"],
        "diagnosis": (
            "ESC desync เกิดเมื่อ ESC 'หลง' timing ของมอเตอร์ แล้วหยุดหมุนทันที "
            "อาการ: มอเตอร์ 1 ตัวหยุดกะทันหัน โดรนหมุนหรือตก "
            "สาเหตุ: Demag compensation ไม่พอ, protocol ไม่เหมาะ"
        ),
        "primary_cause": "ESC demag / protocol ผิด / KV สูงเกิน / throttle ต่ำ",
        "blackbox_hint": "ดู motor output — จะเห็นมอเตอร์ตัวหนึ่งพุ่งไป 0 แล้วกลับมาทันที",
        "bf_version_note": "DSHOT600 + Bidir DShot คือการแก้ที่ดีที่สุด",
        "adjustments": [
            {"param": "motor_pwm_protocol", "direction": "เปลี่ยน", "amount": "DSHOT600",
             "delta": 0, "axis": "system",
             "reason": "Digital protocol ไม่มีปัญหา desync แบบ analog"},
            {"param": "dshot_bidir", "direction": "เปิด", "amount": "ON",
             "delta": 0, "axis": "system",
             "reason": "Bidirectional DShot + RPM filter ลด desync ได้ดีที่สุด"},
            {"param": "motor_poles", "direction": "ตรวจสอบ", "amount": "14 (มาตรฐาน)",
             "delta": 0, "axis": "system",
             "reason": "Pole count ผิดทำให้ RPM ผิด → desync ง่ายขึ้น"},
        ],
        "cli_template": [
            "# Fix: ESC Desync",
            "set motor_pwm_protocol = DSHOT600",
            "set dshot_bidir        = ON",
            "set motor_poles        = 14",
            "# ESC Firmware: อัปเป็น BLHeli_32 หรือ AM32 ล่าสุด",
            "# ใน BLHeli_32: เพิ่ม Demag Compensation = High",
            "save",
        ],
        "tips": [
            "DSHOT600 + Bidir แก้ desync ได้ดีที่สุด — ทำก่อนอย่างอื่น",
            "ตรวจ Blackbox: มอเตอร์ที่ desync จะเห็น motor output กระโดดผิดปกติ",
            "KV สูง (2800+) บน 4S อาจต้องลด RPM limit ใน ESC firmware",
            "ถ้า desync เฉพาะ motor ตัวเดียว → เปลี่ยน ESC หรือมอเตอร์ตัวนั้น",
        ],
    },

    "bounce_recovery": {
        "label": "โดรน Bounce กลับหลัง Punch-out",
        "label_en": "Bounce back after throttle punch",
        "category": "oscillation",
        "severity": "medium",
        "confidence": 83,
        "icon": "🏀",
        "color": "#fb923c",
        "axes_affected": ["pitch", "roll"],
        "quick_win": "เปิด anti_gravity_mode = SMOOTH",
        "related": ["propwash", "propwash_snap"],
        "diagnosis": (
            "โดรน 'กระเด้ง' ขึ้นหรือ nose dip หลัง punch-out "
            "เกิดจาก I-term wind-up ระหว่าง throttle surge "
            "หรือ anti_gravity gain สูงเกินจนทำให้ I พุ่งสูงแล้วปล่อยทันที"
        ),
        "primary_cause": "I wind-up ระหว่าง throttle surge / anti_gravity สูง",
        "blackbox_hint": "ดู I-term trace ระหว่าง punch-out — ถ้าพุ่งแล้วหล่น = wind-up",
        "bf_version_note": "BF4.4: anti_gravity_mode = SMOOTH ช่วยได้มาก",
        "adjustments": [
            {"param": "anti_gravity_mode", "direction": "ตั้ง", "amount": "SMOOTH",
             "delta": 0, "axis": "system",
             "reason": "SMOOTH mode เพิ่ม I แบบค่อยเป็นค่อยไป ไม่ spike"},
            {"param": "anti_gravity_gain", "direction": "ลด", "amount": "3–5",
             "delta": -4, "axis": "filter",
             "reason": "AG สูงเกินทำให้ I พุ่งแล้ว bounce กลับ"},
            {"param": "iterm_relax_cutoff", "direction": "ลด", "amount": "10–12",
             "delta": 0, "axis": "system",
             "reason": "Relax I มากขึ้นตอน rapid throttle change"},
        ],
        "cli_template": [
            "# Fix: Bounce after punch-out",
            "set anti_gravity_mode   = SMOOTH",
            "set anti_gravity_gain   = {ag-4}",
            "set anti_gravity_cutoff = 25",
            "set iterm_relax_cutoff  = 12",
            "save",
        ],
        "tips": [
            "anti_gravity_mode = SMOOTH คือการแก้ที่ง่ายที่สุด",
            "ลด AG gain ทีละ 2 จนหาย bounce",
            "ถ้ายัง bounce อยู่หลัง smooth mode = I ต้องลดลง",
        ],
    },

    "tpa_issues": {
        "label": "โดรน Twitchy ที่ Full Throttle / TPA ผิด",
        "label_en": "Twitchy at high throttle / TPA issue",
        "category": "response",
        "severity": "medium",
        "confidence": 80,
        "icon": "⚡",
        "color": "#f59e0b",
        "axes_affected": ["roll", "pitch"],
        "quick_win": "เพิ่ม TPA rate = 65, breakpoint = 1300",
        "related": ["high_freq_oscillation", "oscillation_after_flip"],
        "diagnosis": (
            "โดรน twitchy หรือ oscillate ที่ throttle สูง แต่ hover ปกติ "
            "เกิดจาก airflow เพิ่มขึ้นที่ full throttle ทำให้ FC ตอบสนองต่อ P มากเกิน "
            "TPA (Throttle PID Attenuation) ลด P อัตโนมัติที่ throttle สูง"
        ),
        "primary_cause": "P สูงเกินที่ full throttle / TPA ไม่ได้ตั้ง",
        "blackbox_hint": "ดู P-term trace ตอน full throttle — ถ้า oscillate เฉพาะ throttle สูง = TPA",
        "bf_version_note": "BF4.4: tpa_mode = PD ดีกว่า P-only",
        "adjustments": [
            {"param": "tpa_rate", "direction": "เพิ่ม", "amount": "65–75",
             "delta": 0, "axis": "system",
             "reason": "TPA ลด P 65% ที่ full throttle ลด oscillation"},
            {"param": "tpa_breakpoint", "direction": "ตั้ง", "amount": "1300",
             "delta": 0, "axis": "system",
             "reason": "เริ่ม attenuation ที่ 30% throttle"},
            {"param": "tpa_mode", "direction": "ตั้ง", "amount": "PD",
             "delta": 0, "axis": "system",
             "reason": "Attenuate ทั้ง P และ D ที่ throttle สูง"},
        ],
        "cli_template": [
            "# Fix: Twitchy at full throttle",
            "set tpa_rate       = 65",
            "set tpa_breakpoint = 1300",
            "set tpa_mode       = PD",
            "save",
        ],
        "tips": [
            "TPA เป็น set-and-forget — ตั้งค่าแล้วไม่ต้องปรับบ่อย",
            "ถ้า hover ปกติแต่ full throttle twitchy = TPA เป็นสาเหตุแน่นอน",
            "tpa_rate = 65-75 เหมาะกับ freestyle ส่วนใหญ่",
            "ลอง tpa_mode = PD ก่อน — attenuate ทั้ง P และ D ดีกว่า P อย่างเดียว",
        ],
    },

    "yaw_authority": {
        "label": "Yaw ตอบสนองช้า / Yaw authority ต่ำ",
        "label_en": "Poor yaw authority / slow yaw",
        "category": "yaw",
        "severity": "low",
        "confidence": 78,
        "icon": "↔️",
        "color": "#a78bfa",
        "axes_affected": ["yaw"],
        "quick_win": "เพิ่ม p_yaw +5 และ feedforward_yaw +10",
        "related": ["slow_response"],
        "diagnosis": (
            "Yaw ตอบสนองช้าหรือ 'mushy' ไม่ทันใจ "
            "มักเกิดจาก P_yaw ต่ำ, feedforward_yaw ต่ำ "
            "หรือ motor mismatch ที่ทำให้ yaw torque ไม่สมดุล"
        ),
        "primary_cause": "P_yaw ต่ำ / feedforward_yaw ต่ำ / motor mismatch",
        "blackbox_hint": "ดู yaw setpoint vs gyro — ถ้า gyro ตามช้า = เพิ่ม P หรือ FF yaw",
        "bf_version_note": "",
        "adjustments": [
            {"param": "p_yaw", "direction": "เพิ่ม", "amount": "3–8",
             "delta": 5, "axis": "yaw",
             "reason": "P_yaw สูงขึ้นทำให้ yaw ตอบสนองเร็ว"},
            {"param": "feedforward_yaw", "direction": "เพิ่ม", "amount": "10–20",
             "delta": 10, "axis": "yaw",
             "reason": "FF yaw ตอบสนองต่อ stick velocity โดยตรง"},
            {"param": "i_yaw", "direction": "ตรวจสอบ", "amount": "75–90",
             "delta": 0, "axis": "yaw",
             "reason": "I_yaw ต้องพอสำหรับ hold heading"},
        ],
        "cli_template": [
            "# Fix: Poor yaw authority",
            "set p_yaw           = {p_yaw+5}",
            "set feedforward_yaw = {ff_yaw+10}",
            "save",
        ],
        "tips": [
            "Yaw P และ FF สูงขึ้นได้ไม่เท่า roll/pitch เพราะ yaw axis มี inertia น้อยกว่า",
            "ถ้าเพิ่ม P แล้ว yaw oscillate = หยุดและลด P กลับ",
            "Motor ที่ถอดเกลียวหรือ bearing เสีย ลด yaw authority ด้วย",
        ],
    },

    "not_arming": {
        "label": "โดรนไม่ ARM / ARM ไม่ได้",
        "label_en": "Drone won't arm",
        "category": "setup",
        "severity": "critical",
        "confidence": 95,
        "icon": "🔐",
        "color": "#f87171",
        "axes_affected": [],
        "quick_win": "พิมพ์ 'status' ใน CLI ดู ARMING_DISABLED flags",
        "related": ["esc_desync", "turtle_mode_fail"],
        "diagnosis": (
            "โดรนปฏิเสธการ ARM มักเกิดจาก: "
            "Throttle ไม่ตำลงสุด, Stick endpoint ไม่ถึง, "
            "Accelerometer ไม่ calibrate, Pre-arm check fail "
            "บน Betaflight 4.3+ มี ARMING_DISABLED flags ที่ต้องตรวจ"
        ),
        "primary_cause": "Pre-arm check fail / stick ไม่ calibrate / mode ผิด",
        "blackbox_hint": "ดู 'status' ใน CLI — จะเห็น ARMING_DISABLED reasons ทั้งหมด",
        "bf_version_note": "BF4.4: พิมพ์ 'status' แสดง flags ชัดเจนมาก",
        "adjustments": [
            {"param": "status (CLI check)", "direction": "ตรวจสอบ", "amount": "พิมพ์ status",
             "delta": 0, "axis": "system",
             "reason": "แสดง ARMING_DISABLED reasons ทั้งหมด"},
            {"param": "small_angle", "direction": "ตรวจสอบ", "amount": "ควร 25–180",
             "delta": 0, "axis": "system",
             "reason": "โดรนเอียงเกิน small_angle จะ ARM ไม่ได้"},
            {"param": "min_check", "direction": "ตรวจสอบ", "amount": "1050",
             "delta": 0, "axis": "system",
             "reason": "ถ้า min_check ต่ำกว่า stick endpoint จะ ARM ไม่ได้"},
        ],
        "cli_template": [
            "# Diagnose: ทำไมไม่ ARM",
            "status                    # ดู ARMING_DISABLED flags",
            "set small_angle = 25      # อนุญาต tilt มากขึ้น",
            "set min_check   = 1050",
            "set max_check   = 1900",
            "# Throttle: ตรวจ CH3 ที่ stick ลงสุด = ~1000",
            "save",
        ],
        "tips": [
            "ใน CLI พิมพ์ 'status' จะเห็น ARMING_DISABLED พร้อม reason ชัดเจน",
            "สาเหตุที่พบบ่อย: THROTTLE, ANGLE, NOPREARM, MSP, FAILSAFE",
            "ตรวจ receiver binding ก่อน — ถ้าไม่รับสัญญาณ ARM ไม่ได้เลย",
            "BF4.4+: เปิด prearm mode ใน modes ก่อน ARM จะสะดวกกว่า",
        ],
    },

    "turtle_mode_fail": {
        "label": "Turtle Mode ไม่ทำงาน",
        "label_en": "Flip over after crash not working",
        "category": "setup",
        "severity": "medium",
        "confidence": 90,
        "icon": "🐢",
        "color": "#22d3ee",
        "axes_affected": [],
        "quick_win": "ตรวจ protocol เป็น DSHOT300+ และ assign switch",
        "related": ["not_arming", "esc_desync"],
        "diagnosis": (
            "Turtle mode ไม่ทำงานหรือทำงานไม่สมบูรณ์ "
            "สาเหตุ: ไม่ได้ assign switch ใน modes, protocol ไม่ใช่ DSHOT, "
            "ESC ไม่รองรับ turtle mode"
        ),
        "primary_cause": "Protocol ไม่ใช่ DSHOT / Mode ไม่ assign / ESC ไม่รองรับ",
        "blackbox_hint": "",
        "bf_version_note": "Turtle mode ต้องการ DSHOT300+ เสมอ — ไม่มี exception",
        "adjustments": [
            {"param": "motor_pwm_protocol", "direction": "เปลี่ยน", "amount": "DSHOT600",
             "delta": 0, "axis": "system",
             "reason": "Turtle mode ต้องการ DSHOT — Oneshot/Multishot ไม่รองรับ"},
            {"param": "flip_over_after_crash", "direction": "assign", "amount": "กำหนด switch",
             "delta": 0, "axis": "system",
             "reason": "ต้องมี mode switch ถึงจะใช้ได้"},
        ],
        "cli_template": [
            "# Fix: Turtle Mode",
            "set motor_pwm_protocol = DSHOT600",
            "# BF Configurator → Modes → Flip Over After Crash",
            "# กำหนด Channel ที่ต้องการ (เช่น AUX3)",
            "save",
        ],
        "tips": [
            "Turtle mode ต้องใช้ DSHOT300/600 เสมอ — ตรวจก่อนอย่างอื่น",
            "ถ้า motor บางตัวหมุนผิดทางตอน turtle → ตรวจ motor direction",
            "ทดสอบ turtle บนพื้นก่อนใช้จริง",
        ],
    },

    "video_breakup": {
        "label": "ภาพ FPV แตก / สัญญาณ VTX หาย",
        "label_en": "FPV video breakup",
        "category": "vtx",
        "severity": "high",
        "confidence": 72,
        "icon": "📡",
        "color": "#22d3ee",
        "axes_affected": [],
        "quick_win": "ใส่ capacitor 470µF บน power VTX",
        "related": [],
        "diagnosis": (
            "ภาพ FPV แตกหรือหายไประหว่างบิน มักเกิดจาก: "
            "VTX ร้อนเกิน, แรงดันไฟตก (voltage sag) บน VTX, "
            "antenna ไม่ดีหรือหัก, channel ชน"
        ),
        "primary_cause": "VTX ร้อน / แรงดันตก / antenna เสีย / channel ชน",
        "blackbox_hint": "ดู voltage trace — ถ้า sag ตอนเดียวกับภาพแตก = power issue",
        "bf_version_note": "",
        "adjustments": [
            {"param": "vtx_power", "direction": "เพิ่ม", "amount": "200mW+ outdoor",
             "delta": 0, "axis": "system",
             "reason": "กำลังส่งต่ำทำให้ภาพแตกเมื่อระยะห่างขึ้น"},
            {"param": "vtx_channel", "direction": "เปลี่ยน", "amount": "ใช้ channel ว่าง",
             "delta": 0, "axis": "system",
             "reason": "Channel ชนทำให้ภาพแทรกกัน"},
        ],
        "cli_template": [
            "# VTX Settings (SmartAudio/IRC Tramp)",
            "set vtx_power   = 3    # level 3 ~ 200mW",
            "set vtx_channel = 6    # Raceband CH6",
            "set vtx_band    = 5    # Raceband",
            "# Hardware: capacitor 470-1000µF บน power VTX",
            "save",
        ],
        "tips": [
            "ใส่ capacitor 470-1000µF บน power supply VTX — แก้ voltage sag",
            "VTX ที่ไม่มี airflow จะ throttle down กำลังส่งเองเมื่อร้อน",
            "Antenna ที่บิดงอลดพิสัยมากกว่า 50%",
            "SmartAudio: ใช้ OSD menu เปลี่ยน channel โดยไม่ต้อง land",
        ],
    },
}


# ─── Category metadata ─────────────────────────────────────
CATEGORIES = {
    "oscillation": {"label": "การสั่น (Oscillation)", "icon": "🌀", "color": "#f87171"},
    "propwash":    {"label": "Propwash",               "icon": "💨", "color": "#fb923c"},
    "response":    {"label": "การตอบสนอง (Response)", "icon": "⚡", "color": "#f59e0b"},
    "yaw":         {"label": "แกน Yaw",               "icon": "↔️", "color": "#a78bfa"},
    "thermal":     {"label": "ความร้อน (Thermal)",     "icon": "🌡️", "color": "#f87171"},
    "pid_advanced":{"label": "PID ขั้นสูง",           "icon": "🎛️", "color": "#4a9eff"},
    "esc":         {"label": "ESC / Motor",            "icon": "⚡", "color": "#f87171"},
    "video":       {"label": "Video / Jello",          "icon": "📹", "color": "#22d3ee"},
    "vtx":         {"label": "VTX / Signal",           "icon": "📡", "color": "#22d3ee"},
    "setup":       {"label": "การตั้งค่าพื้นฐาน",     "icon": "⚙️", "color": "#8aabb8"},
    "gps_or_pid":  {"label": "GPS / Position",         "icon": "🛸", "color": "#a78bfa"},
}


def get_all_symptoms() -> list:
    """Return list of {id, label, label_en, category, severity, icon, color} for UI."""
    return [
        {
            "id":       k,
            "label":    v["label"],
            "label_en": v.get("label_en", ""),
            "category": v["category"],
            "severity": v.get("severity", "medium"),
            "confidence": v.get("confidence", 75),
            "icon":     v.get("icon", "🔧"),
            "color":    v.get("color", "#8aabb8"),
            "quick_win": v.get("quick_win", ""),
            "related":  v.get("related", []),
        }
        for k, v in SYMPTOMS.items()
    ]


def get_advice(symptom_id: str) -> dict:
    """Return full advice for a given symptom ID."""
    if symptom_id not in SYMPTOMS:
        return {"error": f"ไม่พบ symptom: {symptom_id}"}
    s = SYMPTOMS[symptom_id]
    return {
        "id":             symptom_id,
        "label":          s["label"],
        "label_en":       s.get("label_en", ""),
        "category":       s["category"],
        "severity":       s.get("severity", "medium"),
        "confidence":     s.get("confidence", 75),
        "icon":           s.get("icon", "🔧"),
        "color":          s.get("color", "#8aabb8"),
        "axes_affected":  s.get("axes_affected", []),
        "quick_win":      s.get("quick_win", ""),
        "related":        s.get("related", []),
        "diagnosis":      s["diagnosis"],
        "primary_cause":  s["primary_cause"],
        "blackbox_hint":  s.get("blackbox_hint", ""),
        "bf_version_note":s.get("bf_version_note", ""),
        "adjustments":    s["adjustments"],
        "cli_template":   s["cli_template"],
        "tips":           s["tips"],
    }


def get_categories() -> dict:
    return CATEGORIES
