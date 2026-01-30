# logic/presets.py
# OBIXConfig Doctor - Extended Drone Classes + Baseline Presets
# รองรับขนาดตั้งแต่ 2" ถึง 10" แบ่งเป็น class ที่เหมาะสม
from typing import Dict, Any, Tuple

# -----------------------
# Drone classes definition
# -----------------------
# Each class: size_range (inclusive), description
DRONE_CLASSES: Dict[str, Dict[str, Any]] = {
    "micro": {"size_range": (2.0, 2.5), "description": "Micro / Tiny whoops (2.0–2.5\")"},
    "whoop": {"size_range": (2.6, 3.0), "description": "Toothpick / Tiny whoop (2.6–3.0\")"},
    "cine": {"size_range": (3.1, 3.5), "description": "Cine / small cine (3.1–3.5\")"},
    "mini": {"size_range": (3.6, 4.5), "description": "Light freestyle / mini (3.6–4.5\")"},
    "freestyle": {"size_range": (4.6, 5.5), "description": "5\" Freestyle (4.6–5.5\")"},
    "heavy_5": {"size_range": (5.6, 6.0), "description": "Heavy 5\" / 6\" (5.6–6.0\")"},
    "mid_lr": {"size_range": (6.1, 7.5), "description": "Mid / Long-range (6.1–7.5\")"},
    "long_range": {"size_range": (7.6, 10.0), "description": "Long Range / Cinematic (7.6–10\")"},
}

# -----------------------
# Baseline PID & Filter per class (conservative & safe)
# Notes: These are baseline starting points designed to be safe for initial flights.
# Adjust per motor/prop/airframe after real test.
# -----------------------
BASELINE_CTRL: Dict[str, Dict[str, Any]] = {
    "micro": {
        "pid": {"P": 30, "I": 30, "D": 10},
        "filter": {"gyro_cutoff": 250, "dterm_lowpass": 120},
        "notes": "Tiny whoop/micro: high gyro cutoff, low D due to small inertia."
    },
    "whoop": {
        "pid": {"P": 34, "I": 34, "D": 14},
        "filter": {"gyro_cutoff": 230, "dterm_lowpass": 110},
        "notes": "Toothpick / whoop-style small frames."
    },
    "cine": {
        "pid": {"P": 40, "I": 40, "D": 22},
        "filter": {"gyro_cutoff": 170, "dterm_lowpass": 90},
        "notes": "3-3.5\" cine: smooth, low-aggression."
    },
    "mini": {
        "pid": {"P": 40, "I": 42, "D": 24},
        "filter": {"gyro_cutoff": 190, "dterm_lowpass": 100},
        "notes": "3.6-4.5\" mini freestyle: balanced control."
    },
    "freestyle": {
        "pid": {"P": 42, "I": 45, "D": 26},
        "filter": {"gyro_cutoff": 200, "dterm_lowpass": 110},
        "notes": "5\" freestyle baseline: good control without oscillation."
    },
    "heavy_5": {
        "pid": {"P": 36, "I": 40, "D": 20},
        "filter": {"gyro_cutoff": 160, "dterm_lowpass": 90},
        "notes": "Heavy 5\" or 6\" builds: extra inertia, slightly lower gyro cut."
    },
    "mid_lr": {
        "pid": {"P": 30, "I": 34, "D": 18},
        "filter": {"gyro_cutoff": 140, "dterm_lowpass": 80},
        "notes": "6-7.5\" mid/LR: emphasis on stability and smoothness."
    },
    "long_range": {
        "pid": {"P": 26, "I": 30, "D": 14},
        "filter": {"gyro_cutoff": 120, "dterm_lowpass": 70},
        "notes": "8-10\" long-range: low aggression, stable."
    },
}

# -----------------------
# Preset auto-fill examples (quick form fill)
# Key format: "<size>_<shortkey>"
# These are examples — สามารถเพิ่มได้ทีหลัง
# -----------------------
PRESETS: Dict[str, Dict[str, Any]] = {
    "2.5_micro": {
        "class": "micro", "size": 2.5, "weight": 80, "battery": "2S", "prop_size": 2.5, "pitch": 2.0, "blades": 2, "style": "micro"
    },
    "3_whoop": {
        "class": "whoop", "size": 3.0, "weight": 120, "battery": "2S", "prop_size": 3.0, "pitch": 2.0, "blades": 2, "style": "whoop"
    },
    "3.5_cine": {
        "class": "cine", "size": 3.5, "weight": 350, "battery": "4S", "prop_size": 3.5, "pitch": 2.5, "blades": 2, "style": "cine"
    },
    "4_mini": {
        "class": "mini", "size": 4.0, "weight": 420, "battery": "4S", "prop_size": 4.0, "pitch": 3.0, "blades": 2, "style": "mini"
    },
    "5_freestyle": {
        "class": "freestyle", "size": 5.0, "weight": 750, "battery": "4S", "prop_size": 5.0, "pitch": 4.0, "blades": 3, "style": "freestyle"
    },
    "6_heavy5": {
        "class": "heavy_5", "size": 6.0, "weight": 1000, "battery": "4S", "prop_size": 6.0, "pitch": 4.0, "blades": 3, "style": "heavy"
    },
    "7_midlr": {
        "class": "mid_lr", "size": 7.0, "weight": 1100, "battery": "4S", "prop_size": 7.0, "pitch": 3.5, "blades": 2, "style": "longrange"
    },
    "7.5_midlr": {
        "class": "mid_lr", "size": 7.5, "weight": 1200, "battery": "4S", "prop_size": 7.5, "pitch": 3.0, "blades": 2, "style": "longrange"
    },
    "8_lr": {
        "class": "long_range", "size": 8.0, "weight": 1500, "battery": "4S", "prop_size": 8.0, "pitch": 3.5, "blades": 2, "style": "longrange"
    },
    "10_lr": {
        "class": "long_range", "size": 10.0, "weight": 2200, "battery": "6S", "prop_size": 10.0, "pitch": 4.5, "blades": 2, "style": "longrange"
    }
}

# -----------------------
# Helper functions
# -----------------------
def detect_class_from_size(size: float) -> Tuple[str, Dict[str, Any]]:
    """
    Return (class_key, meta) based on size (inches).
    If exact class not found, returns nearest logical class.
    """
    # exact match
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        if lo <= size <= hi:
            return cls, meta

    # fallback: find nearest by distance to center
    best = None
    best_dist = None
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        center = (lo + hi) / 2.0
        dist = abs(center - size)
        if best is None or dist < best_dist:
            best = cls
            best_dist = dist
    return best, DRONE_CLASSES[best]


def get_baseline_for_class(cls_key: str) -> Dict[str, Any]:
    """Return baseline PID/filter and notes for a class key."""
    return BASELINE_CTRL.get(cls_key, {"pid": {}, "filter": {}, "notes": "No baseline available"})