# analyzer/thrust_logic.py
"""
BUG ที่แก้ไข:
1. calculate_thrust_weight(): สูตรเดิม `motor_load * 100 / weight`
   ใช้ motor_load เป็น score (1-6) ไม่ใช่กรัม → ได้ค่า TWR ผิด เช่น 0.0006
   แก้: normalize score เป็น rough TWR range 0–3 ไว้ใช้เป็น fallback
   (advanced_analysis.py จะ override ด้วยค่าจริงเมื่อมีข้อมูลครบ)

2. estimate_battery_runtime(): สูตรเดิม `base * (1500/1000) / weight * cells`
   สำหรับ weight=1000g, 4S → 3.5 * 1.5 / 1000 * 4 = 0.021 นาที (ผิดมาก)
   แก้: ใช้สูตร physics-based: (Wh / hover_power_W) * 60
"""

_DEFAULT_MAH = 1500
_W_PER_GRAM = 0.12     # empirical hover: 0.12 W/g
_NOMINAL_CELL_V = 3.7


def calculate_thrust_weight(motor_load, weight):
    """
    คืนค่า TWR แบบ rough estimate จาก motor_load score (0–6)
    ค่า None หมายถึงคำนวณไม่ได้ — advanced_analysis จะ override ถ้ามีข้อมูล
    """
    try:
        w = float(weight)
        ml = float(motor_load)
        if w <= 0 or ml <= 0:
            return None
        # score 0–6 → TWR range ~0–3  (rough)
        return round((ml / 6.0) * 3.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def estimate_battery_runtime(weight, battery, battery_mAh=None):
    """
    ประมาณเวลาบิน (นาที)
    สูตร: (battery_Wh / hover_power_W) * 60
    ตัวอย่าง: 4S 1500mAh, 750g → (22.2Wh / 90W) * 60 ≈ 14.8 min
    """
    try:
        w = float(weight)
        if w <= 0:
            return 0
        try:
            cells = int(str(battery).upper().replace("S", "").strip())
            cells = max(1, min(cells, 12))
        except Exception:
            cells = 4

        mAh = float(battery_mAh) if battery_mAh else _DEFAULT_MAH
        voltage = cells * _NOMINAL_CELL_V
        battery_wh = (mAh / 1000.0) * voltage
        hover_power_w = _W_PER_GRAM * w
        if hover_power_w <= 0:
            return 0
        minutes = (battery_wh / hover_power_w) * 60.0
        return round(max(0.0, minutes), 1)
    except Exception:
        return 0
