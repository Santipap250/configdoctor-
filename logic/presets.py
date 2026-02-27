# logic/presets.py — OBIXConfig Doctor
# ============================================================
# IMPROVED v3:
# - PID I-term แก้จาก 30-52 → 80-100 (ตาม BF4.4/4.5 จริง)
# - แยก Roll / Pitch / Yaw ชัดเจน (Pitch P สูงกว่า Roll เสมอ)
# - เพิ่ม style variant ต่อ class (freestyle/racing/longrange)
# - Filter settings ครบ: gyro LPF1+LPF2, dterm LPF1+LPF2,
#   dynamic notch, RPM filter, anti-gravity
# - เพิ่ม get_pid_for_class_style() + get_filter_for_class()
# ============================================================
from typing import Dict, Any, Tuple, Optional

# ─────────────────────────────────────────────────────────────
# DRONE CLASS DEFINITIONS
# ─────────────────────────────────────────────────────────────
DRONE_CLASSES: Dict[str, Dict[str, Any]] = {
    "micro":      {"size_range": (1.0,  2.5),  "description": "Micro / Tiny Whoop (1–2.5\")"},
    "whoop":      {"size_range": (2.6,  3.0),  "description": "Toothpick / Whoop (2.6–3.0\")"},
    "cine":       {"size_range": (3.1,  3.5),  "description": "Cine / Small Cine (3.1–3.5\")"},
    "mini":       {"size_range": (3.6,  4.5),  "description": "Mini / Light Freestyle (3.6–4.5\")"},
    "freestyle":  {"size_range": (4.6,  5.5),  "description": "5\" Freestyle / Racing (4.6–5.5\")"},
    "heavy_5":    {"size_range": (5.6,  6.0),  "description": "Heavy 5\" / 6\" Build (5.6–6.0\")"},
    "mid_lr":     {"size_range": (6.1,  7.5),  "description": "Mid / Long-Range (6.1–7.5\")"},
    "long_range": {"size_range": (7.6, 10.0),  "description": "Long Range / Cinematic (7.6–10\")"},
}

