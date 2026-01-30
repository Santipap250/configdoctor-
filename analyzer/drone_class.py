# analyzer/drone_class.py
# OBIXConfig Doctor - Drone class detection + baseline PID/filter
# เวอร์ชันแบบ conservative (safe baselines) — ขยายเพิ่มได้เรื่อย ๆ

from typing import Tuple, Dict, Any

DRONE_CLASSES: Dict[str, Dict[str, Any]] = {
    "micro": {
        "min_size": 2.0, "max_size": 2.9, "max_weight": 150,
        "description": "Micro / Tiny whoop (2.0–2.9\")",
        "pid": {
            "roll":  {"p": 30, "i": 30, "d": 10},
            "pitch": {"p": 30, "i": 30, "d": 10},
            "yaw":   {"p": 28, "i": 30, "d": 0}
        },
        "filter": {"gyro_lpf2": 250, "dterm_lpf1": 120, "dyn_notch": None}
    },
    "whoop": {
        "min_size": 3.0, "max_size": 3.4, "max_weight": 300,
        "description": "Toothpick / small cine (3.0–3.4\")",
        "pid": {
            "roll":  {"p": 36, "i": 36, "d": 14},
            "pitch": {"p": 36, "i": 36, "d": 14},
            "yaw":   {"p": 34, "i": 36, "d": 0}
        },
        "filter": {"gyro_lpf2": 220, "dterm_lpf1": 110, "dyn_notch": None}
    },
    "cine": {
        "min_size": 3.5, "max_size": 4.5, "max_weight": 700,
        "description": "Cine / mini (3.5–4.5\")",
        "pid": {
            "roll":  {"p": 42, "i": 45, "d": 22},
            "pitch": {"p": 42, "i": 45, "d": 22},
            "yaw":   {"p": 36, "i": 42, "d": 0}
        },
        "filter": {"gyro_lpf2": 170, "dterm_lpf1": 100, "dyn_notch": 2}
    },
    "freestyle_5": {
        "min_size": 4.6, "max_size": 5.4, "max_weight": 1200,
        "description": "5\" Freestyle (4.6–5.4\")",
        "pid": {
            "roll":  {"p": 48, "i": 52, "d": 38},
            "pitch": {"p": 48, "i": 52, "d": 38},
            "yaw":   {"p": 40, "i": 45, "d": 0}
        },
        "filter": {"gyro_lpf2": 200, "dterm_lpf1": 110, "dyn_notch": 2}
    },
    "mid_lr": {
        "min_size": 5.5, "max_size": 7.5, "max_weight": 2000,
        "description": "Mid / Long-range (5.5–7.5\")",
        "pid": {
            "roll":  {"p": 36, "i": 40, "d": 20},
            "pitch": {"p": 36, "i": 40, "d": 20},
            "yaw":   {"p": 33, "i": 38, "d": 0}
        },
        "filter": {"gyro_lpf2": 140, "dterm_lpf1": 80, "dyn_notch": 1}
    },
    "long_range": {
        "min_size": 7.6, "max_size": 10.0, "max_weight": 3500,
        "description": "Long Range / Cinematic (7.6–10\")",
        "pid": {
            "roll":  {"p": 30, "i": 34, "d": 14},
            "pitch": {"p": 30, "i": 34, "d": 14},
            "yaw":   {"p": 26, "i": 30, "d": 0}
        },
        "filter": {"gyro_lpf2": 120, "dterm_lpf1": 70, "dyn_notch": 1}
    }
}


def detect_drone_class(size: float, weight: float) -> Tuple[str, Dict[str, Any]]:
    """
    Return (class_key, class_meta) if matched, else (None, None).
    Matching uses inclusive size ranges AND weight upper bound.
    """
    try:
        s = float(size)
        w = float(weight)
    except Exception:
        return None, None

    for key, meta in DRONE_CLASSES.items():
        if meta["min_size"] <= s <= meta["max_size"] and w <= meta["max_weight"]:
            return key, meta

    # fallback: choose nearest by size center
    best = None
    best_dist = None
    for key, meta in DRONE_CLASSES.items():
        center = (meta["min_size"] + meta["max_size"]) / 2.0
        dist = abs(center - s)
        if best is None or dist < best_dist:
            best = key
            best_dist = dist

    return best, DRONE_CLASSES.get(best)