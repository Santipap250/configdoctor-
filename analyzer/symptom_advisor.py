# analyzer/symptom_advisor.py — OBIXConfig Doctor
"""
PID Symptom-to-Fix Advisor for Betaflight FPV Drones.

Maps common flying symptoms to specific PID/filter adjustments with
ready-to-paste CLI commands. Based on community knowledge from
Joshua Bardwell, Betaflight tuning guides, and FPV forums.

Each symptom has:
  - diagnosis: root cause explanation (Thai)
  - axes:      which axes are affected
  - adjustments: list of {param, direction, reason}
  - cli_template: suggested CLI commands (uses placeholder values)
  - tips: additional flying/setup tips
"""

from __future__ import annotations
from typing import Dict, Any, List

# ─────────────────────────────────────────────────────────────────────────
# SYMPTOM DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────
SYMPTOMS: Dict[str, Dict[str, Any]] = {

    "oscillation_after_flip": {
        "label": "สั่นหลัง flip / roll (Post-maneuver oscillation)",
        "category": "oscillation",
        "diagnosis": (
            "อาการสั่นหลัง flip หรือ roll มักเกิดจาก D-term สูงเกินไป "
            "หรือ D-term filter ต่ำเกินไปจนทำให้ noise กระตุ้น motors ต่อเนื่อง "
            "อาจเกิดจาก P สูงเกินไปด้วยถ้าสั่นทันทีในระหว่างทำ maneuver"
        ),
        "primary_cause": "D-term สูง / D-term filter ต่ำ",
        "adjustments": [
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "2–3 ครั้งละ 5%",
             "reason": "ลด D-term ลดการตอบสนองต่อ noise หลัง maneuver"},
            {"param": "dterm_lpf1_hz",    "direction": "ลด", "amount": "ลด 10–20Hz",
             "reason": "filter D-term มากขึ้น ลด noise ที่ amplify"},
            {"param": "p_roll / p_pitch", "direction": "ลดเล็กน้อย", "amount": "ลด 2–3 ถ้า P สูง",
             "reason": "ถ้า P สูงเกินก็ส่งเสริม oscillation"},
        ],
        "cli_template": [
            "# แก้: สั่นหลัง flip",
            "set d_roll = {current_d_roll - 3}     # ลด D roll ลง 3",
            "set d_pitch = {current_d_pitch - 3}   # ลด D pitch ลง 3",
            "set dterm_lpf1_hz = {current - 15}    # เพิ่ม filter D-term",
            "save",
        ],
        "tips": [
            "ทดสอบโดยลด D ทีละ 3 แล้วบินซ้ำ",
            "ถ้าลด D แล้ว propwash เพิ่มขึ้น = D ยังต้องการ ให้ปรับ filter แทน",
            "ใช้ Blackbox ดูว่า gyro noise กระโดดสูงตอนไหน",
        ],
    },

    "propwash": {
        "label": "Propwash (สั่นตอน throttle drop)",
        "category": "propwash",
        "diagnosis": (
            "Propwash เกิดตอนลด throttle กะทันหันแล้วเพิ่มอีกครั้ง "
            "เป็น chaos ของ airflow ที่ propeller ตัวเองสร้าง "
            "D-term ต่ำ, I-term ต่ำ หรือ P ต่ำ ล้วนทำให้แย่ลง "
            "RPM filter ไม่ดีก็ทำให้ motors ไม่ response smoothly"
        ),
        "primary_cause": "D-term ต่ำเกินไป, RPM filter ไม่ดี",
        "adjustments": [
            {"param": "d_roll / d_pitch", "direction": "เพิ่ม", "amount": "เพิ่ม 3–5",
             "reason": "D-term ช่วย damp propwash ได้ดี"},
            {"param": "i_roll / i_pitch", "direction": "ตรวจสอบ", "amount": "ควรอยู่ที่ 85–95",
             "reason": "I-term ต่ำทำให้ไม่ lock-in position ระหว่าง throttle change"},
            {"param": "anti_gravity",     "direction": "เพิ่ม", "amount": "ลอง 7–10",
             "reason": "Anti-gravity เพิ่ม I ชั่วคราวตอน throttle change"},
            {"param": "rpm_filter",       "direction": "เปิด",  "amount": "SET ON",
             "reason": "RPM filter ลด motor noise ทำให้ motors smooth กว่า"},
        ],
        "cli_template": [
            "# แก้: Propwash",
            "set d_roll = {d_roll + 4}",
            "set d_pitch = {d_pitch + 4}",
            "set anti_gravity_gain = 8",
            "set iterm_relax = RPH          # เปิด I-term relax ลด I buildup ระหว่าง maneuver",
            "set iterm_relax_type = SETPOINT",
            "save",
        ],
        "tips": [
            "Propwash แก้ยาก — อาจต้องทดสอบหลายรอบ",
            "ลองเพิ่ม D ทีละ 2 จนเริ่มได้ยินเสียงบึ้ง แล้วลดลงมา 2",
            "RPM filter สำคัญมากสำหรับ propwash — ตรวจสอบว่าเปิดอยู่",
            "ใบพัดใหม่ balance ดีช่วยได้มาก",
        ],
    },

    "bounce_back": {
        "label": "Bounce-back / Overshoot หลัง maneuver",
        "category": "oscillation",
        "diagnosis": (
            "โดรนไป 'เกิน' เป้าหมายแล้วกระเด้งกลับ (bounce) หลัง roll/flip "
            "สาเหตุหลักคือ P สูงเกินไป หรือ D ต่ำเกินไปไม่พอจะ damp overshoot "
            "อาจเกิดจาก feedforward สูงด้วยถ้าเกิดตอนเริ่ม stick input"
        ),
        "primary_cause": "P สูงเกิน / D ต่ำ",
        "adjustments": [
            {"param": "p_roll / p_pitch", "direction": "ลด", "amount": "ลด 3–5",
             "reason": "P ต่ำลงลด tendency ที่จะ overshoot"},
            {"param": "d_roll / d_pitch", "direction": "เพิ่ม", "amount": "เพิ่ม 2–4",
             "reason": "D ช่วย damp overshoot โดยตรง"},
            {"param": "feedforward",      "direction": "ลด", "amount": "ลด 10–15 ถ้า >30",
             "reason": "Feedforward สูงทำให้เริ่ม maneuver แรงเกินไป"},
        ],
        "cli_template": [
            "# แก้: Bounce-back",
            "set p_roll = {p_roll - 4}",
            "set p_pitch = {p_pitch - 4}",
            "set d_roll = {d_roll + 3}",
            "set d_pitch = {d_pitch + 3}",
            "set feedforward_roll = 25    # ลด feedforward ถ้าสูงกว่า 30",
            "save",
        ],
        "tips": [
            "ถ้าแก้ P แล้ว drone ไม่ 'crisp' ให้เพิ่ม feedforward แทน P",
            "Bounce-back ในอากาศลม = wind reject ไม่พอ ให้เพิ่ม I",
        ],
    },

    "yaw_spin": {
        "label": "Yaw spin / หมุน yaw เองหลัง flip",
        "category": "yaw",
        "diagnosis": (
            "โดรนหมุนไม่หยุดหรือ drift ใน yaw axis หลัง flip/roll "
            "สาเหตุหลัก: yaw P สูง, yaw I ต่ำเกิน หรือ motor timing ไม่ match "
            "อาจเกิดจาก ESC calibration ไม่ตรงกัน"
        ),
        "primary_cause": "Yaw P สูง / I-term ต่ำ / motor imbalance",
        "adjustments": [
            {"param": "p_yaw",  "direction": "ลด", "amount": "ลด 5–10",
             "reason": "Yaw P มักต้องต่ำกว่า Roll/Pitch เสมอ"},
            {"param": "i_yaw",  "direction": "เพิ่ม", "amount": "เพิ่ม 5–10",
             "reason": "I-term ช่วย hold yaw heading"},
            {"param": "yaw_stop_time", "direction": "ลด", "amount": "ลอง 0.02",
             "reason": "ปรับ yaw stop speed"},
        ],
        "cli_template": [
            "# แก้: Yaw spin",
            "set p_yaw = {p_yaw - 8}",
            "set i_yaw = {i_yaw + 8}",
            "# ตรวจสอบ motor direction และ ESC calibration ด้วย",
            "save",
        ],
        "tips": [
            "ตรวจสอบ motor screws ให้แน่น — loose motor ทำให้ yaw drift",
            "ตรวจ propeller ทั้ง 4 ใบว่าใส่ถูก direction",
            "ESC calibration: ทำ all-at-once calibration ใหม่",
        ],
    },

    "toilet_bowl": {
        "label": "Toilet bowl / วนเป็นวงกลมตอน hover",
        "category": "gps_or_pid",
        "diagnosis": (
            "อาการวนเป็นวงกลมขณะ hover มักเกิดจาก I-term ต่ำเกินไปทำให้ไม่ hold position "
            "หรือ yaw drift ร่วมกับ P ที่ไม่สมดุลระหว่าง roll และ pitch "
            "อาจเกิดจาก compass (magnetometer) miscalibration ด้วยถ้ามี GPS"
        ),
        "primary_cause": "I-term ต่ำ / yaw drift / compass miscalibration",
        "adjustments": [
            {"param": "i_roll / i_pitch", "direction": "เพิ่ม", "amount": "เพิ่ม 5",
             "reason": "I สูงขึ้นช่วย reject wind และ hold attitude"},
            {"param": "p_yaw",           "direction": "ลดเล็กน้อย", "amount": "ลด 3",
             "reason": "ลด yaw response ที่ไว"},
        ],
        "cli_template": [
            "# แก้: Toilet bowl",
            "set i_roll = {i_roll + 5}",
            "set i_pitch = {i_pitch + 5}",
            "set p_yaw = {p_yaw - 3}",
            "# ถ้ามี GPS: ทำ compass calibration ใหม่",
            "save",
        ],
        "tips": [
            "ทดสอบในสภาพอากาศนิ่งก่อนเพื่อแยกว่าเป็น wind หรือ PID",
            "ตรวจสอบว่า IMU orientation ตั้งค่าถูกต้องใน FC",
        ],
    },

    "slow_response": {
        "label": "ตอบสนองช้า / drone รู้สึกเฉื่อย",
        "category": "response",
        "diagnosis": (
            "โดรนตอบสนองต่อ stick input ช้าหรือรู้สึก 'mushy' "
            "มักเกิดจาก P ต่ำเกิน, feedforward ต่ำ หรือ filter aggressive เกินไป "
            "อาจเกิดจาก rates ต่ำด้วยถ้าความเร็ว rotation ไม่เพียงพอ"
        ),
        "primary_cause": "P ต่ำ / feedforward ต่ำ / filter aggressive",
        "adjustments": [
            {"param": "p_roll / p_pitch", "direction": "เพิ่ม", "amount": "เพิ่ม 3–5",
             "reason": "P สูงขึ้นทำให้ตอบสนองเร็ว"},
            {"param": "feedforward",      "direction": "เพิ่ม", "amount": "เพิ่ม 10–20",
             "reason": "Feedforward ตอบสนองต่อ stick velocity โดยตรง"},
            {"param": "gyro_lpf1_hz",     "direction": "เพิ่ม", "amount": "เพิ่ม 20–30Hz",
             "reason": "Filter น้อยลง = latency ต่ำลง = response เร็วขึ้น"},
        ],
        "cli_template": [
            "# แก้: ตอบสนองช้า",
            "set p_roll = {p_roll + 4}",
            "set p_pitch = {p_pitch + 4}",
            "set feedforward_roll = {ff + 15}",
            "set feedforward_pitch = {ff + 15}",
            "set gyro_lpf1_hz = {lpf + 20}    # เพิ่มได้ถ้า noise ไม่มาก",
            "save",
        ],
        "tips": [
            "ตรวจสอบ rates ก่อน — ถ้า rates ต่ำ response จะช้าโดยธรรมชาติ",
            "เพิ่ม P ทีละ 3 จนเริ่มสั่น แล้วลดลงมา 5",
        ],
    },

    "motor_hot": {
        "label": "มอเตอร์ร้อนหลังบิน",
        "category": "thermal",
        "diagnosis": (
            "มอเตอร์ร้อนเกินปกติหลังบิน อาจเกิดจาก D-term สูงมากส่งกระแสสูงต่อเนื่อง "
            "ใบพัดหนักเกินสำหรับมอเตอร์ KV นั้น หรือ filter ไม่พอทำให้ motor ทำงานหนัก "
            "รวมถึง ESC desync ที่ทำให้มอเตอร์ stutter"
        ),
        "primary_cause": "D-term สูง / ใบพัดหนัก / filter ไม่ดี",
        "adjustments": [
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "ลด 3–5",
             "reason": "D สูงส่งกระแสสูงต่อเนื่องทำให้ motor ร้อน"},
            {"param": "dterm_lpf1_hz",    "direction": "ลด", "amount": "ลด 15–20Hz",
             "reason": "Filter D-term มากขึ้นลด high-freq noise ที่ drive motor"},
            {"param": "rpm_filter",       "direction": "เปิด", "amount": "SET ON",
             "reason": "RPM filter ลด motor noise มากที่สุด"},
            {"param": "motor_pwm_protocol", "direction": "ตรวจสอบ", "amount": "ใช้ DSHOT600",
             "reason": "Digital protocol ลด ESC desync"},
        ],
        "cli_template": [
            "# แก้: มอเตอร์ร้อน",
            "set d_roll = {d_roll - 4}",
            "set d_pitch = {d_pitch - 4}",
            "set dterm_lpf1_hz = {lpf - 15}",
            "set motor_pwm_protocol = DSHOT600",
            "# ตรวจสอบ: ใบพัดสมดุล, motor screws, airflow ไม่อุดตัน",
            "save",
        ],
        "tips": [
            "วัดอุณหภูมิมอเตอร์หลังบิน 2 นาที — ควรต่ำกว่า 60°C",
            "ตรวจสอบว่า motor ไม่มีขยะหรือ grass อุดอยู่",
            "ลองใบพัดขนาดเล็กลงหรือ pitch ต่ำลง",
            "ถ้า 1 มอเตอร์ร้อนกว่าอีก 3 ตัว = bearing ใกล้หมดหรือ winding ไหม้",
        ],
    },

    "jello_footage": {
        "label": "ภาพ Jello / ภาพสั่น ripple บน footage",
        "category": "video",
        "diagnosis": (
            "Jello effect บน video footage เกิดจาก vibration ที่ความถี่ใกล้เคียง rolling shutter rate ของกล้อง "
            "สาเหตุหลัก: ใบพัด imbalance, frame resonance หรือ motor bearing เสีย "
            "PID ที่ไม่ดีทำให้ oscillation ส่งไปยัง frame มากขึ้น"
        ),
        "primary_cause": "ใบพัด imbalance / motor bearing / frame resonance",
        "adjustments": [
            {"param": "gyro_lpf1_hz", "direction": "ลด", "amount": "ลด 20–30Hz",
             "reason": "Filter gyro มากขึ้นลด vibration ที่ส่งไป FC"},
            {"param": "d_roll / d_pitch", "direction": "ลด", "amount": "ลด 2–3",
             "reason": "D ต่ำลงลด motor buzz frequency"},
        ],
        "cli_template": [
            "# แก้: Jello footage",
            "set gyro_lpf1_hz = {lpf - 20}",
            "set d_roll = {d_roll - 2}",
            "set d_pitch = {d_pitch - 2}",
            "# แก้จริง: balance ใบพัด, damper pad ใต้ FC/กล้อง",
            "save",
        ],
        "tips": [
            "การแก้ด้วย PID/filter เป็น workaround เท่านั้น",
            "แก้จริง: balance ใบพัดทุกใบ ใช้เครื่อง balancer หรือ tape ชิ้นเล็กๆ",
            "ติด damper pad (anti-vibration mount) ใต้กล้อง",
            "ตรวจ motor bearing: หมุน motor ด้วยมือ — ควร smooth ไม่สะดุด",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # NEW SYMPTOMS (v2.0)
    # ─────────────────────────────────────────────────────────────────────────

    "esc_desync": {
        "label": "ESC Desync / มอเตอร์หยุดกลางอากาศ (Motor stutter/stop)",
        "category": "esc",
        "diagnosis": (
            "ESC desync เกิดเมื่อ ESC 'หลง' timing ของมอเตอร์ แล้วหยุดหมุนทันที "
            "อาการ: มอเตอร์ 1 ตัวหยุดกะทันหัน โดรนหมุนหรือตก "
            "สาเหตุ: Demag compensation ไม่พอ, throttle ต่ำเกินจนมอเตอร์หยุด, "
            "protocol ไม่เหมาะ (Oneshot/Multishot บน ESC เก่า) "
            "หรือ motor KV สูงเกินไปบนแรงดันสูง"
        ),
        "primary_cause": "ESC demag / protocol / KV สูงเกิน / throttle ต่ำเกิน",
        "adjustments": [
            {"param": "motor_pwm_protocol", "direction": "เปลี่ยน", "amount": "DSHOT300 หรือ DSHOT600",
             "reason": "Digital protocol ไม่มีปัญหา desync แบบ analog"},
            {"param": "dshot_bidir",        "direction": "เปิด",   "amount": "ON",
             "reason": "Bidirectional DShot + RPM filter ลด desync ได้ดีที่สุด"},
            {"param": "motor_poles",        "direction": "ตรวจสอบ", "amount": "ค่าถูกต้องตาม motor",
             "reason": "Pole count ผิดทำให้ RPM ผิด → desync ง่ายขึ้น"},
            {"param": "min_throttle",       "direction": "เพิ่ม",  "amount": "ลอง 1020-1030",
             "reason": "Throttle ต่ำมากทำให้มอเตอร์หยุดหมุน (เสี่ยง desync)"},
        ],
        "cli_template": [
            "# แก้: ESC Desync",
            "set motor_pwm_protocol = DSHOT600",
            "set dshot_bidir = ON",
            "set motor_poles = 14           # ตรวจสอบ spec motor ของคุณ",
            "set min_throttle = 1020",
            "# ESC Firmware: อัปเป็น BLHeli_32 หรือ AM32 ล่าสุด",
            "# ใน BLHeli_32: เพิ่ม Demag Compensation เป็น High",
            "save",
        ],
        "tips": [
            "DSHOT600 + Bidir DShot แก้ desync ได้ดีที่สุด — ทำก่อนอย่างอื่น",
            "ตรวจ Blackbox: มอเตอร์ที่ desync จะเห็น motor output กระโดดผิดปกติ",
            "KV สูง (2800+) บน 4S อาจต้องลด RPM limit ใน ESC firmware",
            "ถ้า desync เฉพาะ motor ตัวเดียว → เปลี่ยน ESC หรือมอเตอร์ตัวนั้น",
            "Motor bearing เสียทำให้ load ไม่สม่ำเสมอ → desync ได้",
        ],
    },

    "wind_rejection": {
        "label": "กันลมไม่อยู่ / โดรนล่องลอยเมื่อมีลม",
        "category": "pid_advanced",
        "diagnosis": (
            "โดรนไม่สามารถ hold position หรือ attitude ได้ดีเมื่อมีลม "
            "อาการ: โดรนถูกลมพัดไป ต้องใช้ stick ต้านตลอด, drift ขณะ hover "
            "สาเหตุหลัก: I-term ต่ำเกินไปทำให้ไม่ reject disturbance, "
            "anti_gravity ต่ำ หรือ iterm_relax ตั้งค่าผิดทำให้ I ไม่ทำงาน"
        ),
        "primary_cause": "I-term ต่ำ / iterm_relax ผิด / anti_gravity ต่ำ",
        "adjustments": [
            {"param": "i_roll / i_pitch",  "direction": "เพิ่ม", "amount": "เพิ่ม 5–10",
             "reason": "I-term สูงขึ้นช่วย reject wind disturbance"},
            {"param": "i_yaw",             "direction": "เพิ่ม", "amount": "เพิ่ม 3–5",
             "reason": "Yaw I ช่วย hold heading ในลม"},
            {"param": "iterm_relax",       "direction": "ตรวจสอบ", "amount": "ควรเป็น RPH หรือ RP",
             "reason": "iterm_relax = OFF ทำให้ I ไม่สะสมได้ดีตอนบิน"},
            {"param": "anti_gravity_gain", "direction": "เพิ่ม", "amount": "ลอง 7–12",
             "reason": "Anti-gravity เพิ่ม I ชั่วคราวตอน throttle change ต้านลม"},
        ],
        "cli_template": [
            "# แก้: กันลมไม่อยู่",
            "set i_roll = {i_roll + 8}",
            "set i_pitch = {i_pitch + 8}",
            "set i_yaw = {i_yaw + 5}",
            "set iterm_relax = RPH",
            "set iterm_relax_type = SETPOINT",
            "set iterm_relax_cutoff = 15",
            "set anti_gravity_gain = 10",
            "save",
        ],
        "tips": [
            "ทดสอบในลมจริง — เพิ่ม I ทีละ 5 จนโดรน hold ได้ดีขึ้น",
            "iterm_relax = RPH ทำให้ I ยังทำงานแต่ไม่ wind up ระหว่าง maneuver",
            "Longrange build ควร I สูงกว่า freestyle เพราะต้องต้านลมระยะไกล",
            "ตรวจสอบ CoG — ถ้า CoG ไม่ตรงกลาง โดรนจะ drift แม้ PID ดี",
        ],
    },

    "not_arming": {
        "label": "โดรนไม่ ARM / ARM แล้วมอเตอร์ไม่หมุน",
        "category": "setup",
        "diagnosis": (
            "โดรนปฏิเสธการ ARM มักเกิดจาก: "
            "Throttle ไม่ตำลงสุด, Stick endpoint ไม่ถึง, "
            "Accelerometer ไม่ calibrate, Pre-arm check fail "
            "(volt/GPS/barometer), หรือ Mode ไม่ถูก "
            "บน Betaflight 4.3+ มี ARMING_DISABLED flags ที่ต้องตรวจ"
        ),
        "primary_cause": "Pre-arm check fail / stick ไม่ calibrate / mode ผิด",
        "adjustments": [
            {"param": "arm (CLI check)",      "direction": "ตรวจสอบ", "amount": "type 'arm' ใน CLI",
             "reason": "แสดง ARMING_DISABLED reasons ทั้งหมด"},
            {"param": "min_check",            "direction": "ตรวจสอบ", "amount": "ควร 1050-1100",
             "reason": "ถ้า min_check ต่ำกว่า stick endpoint จะ ARM ไม่ได้"},
            {"param": "max_check",            "direction": "ตรวจสอบ", "amount": "ควร 1900",
             "reason": "ตรวจ endpoint ของ TX"},
            {"param": "small_angle",          "direction": "ตรวจสอบ", "amount": "set small_angle = 25",
             "reason": "โดรนเอียงเกิน small_angle จะ ARM ไม่ได้"},
        ],
        "cli_template": [
            "# ตรวจสอบ: ทำไมไม่ ARM",
            "status                          # ดู ARMING_DISABLED flags",
            "set small_angle = 25            # อนุญาต tilt มากขึ้น",
            "set min_check = 1050",
            "set max_check = 1900",
            "# Receiver: ตรวจ Channel 3 (Throttle) ที่ stick ลงสุด = 1000",
            "# Accelerometer calibration: กด 'calib_acc' ใน CLI แล้วตั้ง FC ให้นิ่งราบ",
            "save",
        ],
        "tips": [
            "ใน CLI พิมพ์ 'status' จะเห็น ARMING_DISABLED พร้อม reason",
            "สาเหตุที่พบบ่อย: THROTTLE, ANGLE, NOPREARM, MSP, FAILSAFE",
            "ตรวจ receiver binding ก่อน — ถ้าไม่รับสัญญาณ ARM ไม่ได้เลย",
            "BF4.4+: เปิด prearm mode ใน modes ก่อน ARM จะสะดวกกว่า",
            "ตรวจ motor plug: motor ที่ถอดออกทำให้ FC detect ผิดปกติ",
        ],
    },

    "turtle_mode_fail": {
        "label": "Turtle mode ไม่ทำงาน / พลิกกลับไม่ได้",
        "category": "setup",
        "diagnosis": (
            "Turtle mode (flip after crash) ไม่ทำงานหรือทำงานไม่สมบูรณ์ "
            "สาเหตุ: ไม่ได้ assign switch ใน modes, motor direction ไม่ถูก, "
            "3D mode ไม่ได้เปิด หรือ ESC ไม่รองรับ turtle mode (ต้องการ DSHOT)"
        ),
        "primary_cause": "Mode ไม่ assign / protocol ไม่ใช่ DSHOT / motor direction",
        "adjustments": [
            {"param": "motor_pwm_protocol",   "direction": "เปลี่ยน", "amount": "DSHOT300 หรือสูงกว่า",
             "reason": "Turtle mode ต้องการ DSHOT — Oneshot/Multishot ไม่รองรับ"},
            {"param": "flip_over_after_crash","direction": "assign",  "amount": "กำหนด switch ใน Modes",
             "reason": "ต้องมี mode switch ถึงจะใช้ได้"},
        ],
        "cli_template": [
            "# ตั้งค่า Turtle Mode",
            "set motor_pwm_protocol = DSHOT600   # ต้องเป็น DSHOT",
            "# ใน Betaflight Configurator → Modes → เพิ่ม Flip Over After Crash",
            "# กำหนด Channel ที่ต้องการ (เช่น AUX3)",
            "# ใน ESC Configurator: ตั้ง Bidirectional mode = enabled",
            "save",
        ],
        "tips": [
            "Turtle mode ต้องใช้ DSHOT300/600 เสมอ — ตรวจก่อนอย่างอื่น",
            "ถ้า motor บางตัวหมุนผิดทางตอน turtle → ตรวจ motor direction ใน BF",
            "Motor ที่ไม่มีรู airflow อาจร้อนมากตอน turtle — ระวัง",
            "ทดสอบ turtle บนพื้นก่อนใช้จริง",
        ],
    },

    "video_breakup": {
        "label": "ภาพ FPV แตก / สัญญาณ VTX หาย (Video breakup)",
        "category": "vtx",
        "diagnosis": (
            "ภาพ FPV แตกหรือหายไประหว่างบิน มักเกิดจาก: "
            "VTX ร้อนเกิน (over-temp throttle), แรงดันไฟตก (voltage sag) บน VTX, "
            "antenna ไม่ดีหรือหัก, กำลังส่ง (power) ต่ำเกิน "
            "หรือ channel ชน กับ VTX ตัวอื่นในพื้นที่"
        ),
        "primary_cause": "VTX ร้อน / แรงดันตก / antenna เสีย / channel ชน",
        "adjustments": [
            {"param": "vtx_power",   "direction": "เพิ่ม", "amount": "200mW+ สำหรับ outdoor",
             "reason": "กำลังส่งต่ำทำให้ภาพแตกเมื่อระยะห่างขึ้น"},
            {"param": "vtx_channel", "direction": "เปลี่ยน", "amount": "ใช้ channel ว่าง",
             "reason": "Channel ชนทำให้ภาพแทรกกัน"},
        ],
        "cli_template": [
            "# VTX Settings (ถ้าใช้ SmartAudio/IRC Tramp)",
            "set vtx_power = 3               # level 3 = โดยทั่วไป 200mW (ขึ้นกับ VTX)",
            "set vtx_channel = 6             # Raceband CH6 (ใช้กันน้อย)",
            "set vtx_band = 5                # Raceband",
            "# Hardware: ตรวจ solder ที่ connector VTX, ตรวจ capacitor 1000µF บน power",
            "save",
        ],
        "tips": [
            "ใส่ capacitor 470-1000µF บน power supply ของ VTX — ลด voltage sag",
            "VTX ที่ไม่มี airflow จะ throttle down กำลังส่งเองเมื่อร้อน",
            "Antenna ที่บิดงอหรือหัก ลดพิสัยมากกว่า 50%",
            "ทดสอบ VTX บนพื้น: ถ้าภาพดี แต่บินแล้วแตก = voltage sag",
            "SmartAudio: ใช้ OSD menu เปลี่ยน channel โดยไม่ต้อง land",
        ],
    },
}


def get_all_symptoms() -> List[Dict[str, str]]:
    """Return list of {id, label, category} for UI display."""
    return [
        {"id": k, "label": v["label"], "category": v["category"]}
        for k, v in SYMPTOMS.items()
    ]


def get_advice(symptom_id: str) -> Dict[str, Any]:
    """
    Return full advice for a given symptom ID.
    Returns empty dict if not found.
    """
    if symptom_id not in SYMPTOMS:
        return {"error": f"ไม่พบ symptom: {symptom_id}"}

    s = SYMPTOMS[symptom_id]
    return {
        "id":           symptom_id,
        "label":        s["label"],
        "category":     s["category"],
        "diagnosis":    s["diagnosis"],
        "primary_cause": s["primary_cause"],
        "adjustments":  s["adjustments"],
        "cli_template": s["cli_template"],
        "tips":         s["tips"],
    }