# ─────────────────────────────────────────────────────────────
# BASELINE PID — per class, per axis
# BF4.4/4.5 community-verified starting points
# I-term: 80-100 (ค่าจริง ไม่ใช่ 30-52 แบบ BF3.x)
# Pitch P สูงกว่า Roll เสมอ (~5-8%) เพราะ CoG อยู่ด้านหน้า
# ─────────────────────────────────────────────────────────────
BASELINE_CTRL: Dict[str, Dict[str, Any]] = {
    "micro": {
        "pid": {
            "roll":  {"P": 52, "I": 80, "D": 20},
            "pitch": {"P": 55, "I": 80, "D": 20},
            "yaw":   {"P": 38, "I": 80, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       250,
            "gyro_lpf2":       None,
            "dterm_lpf1":      130,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   100,
            "dyn_notch_max":   500,
            "rpm_filter":      True,
            "anti_gravity":    5,
        },
        "notes": "Micro/whoop: gyro cutoff สูง, D ต่ำ เพราะ inertia น้อย RPM filter ช่วยมาก"
    },
    "whoop": {
        "pid": {
            "roll":  {"P": 55, "I": 85, "D": 24},
            "pitch": {"P": 58, "I": 85, "D": 25},
            "yaw":   {"P": 40, "I": 85, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       230,
            "gyro_lpf2":       None,
            "dterm_lpf1":      120,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   100,
            "dyn_notch_max":   500,
            "rpm_filter":      True,
            "anti_gravity":    5,
        },
        "notes": "Whoop/toothpick: I สูงขึ้นเล็กน้อย ช่วย lock-in บน ducted frame"
    },
    "cine": {
        "pid": {
            "roll":  {"P": 50, "I": 88, "D": 28},
            "pitch": {"P": 53, "I": 88, "D": 30},
            "yaw":   {"P": 38, "I": 88, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       200,
            "gyro_lpf2":       None,
            "dterm_lpf1":      110,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   80,
            "dyn_notch_max":   400,
            "rpm_filter":      True,
            "anti_gravity":    5,
        },
        "notes": "Cine 3-3.5\": เน้นความนิ่ง, filter ค่อนข้าง aggressive เพื่อลด jello"
    },
    "mini": {
        "pid": {
            "roll":  {"P": 50, "I": 90, "D": 33},
            "pitch": {"P": 53, "I": 90, "D": 35},
            "yaw":   {"P": 40, "I": 90, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       200,
            "gyro_lpf2":       None,
            "dterm_lpf1":      110,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   80,
            "dyn_notch_max":   400,
            "rpm_filter":      True,
            "anti_gravity":    5,
        },
        "notes": "Mini 3.6-4.5\": สมดุลระหว่าง response กับ filter"
    },
    "freestyle": {
        "pid": {
            "roll":  {"P": 48, "I": 90, "D": 38},
            "pitch": {"P": 52, "I": 90, "D": 40},
            "yaw":   {"P": 40, "I": 90, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       200,
            "gyro_lpf2":       None,
            "dterm_lpf1":      110,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   80,
            "dyn_notch_max":   400,
            "rpm_filter":      True,
            "anti_gravity":    5,
        },
        "notes": "5\" Freestyle (BF4.4/4.5): I=90 เพื่อ lock-in ดี, RPM filter ลด motor noise"
    },
    "heavy_5": {
        "pid": {
            "roll":  {"P": 42, "I": 88, "D": 28},
            "pitch": {"P": 45, "I": 88, "D": 30},
            "yaw":   {"P": 35, "I": 85, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       170,
            "gyro_lpf2":       None,
            "dterm_lpf1":      100,
            "dterm_lpf2":      None,
            "dyn_notch_count": 2,
            "dyn_notch_min":   80,
            "dyn_notch_max":   350,
            "rpm_filter":      True,
            "anti_gravity":    4,
        },
        "notes": "Heavy 5\"/6\": P ลดลงเพราะ inertia สูง, filter ต่ำลงเพื่อ stability"
    },
    "mid_lr": {
        "pid": {
            "roll":  {"P": 38, "I": 85, "D": 22},
            "pitch": {"P": 40, "I": 85, "D": 24},
            "yaw":   {"P": 32, "I": 82, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       150,
            "gyro_lpf2":       None,
            "dterm_lpf1":      90,
            "dterm_lpf2":      None,
            "dyn_notch_count": 1,
            "dyn_notch_min":   60,
            "dyn_notch_max":   300,
            "rpm_filter":      True,
            "anti_gravity":    3,
        },
        "notes": "Mid/LR 6-7.5\": เน้น stability, anti-gravity ต่ำลงเพราะ throttle punch-in น้อย"
    },
    "long_range": {
        "pid": {
            "roll":  {"P": 32, "I": 80, "D": 16},
            "pitch": {"P": 35, "I": 80, "D": 18},
            "yaw":   {"P": 28, "I": 78, "D": 0},
        },
        "filter": {
            "gyro_lpf1":       130,
            "gyro_lpf2":       None,
            "dterm_lpf1":      80,
            "dterm_lpf2":      None,
            "dyn_notch_count": 1,
            "dyn_notch_min":   50,
            "dyn_notch_max":   250,
            "rpm_filter":      True,
            "anti_gravity":    3,
        },
        "notes": "LR 7.6-10\": P/D ต่ำ smooth response, I ยังสูงเพื่อ wind rejection ระยะไกล"
    },
}

# ─────────────────────────────────────────────────────────────
# STYLE MULTIPLIERS
# ปรับ P/I/D ตาม flying style บน top of class baseline
# ─────────────────────────────────────────────────────────────
_STYLE_ADJUST = {
    "freestyle": {"p_mul": 1.00, "i_mul": 1.00, "d_mul": 1.00},
    "racing":    {"p_mul": 1.15, "i_mul": 0.92, "d_mul": 1.12},
    "longrange": {"p_mul": 0.88, "i_mul": 1.00, "d_mul": 0.82},
}

def _apply_style(pid_axis: dict, mul: dict) -> dict:
    return {
        "p": max(1, round(pid_axis["P"] * mul["p_mul"])),
        "i": max(1, round(pid_axis["I"] * mul["i_mul"])),
        "d": max(0, round(pid_axis.get("D", 0) * mul["d_mul"])),
    }

def get_pid_for_class_style(cls_key: str, style: str) -> Dict[str, Any]:
    """
    Return per-axis PID {roll, pitch, yaw} adjusted for frame class + flying style.
    Values are in lowercase keys (p/i/d) for template compatibility.
    """
    base = BASELINE_CTRL.get(cls_key) or BASELINE_CTRL["freestyle"]
    pid_base = base.get("pid", {})
    mul = _STYLE_ADJUST.get(style, _STYLE_ADJUST["freestyle"])

    roll_base  = pid_base.get("roll",  {"P": 48, "I": 90, "D": 38})
    pitch_base = pid_base.get("pitch", {"P": 52, "I": 90, "D": 40})
    yaw_base   = pid_base.get("yaw",   {"P": 40, "I": 90, "D": 0})

    return {
        "roll":  _apply_style(roll_base,  mul),
        "pitch": _apply_style(pitch_base, mul),
        "yaw":   {**_apply_style(yaw_base, {**mul, "d_mul": 1.0}), "d": 0},
    }

def get_filter_for_class(cls_key: str) -> Dict[str, Any]:
    """Return complete filter settings for a class."""
    base = BASELINE_CTRL.get(cls_key) or BASELINE_CTRL["freestyle"]
    flt = base.get("filter", {})
    return {
        "gyro_lpf1":       flt.get("gyro_lpf1", 200),
        "gyro_lpf2":       flt.get("gyro_lpf2"),
        "dterm_lpf1":      flt.get("dterm_lpf1", 110),
        "dterm_lpf2":      flt.get("dterm_lpf2"),
        "dyn_notch_count": flt.get("dyn_notch_count", 2),
        "dyn_notch_min":   flt.get("dyn_notch_min", 80),
        "dyn_notch_max":   flt.get("dyn_notch_max", 400),
        "rpm_filter":      flt.get("rpm_filter", True),
        "anti_gravity":    flt.get("anti_gravity", 5),
    }

# ─────────────────────────────────────────────────────────────
# PRESETS
# ─────────────────────────────────────────────────────────────
PRESETS: Dict[str, Dict[str, Any]] = {
    "2.5_micro":   {"class": "micro",      "size": 2.5,  "weight": 80,   "battery": "3S", "prop_size": 2.5,  "pitch": 2.0, "blades": 2, "style": "freestyle"},
    "3_whoop":     {"class": "whoop",      "size": 3.0,  "weight": 120,  "battery": "3S", "prop_size": 3.0,  "pitch": 2.0, "blades": 2, "style": "freestyle"},
    "3.5_cine":    {"class": "cine",       "size": 3.5,  "weight": 350,  "battery": "4S", "prop_size": 3.5,  "pitch": 2.5, "blades": 2, "style": "longrange"},
    "4_mini":      {"class": "mini",       "size": 4.0,  "weight": 420,  "battery": "4S", "prop_size": 4.0,  "pitch": 3.0, "blades": 2, "style": "freestyle"},
    "5_freestyle": {"class": "freestyle",  "size": 5.0,  "weight": 750,  "battery": "4S", "prop_size": 5.0,  "pitch": 4.0, "blades": 3, "style": "freestyle"},
    "6_heavy5":    {"class": "heavy_5",    "size": 6.0,  "weight": 1000, "battery": "6S", "prop_size": 6.0,  "pitch": 4.0, "blades": 3, "style": "freestyle"},
    "7_midlr":     {"class": "mid_lr",     "size": 7.0,  "weight": 1100, "battery": "6S", "prop_size": 7.0,  "pitch": 3.5, "blades": 2, "style": "longrange"},
    "7.5_midlr":   {"class": "mid_lr",     "size": 7.5,  "weight": 1200, "battery": "6S", "prop_size": 7.5,  "pitch": 3.0, "blades": 2, "style": "longrange"},
    "8_lr":        {"class": "long_range", "size": 8.0,  "weight": 1500, "battery": "6S", "prop_size": 8.0,  "pitch": 3.5, "blades": 2, "style": "longrange"},
    "10_lr":       {"class": "long_range", "size": 10.0, "weight": 2200, "battery": "6S", "prop_size": 10.0, "pitch": 4.5, "blades": 2, "style": "longrange"},
}

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def detect_class_from_size(size: float) -> Tuple[str, Dict[str, Any]]:
    try:
        s = float(size)
    except Exception:
        return "freestyle", DRONE_CLASSES["freestyle"]
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        if lo <= s <= hi:
            return cls, meta
    best, best_dist = None, None
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        dist = abs((lo + hi) / 2.0 - s)
        if best is None or dist < best_dist:
            best, best_dist = cls, dist
    return best, DRONE_CLASSES[best]


def get_baseline_for_class(cls_key: str) -> Dict[str, Any]:
    """Return baseline dict — backward-compatible with old template keys."""
    data = BASELINE_CTRL.get(cls_key, {})
    pid_axes = data.get("pid", {})
    flt = data.get("filter", {})
    roll = pid_axes.get("roll", {"P": 48, "I": 90, "D": 38})
    return {
        "pid": {"P": roll["P"], "I": roll["I"], "D": roll.get("D", 0)},
        "pid_axes": pid_axes,
        "filter": {
            "gyro_cutoff":     flt.get("gyro_lpf1"),
            "gyro_lpf1":       flt.get("gyro_lpf1"),
            "gyro_lpf2":       flt.get("gyro_lpf2", "—"),
            "dterm_lowpass":   flt.get("dterm_lpf1"),
            "dterm_lpf1":      flt.get("dterm_lpf1"),
            "dterm_lpf2":      flt.get("dterm_lpf2", "—"),
            "dyn_notch":       flt.get("dyn_notch_count", 2),
            "dyn_notch_min":   flt.get("dyn_notch_min"),
            "dyn_notch_max":   flt.get("dyn_notch_max"),
            "rpm_filter":      flt.get("rpm_filter", True),
            "anti_gravity":    flt.get("anti_gravity", 5),
        },
        "notes": data.get("notes", ""),
    }
