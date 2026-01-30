def calculate_thrust_weight(motor_load, weight):
    # Thrust-to-Weight Ratio
    try:
        ratio = (motor_load * 100) / weight
    except ZeroDivisionError:
        ratio = 0
    return round(ratio, 2)

def estimate_battery_runtime(weight, battery):
    # ประมาณเวลา (นาที) สำหรับ 4S / 6S แบบง่าย
    base = 3.5  # สมมุติเป็น minutes per unit weight
    if battery == "4S":
        return round(base * (1500/1000) / weight * 4, 1)
    elif battery == "6S":
        return round(base * (1500/1000) / weight * 6, 1)
    else:
        return 0
