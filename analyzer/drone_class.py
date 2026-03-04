# analyzer/drone_class.py — OBIXConfig Doctor
# ============================================================
# FIX v2.3: ปรับ PID I-term ให้ตรงกับ BF4.4/4.5 (I=80-90)
# แก้ class size ranges ให้ตรงกับ logic/presets.py
# เพิ่ม class "mini" (3.6-4.5") แยกจาก cine (3.1-3.5")
# เพิ่ม Pitch P สูงกว่า Roll (~5%) ตามจริง
# NOTE: ไฟล์นี้ใช้เป็น legacy fallback เท่านั้น
#       main logic ใช้ logic/presets.py → detect_class_from_size()
# ============================================================

from typing import Tuple, Dict, Any

DRONE_CLASSES: Dict[str, Dict[str, Any]] = {
    "micro": {
        # BF4.4+: I ควรอยู่ที่ 80 ขึ้นไป (เดิม 30 = BF3.x เก่ามาก)
        "min_size": 1.0, "max_size": 2.5, "max_weight": 150,
        "description": "Micro / Tiny Whoop (1–2.5\")",
        "pid": {
            "roll":  {"p": 52, "i": 80, "d": 20},
            "pitch": {"p": 55, "i": 80, "d": 20},   # Pitch P > Roll P เสมอ
            "yaw":   {"p": 38, "i": 80, "d": 0}
        },
        "filter": {"gyro_lpf1": 250, "gyro_lpf2": None, "dterm_lpf1": 130, "dyn_notch": 2}
    },
    "whoop": {
        "min_size": 2.6, "max_size": 3.0, "max_weight": 300,
        "description": "Toothpick / Whoop (2.6–3.0\")",
        "pid": {
            "roll":  {"p": 55, "i": 85, "d": 24},
            "pitch": {"p": 58, "i": 85, "d": 25},
            "yaw":   {"p": 40, "i": 85, "d": 0}
        },
        "filter": {"gyro_lpf1": 230, "gyro_lpf2": None, "dterm_lpf1": 120, "dyn_notch": 2}
    },
    "cine": {
        # FIX: เดิม cine = 3.5-4.5" (ผิด!) — แก้เป็น 3.1-3.5" เท่านั้น
        "min_size": 3.1, "max_size": 3.5, "max_weight": 600,
        "description": "Cinewhoop / Small Cine (3.1–3.5\")",
        "pid": {
            "roll":  {"p": 50, "i": 88, "d": 28},
            "pitch": {"p": 53, "i": 88, "d": 30},
            "yaw":   {"p": 38, "i": 88, "d": 0}
        },
        "filter": {"gyro_lpf1": 200, "gyro_lpf2": None, "dterm_lpf1": 110, "dyn_notch": 2}
    },
    "mini": {
        # FIX: เพิ่ม class "mini" 3.6-4.5" ที่หายไปใน version เดิม
        "min_size": 3.6, "max_size": 4.5, "max_weight": 800,
        "description": "Mini / Light Freestyle (3.6–4.5\")",
        "pid": {
            "roll":  {"p": 50, "i": 90, "d": 33},
            "pitch": {"p": 53, "i": 90, "d": 35},
            "yaw":   {"p": 40, "i": 90, "d": 0}
        },
        "filter": {"gyro_lpf1": 200, "gyro_lpf2": None, "dterm_lpf1": 110, "dyn_notch": 2}
    },
    "freestyle_5": {
        # FIX: เดิม pitch P = roll P (ผิด) — แก้ pitch P สูงกว่า roll P
        "min_size": 4.6, "max_size": 5.5, "max_weight": 1200,
        "description": "5\" Freestyle (4.6–5.5\")",
        "pid": {
            "roll":  {"p": 48, "i": 90, "d": 38},
            "pitch": {"p": 52, "i": 90, "d": 40},   # FIX: was pitch==roll
            "yaw":   {"p": 40, "i": 90, "d": 0}
        },
        "filter": {"gyro_lpf1": 200, "gyro_lpf2": None, "dterm_lpf1": 110, "dyn_notch": 2}
    },
    "heavy_5": {
        "min_size": 5.6, "max_size": 6.0, "max_weight": 1400,
        "description": "Heavy 5\" / 6\" Build (5.6–6.0\")",
        "pid": {
            "roll":  {"p": 42, "i": 88, "d": 28},
            "pitch": {"p": 45, "i": 88, "d": 30},
            "yaw":   {"p": 35, "i": 85, "d": 0}
        },
        "filter": {"gyro_lpf1": 170, "gyro_lpf2": None, "dterm_lpf1": 100, "dyn_notch": 2}
    },
    "mid_lr": {
        # FIX: เดิม mid_lr เริ่มที่ 5.5" แต่ presets.py เริ่มที่ 6.1"
        "min_size": 6.1, "max_size": 7.5, "max_weight": 2000,
        "description": "Mid / Long-Range (6.1–7.5\")",
        "pid": {
            "roll":  {"p": 38, "i": 85, "d": 22},
            "pitch": {"p": 40, "i": 85, "d": 24},
            "yaw":   {"p": 32, "i": 82, "d": 0}
        },
        "filter": {"gyro_lpf1": 150, "gyro_lpf2": None, "dterm_lpf1": 90, "dyn_notch": 1}
    },
    "long_range": {
        # FIX: I เดิม 34 (BF3.x) → แก้เป็น 80 (BF4.4+)
        "min_size": 7.6, "max_size": 10.0, "max_weight": 3500,
        "description": "Long Range / Cinematic (7.6–10\")",
        "pid": {
            "roll":  {"p": 32, "i": 80, "d": 16},
            "pitch": {"p": 35, "i": 80, "d": 18},
            "yaw":   {"p": 28, "i": 78, "d": 0}
        },
        "filter": {"gyro_lpf1": 130, "gyro_lpf2": None, "dterm_lpf1": 80, "dyn_notch": 1}
    },
}


def detect_drone_class(size: float, weight: float) -> Tuple[str, Dict[str, Any]]:
    """
    Return (class_key, class_meta) based on size + weight.
    NOTE: preferred path is logic/presets.detect_class_from_size()
    """
    try:
        s = float(size)
        w = float(weight)
    except Exception:
        return "freestyle_5", DRONE_CLASSES["freestyle_5"]

    for key, meta in DRONE_CLASSES.items():
        if meta["min_size"] <= s <= meta["max_size"] and w <= meta["max_weight"]:
            return key, meta

    # fallback: nearest by size center
    best, best_dist = None, None
    for key, meta in DRONE_CLASSES.items():
        center = (meta["min_size"] + meta["max_size"]) / 2.0
        dist = abs(center - s)
        if best is None or dist < best_dist:
            best, best_dist = key, dist
    return best, DRONE_CLASSES.get(best)
