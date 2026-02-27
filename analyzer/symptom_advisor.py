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
