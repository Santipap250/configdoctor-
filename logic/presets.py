# logic/presets.py — OBIXConfig Doctor v5.2
# ============================================================
# v5.2 — MASSIVE PRESET EXPANSION
# - 1.5"–12" ทุก battery S-count
# - 5" แยก 4S / 5S / 6S baseline PID ต่างกัน
# - named presets: Freestyle/Racing/Cine/LR/UltraLR
# ============================================================
from typing import Dict, Any, Tuple, Optional

DRONE_CLASSES: Dict[str, Dict[str, Any]] = {
    "nano":       {"size_range": (0.0,  1.4),  "description": "Nano / Micro Whoop (<=1.4\")"},
    "micro":      {"size_range": (1.5,  2.5),  "description": "Micro / Tiny Whoop (1.5-2.5\")"},
    "whoop":      {"size_range": (2.6,  3.0),  "description": "Toothpick / Whoop (2.6-3.0\")"},
    "cine":       {"size_range": (3.1,  3.5),  "description": "Cine / Small Cine (3.1-3.5\")"},
    "mini":       {"size_range": (3.6,  4.5),  "description": "Mini / Light Freestyle (3.6-4.5\")"},
    "freestyle":  {"size_range": (4.6,  5.5),  "description": "5\" Freestyle / Racing (4.6-5.5\")"},
    "heavy_5":    {"size_range": (5.6,  6.0),  "description": "Heavy 5\" / 6\" Build (5.6-6.0\")"},
    "mid_lr":     {"size_range": (6.1,  7.5),  "description": "Mid / Long-Range (6.1-7.5\")"},
    "long_range": {"size_range": (7.6, 10.0),  "description": "Long Range / Cinematic (7.6-10\")"},
    "ultra_lr":   {"size_range": (10.1, 15.0), "description": "Ultra Long Range / Heavy Lifter (10\"+)"},
}

BASELINE_CTRL: Dict[str, Dict[str, Any]] = {
    "nano": {
        "pid": {"roll":{"P":48,"I":75,"D":14},"pitch":{"P":50,"I":75,"D":15},"yaw":{"P":35,"I":75,"D":0}},
        "filter": {"gyro_lpf1":300,"gyro_lpf2":None,"dterm_lpf1":150,"dterm_lpf2":None,"dyn_notch_count":1,"dyn_notch_min":150,"dyn_notch_max":600,"rpm_filter":True,"anti_gravity":3},
        "notes": "Nano <=1.4\": RPM filter สำคัญมาก inertia ต่ำสุด D ไม่ต้องเยอะ",
    },
    "micro": {
        "pid": {"roll":{"P":52,"I":80,"D":20},"pitch":{"P":55,"I":80,"D":20},"yaw":{"P":38,"I":80,"D":0}},
        "filter": {"gyro_lpf1":250,"gyro_lpf2":None,"dterm_lpf1":130,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":120,"dyn_notch_max":550,"rpm_filter":True,"anti_gravity":4},
        "notes": "Micro 1.5-2.5\": gyro cutoff สูง D ต่ำ RPM filter ลด motor buzz",
    },
    "whoop": {
        "pid": {"roll":{"P":55,"I":85,"D":24},"pitch":{"P":58,"I":85,"D":25},"yaw":{"P":40,"I":85,"D":0}},
        "filter": {"gyro_lpf1":230,"gyro_lpf2":None,"dterm_lpf1":120,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":100,"dyn_notch_max":500,"rpm_filter":True,"anti_gravity":5},
        "notes": "Whoop/Toothpick: I สูงช่วย lock-in บน ducted frame",
    },
    "cine": {
        "pid": {"roll":{"P":50,"I":88,"D":28},"pitch":{"P":53,"I":88,"D":30},"yaw":{"P":38,"I":88,"D":0}},
        "filter": {"gyro_lpf1":200,"gyro_lpf2":None,"dterm_lpf1":110,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":400,"rpm_filter":True,"anti_gravity":5},
        "notes": "Cine 3-3.5\": filter aggressive ลด jello D ปานกลาง",
    },
    "mini": {
        "pid": {"roll":{"P":50,"I":90,"D":33},"pitch":{"P":53,"I":90,"D":35},"yaw":{"P":40,"I":90,"D":0}},
        "filter": {"gyro_lpf1":200,"gyro_lpf2":None,"dterm_lpf1":110,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":400,"rpm_filter":True,"anti_gravity":5},
        "notes": "Mini 3.6-4.5\": สมดุล response กับ filter",
    },
    # 5\" แยก 4S/5S/6S
    "freestyle": {
        "pid": {"roll":{"P":48,"I":90,"D":38},"pitch":{"P":52,"I":90,"D":40},"yaw":{"P":40,"I":90,"D":0}},
        "filter": {"gyro_lpf1":200,"gyro_lpf2":None,"dterm_lpf1":110,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":400,"rpm_filter":True,"anti_gravity":5},
        "notes": "5\" Freestyle 4S (BF4.4/4.5): I=90 lock-in ดี RPM filter ลด motor noise",
    },
    "freestyle_5s": {
        "pid": {"roll":{"P":44,"I":88,"D":36},"pitch":{"P":47,"I":88,"D":38},"yaw":{"P":37,"I":88,"D":0}},
        "filter": {"gyro_lpf1":185,"gyro_lpf2":None,"dterm_lpf1":105,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":380,"rpm_filter":True,"anti_gravity":5},
        "notes": "5\" Freestyle 5S: P ลงเพราะ throttle resolution ดีขึ้น voltage สูงขึ้น motor เร็วขึ้น",
    },
    "freestyle_6s": {
        "pid": {"roll":{"P":40,"I":85,"D":34},"pitch":{"P":43,"I":85,"D":36},"yaw":{"P":34,"I":85,"D":0}},
        "filter": {"gyro_lpf1":175,"gyro_lpf2":None,"dterm_lpf1":100,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":360,"rpm_filter":True,"anti_gravity":4},
        "notes": "5\" Freestyle 6S: P ต้องลงอีก มิฉะนั้น oscillate รุนแรง D ลดเพราะ noise มากขึ้น",
    },
    "heavy_5": {
        "pid": {"roll":{"P":42,"I":88,"D":28},"pitch":{"P":45,"I":88,"D":30},"yaw":{"P":35,"I":85,"D":0}},
        "filter": {"gyro_lpf1":170,"gyro_lpf2":None,"dterm_lpf1":100,"dterm_lpf2":None,"dyn_notch_count":2,"dyn_notch_min":80,"dyn_notch_max":350,"rpm_filter":True,"anti_gravity":4},
        "notes": "Heavy 5\"/6\": inertia สูง P ลงเพื่อ stability",
    },
    "mid_lr": {
        "pid": {"roll":{"P":38,"I":85,"D":22},"pitch":{"P":40,"I":85,"D":24},"yaw":{"P":32,"I":82,"D":0}},
        "filter": {"gyro_lpf1":150,"gyro_lpf2":None,"dterm_lpf1":90,"dterm_lpf2":None,"dyn_notch_count":1,"dyn_notch_min":100,"dyn_notch_max":350,"rpm_filter":True,"anti_gravity":3},
        "notes": "Mid/LR 6-7.5\": stability over agility anti_gravity ต่ำ throttle punch-in น้อยกว่า",
    },
    "long_range": {
        "pid": {"roll":{"P":32,"I":80,"D":16},"pitch":{"P":35,"I":80,"D":18},"yaw":{"P":28,"I":78,"D":0}},
        "filter": {"gyro_lpf1":130,"gyro_lpf2":None,"dterm_lpf1":80,"dterm_lpf2":None,"dyn_notch_count":1,"dyn_notch_min":100,"dyn_notch_max":320,"rpm_filter":True,"anti_gravity":3},
        "notes": "LR 7.6-10\": P/D ต่ำ smooth response I สูง wind rejection ระยะไกล",
    },
    "ultra_lr": {
        "pid": {"roll":{"P":26,"I":75,"D":12},"pitch":{"P":28,"I":75,"D":13},"yaw":{"P":22,"I":72,"D":0}},
        "filter": {"gyro_lpf1":110,"gyro_lpf2":None,"dterm_lpf1":70,"dterm_lpf2":None,"dyn_notch_count":1,"dyn_notch_min":80,"dyn_notch_max":280,"rpm_filter":True,"anti_gravity":2},
        "notes": "Ultra LR 10\"+: P/D ต่ำมาก เน้น stability สุดๆ ไม่ทำ trick",
    },
}

_STYLE_ADJUST = {
    "freestyle": {"p_mul":1.00,"i_mul":1.00,"d_mul":1.00},
    "racing":    {"p_mul":1.18,"i_mul":0.90,"d_mul":1.15},
    "longrange": {"p_mul":0.85,"i_mul":1.00,"d_mul":0.80},
}

def _cells_from_str(s):
    try: return max(1, min(int(str(s).upper().replace("S","").strip()), 8))
    except: return 4

def _pick_baseline_key(cls_key, battery="4S"):
    cells = _cells_from_str(str(battery or "4S"))
    if cls_key == "freestyle":
        if cells >= 6: return "freestyle_6s"
        if cells == 5: return "freestyle_5s"
    return cls_key

def _apply_style(pid_axis, mul):
    return {"p":max(1,round(pid_axis["P"]*mul["p_mul"])),"i":max(1,round(pid_axis["I"]*mul["i_mul"])),"d":max(0,round(pid_axis.get("D",0)*mul["d_mul"]))}

def get_pid_for_class_style(cls_key, style, battery="4S"):
    bkey = _pick_baseline_key(cls_key, battery)
    base = BASELINE_CTRL.get(bkey) or BASELINE_CTRL.get(cls_key) or BASELINE_CTRL["freestyle"]
    pid_base = base.get("pid", {})
    mul = _STYLE_ADJUST.get(style, _STYLE_ADJUST["freestyle"])
    roll_base  = pid_base.get("roll",  {"P":48,"I":90,"D":38})
    pitch_base = pid_base.get("pitch", {"P":52,"I":90,"D":40})
    yaw_base   = pid_base.get("yaw",   {"P":40,"I":90,"D":0})
    return {
        "roll":  _apply_style(roll_base, mul),
        "pitch": _apply_style(pitch_base, mul),
        "yaw":   {**_apply_style(yaw_base, {**mul,"d_mul":1.0}), "d":0},
    }

def get_filter_for_class(cls_key, battery="4S"):
    bkey = _pick_baseline_key(cls_key, battery)
    base = BASELINE_CTRL.get(bkey) or BASELINE_CTRL.get(cls_key) or BASELINE_CTRL["freestyle"]
    flt = base.get("filter", {})
    return {"gyro_lpf1":flt.get("gyro_lpf1",200),"gyro_lpf2":flt.get("gyro_lpf2"),"dterm_lpf1":flt.get("dterm_lpf1",110),"dterm_lpf2":flt.get("dterm_lpf2"),"dyn_notch_count":flt.get("dyn_notch_count",2),"dyn_notch_min":flt.get("dyn_notch_min",80),"dyn_notch_max":flt.get("dyn_notch_max",400),"rpm_filter":flt.get("rpm_filter",True),"anti_gravity":flt.get("anti_gravity",5)}

PRESETS: Dict[str, Dict[str, Any]] = {
    # Nano
    "1s_nano":         {"label":"1\" Nano Whoop 1S","class":"nano","size":1.0,"weight":22,"battery":"1S","battery_mAh":250,"prop_size":1.0,"pitch":1.0,"blades":4,"style":"freestyle","motor_kv":19000},
    "1.5_tiny":        {"label":"1.5\" Tiny Whoop 1S","class":"nano","size":1.5,"weight":30,"battery":"1S","battery_mAh":300,"prop_size":1.5,"pitch":1.2,"blades":4,"style":"freestyle","motor_kv":12500},
    "2_nano_2s":       {"label":"2\" Nano 2S","class":"micro","size":2.0,"weight":60,"battery":"2S","battery_mAh":350,"prop_size":2.0,"pitch":1.5,"blades":3,"style":"freestyle","motor_kv":8000},
    # Micro
    "2.5_micro_2s":    {"label":"2.5\" Micro 2S","class":"micro","size":2.5,"weight":75,"battery":"2S","battery_mAh":400,"prop_size":2.5,"pitch":2.0,"blades":3,"style":"freestyle","motor_kv":6000},
    "2.5_micro_3s":    {"label":"2.5\" Micro 3S","class":"micro","size":2.5,"weight":80,"battery":"3S","battery_mAh":400,"prop_size":2.5,"pitch":2.0,"blades":2,"style":"freestyle","motor_kv":4500},
    "3_whoop_1s":      {"label":"3\" Whoop 1S","class":"whoop","size":3.0,"weight":85,"battery":"1S","battery_mAh":550,"prop_size":3.0,"pitch":2.0,"blades":4,"style":"freestyle","motor_kv":8500},
    "3_whoop_2s":      {"label":"3\" Toothpick 2S","class":"whoop","size":3.0,"weight":90,"battery":"2S","battery_mAh":500,"prop_size":3.0,"pitch":2.0,"blades":2,"style":"freestyle","motor_kv":5500},
    "3_whoop_3s":      {"label":"3\" Whoop 3S","class":"whoop","size":3.0,"weight":120,"battery":"3S","battery_mAh":550,"prop_size":3.0,"pitch":2.0,"blades":2,"style":"freestyle","motor_kv":3500},
    # Cine 3.5"
    "3.5_cine_3s":     {"label":"3.5\" Cine 3S","class":"cine","size":3.5,"weight":280,"battery":"3S","battery_mAh":750,"prop_size":3.5,"pitch":2.5,"blades":2,"style":"longrange","motor_kv":2750},
    "3.5_cine_4s":     {"label":"3.5\" Cine 4S","class":"cine","size":3.5,"weight":300,"battery":"4S","battery_mAh":650,"prop_size":3.5,"pitch":2.5,"blades":2,"style":"longrange","motor_kv":2500},
    # Mini 4"
    "4_mini_3s":       {"label":"4\" Mini 3S","class":"mini","size":4.0,"weight":380,"battery":"3S","battery_mAh":850,"prop_size":4.0,"pitch":3.0,"blades":2,"style":"freestyle","motor_kv":2800},
    "4_mini_4s_free":  {"label":"4\" Mini 4S Freestyle","class":"mini","size":4.0,"weight":420,"battery":"4S","battery_mAh":850,"prop_size":4.0,"pitch":3.0,"blades":2,"style":"freestyle","motor_kv":2500},
    "4_mini_4s_race":  {"label":"4\" Mini 4S Racing","class":"mini","size":4.0,"weight":400,"battery":"4S","battery_mAh":750,"prop_size":4.0,"pitch":3.5,"blades":3,"style":"racing","motor_kv":2600},
    # 5" 4S
    "5_4s_freestyle":  {"label":"5\" 4S Freestyle (Standard)","class":"freestyle","size":5.0,"weight":720,"battery":"4S","battery_mAh":1500,"prop_size":5.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":2306},
    "5_4s_racing":     {"label":"5\" 4S Racing Gate","class":"freestyle","size":5.0,"weight":650,"battery":"4S","battery_mAh":1300,"prop_size":5.1,"pitch":4.5,"blades":3,"style":"racing","motor_kv":2550},
    "5_4s_smooth":     {"label":"5\" 4S Smooth / HD Cine","class":"freestyle","size":5.0,"weight":800,"battery":"4S","battery_mAh":1800,"prop_size":5.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":1950},
    "5_4s_bangers":    {"label":"5\" 4S Bangers (High-D)","class":"freestyle","size":5.0,"weight":710,"battery":"4S","battery_mAh":1500,"prop_size":5.1,"pitch":4.1,"blades":3,"style":"freestyle","motor_kv":2450},
    # 5" 5S
    "5_5s_freestyle":  {"label":"5\" 5S Freestyle","class":"freestyle","size":5.0,"weight":730,"battery":"5S","battery_mAh":1300,"prop_size":5.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1900},
    "5_5s_racing":     {"label":"5\" 5S Race Spec","class":"freestyle","size":5.0,"weight":660,"battery":"5S","battery_mAh":1100,"prop_size":5.1,"pitch":4.6,"blades":3,"style":"racing","motor_kv":2000},
    "5_5s_dji":        {"label":"5\" 5S DJI O3/O4 Build","class":"freestyle","size":5.0,"weight":780,"battery":"5S","battery_mAh":1300,"prop_size":5.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1750},
    # 5" 6S
    "5_6s_freestyle":  {"label":"5\" 6S Freestyle","class":"freestyle","size":5.0,"weight":750,"battery":"6S","battery_mAh":1100,"prop_size":5.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1750},
    "5_6s_racing":     {"label":"5\" 6S Race Build","class":"freestyle","size":5.0,"weight":680,"battery":"6S","battery_mAh":1000,"prop_size":5.1,"pitch":4.6,"blades":3,"style":"racing","motor_kv":1900},
    "5_6s_lr":         {"label":"5\" 6S Long Range","class":"freestyle","size":5.0,"weight":800,"battery":"6S","battery_mAh":1500,"prop_size":5.0,"pitch":3.8,"blades":2,"style":"longrange","motor_kv":1600},
    # 6"
    "6_4s_heavy":      {"label":"6\" 4S Heavy Freestyle","class":"heavy_5","size":6.0,"weight":900,"battery":"4S","battery_mAh":2200,"prop_size":6.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1700},
    "6_6s_standard":   {"label":"6\" 6S Standard Freestyle","class":"heavy_5","size":6.0,"weight":850,"battery":"6S","battery_mAh":1300,"prop_size":6.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1750},
    "6_6s_cine":       {"label":"6\" 6S Cine Smooth","class":"heavy_5","size":6.0,"weight":950,"battery":"6S","battery_mAh":1500,"prop_size":6.0,"pitch":3.8,"blades":2,"style":"longrange","motor_kv":1600},
    # 7" Mid LR
    "7_4s_midlr":      {"label":"7\" 4S Mid-Range","class":"mid_lr","size":7.0,"weight":1000,"battery":"4S","battery_mAh":3000,"prop_size":7.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":1300},
    "7_6s_midlr":      {"label":"7\" 6S Mid LR (Popular)","class":"mid_lr","size":7.0,"weight":1100,"battery":"6S","battery_mAh":2200,"prop_size":7.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":1200},
    "7.5_6s_midlr":    {"label":"7.5\" 6S LR Spec","class":"mid_lr","size":7.5,"weight":1200,"battery":"6S","battery_mAh":2500,"prop_size":7.5,"pitch":3.0,"blades":2,"style":"longrange","motor_kv":1100},
    "7_6s_freestyle":  {"label":"7\" 6S Freestyle Big","class":"mid_lr","size":7.0,"weight":1050,"battery":"6S","battery_mAh":2000,"prop_size":7.0,"pitch":4.0,"blades":3,"style":"freestyle","motor_kv":1300},
    # 8" LR
    "8_6s_lr":         {"label":"8\" 6S Long Range","class":"long_range","size":8.0,"weight":1400,"battery":"6S","battery_mAh":3000,"prop_size":8.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":1000},
    "8_6s_hd":         {"label":"8\" 6S LR + HD Payload","class":"long_range","size":8.0,"weight":1600,"battery":"6S","battery_mAh":3500,"prop_size":8.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":900},
    "8_7s_ultra":      {"label":"8\" 7S Ultra LR","class":"long_range","size":8.0,"weight":1500,"battery":"7S","battery_mAh":2500,"prop_size":8.0,"pitch":3.5,"blades":2,"style":"longrange","motor_kv":900},
    # 10"+ Ultra LR
    "10_6s_lr":        {"label":"10\" 6S Long Range Classic","class":"long_range","size":10.0,"weight":1800,"battery":"6S","battery_mAh":4000,"prop_size":10.0,"pitch":4.5,"blades":2,"style":"longrange","motor_kv":800},
    "10_6s_heavy":     {"label":"10\" 6S Heavy Lifter","class":"long_range","size":10.0,"weight":2200,"battery":"6S","battery_mAh":5000,"prop_size":10.0,"pitch":4.5,"blades":2,"style":"longrange","motor_kv":700},
    "10_7s_ultra":     {"label":"10\" 7S Ultra Range","class":"long_range","size":10.0,"weight":1900,"battery":"7S","battery_mAh":3500,"prop_size":10.0,"pitch":4.5,"blades":2,"style":"longrange","motor_kv":750},
    "12_6s_ultra":     {"label":"12\" 6S Ultra LR","class":"ultra_lr","size":12.0,"weight":2500,"battery":"6S","battery_mAh":6000,"prop_size":12.0,"pitch":5.0,"blades":2,"style":"longrange","motor_kv":600},
}

def detect_class_from_size(size):
    try: s = float(size)
    except: return "freestyle", DRONE_CLASSES["freestyle"]
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        if lo <= s <= hi: return cls, meta
    best, best_dist = None, None
    for cls, meta in DRONE_CLASSES.items():
        lo, hi = meta["size_range"]
        dist = abs((lo+hi)/2.0 - s)
        if best is None or dist < best_dist: best, best_dist = cls, dist
    return best, DRONE_CLASSES[best]

def get_baseline_for_class(cls_key, battery="4S"):
    bkey = _pick_baseline_key(cls_key, battery)
    data = BASELINE_CTRL.get(bkey) or BASELINE_CTRL.get(cls_key, {})
    pid_axes = data.get("pid", {})
    flt = data.get("filter", {})
    roll = pid_axes.get("roll", {"P":48,"I":90,"D":38})
    return {
        "pid":{"P":roll["P"],"I":roll["I"],"D":roll.get("D",0)},
        "pid_axes":pid_axes,
        "filter":{"gyro_cutoff":flt.get("gyro_lpf1"),"gyro_lpf1":flt.get("gyro_lpf1"),"gyro_lpf2":flt.get("gyro_lpf2","--"),"dterm_lowpass":flt.get("dterm_lpf1"),"dterm_lpf1":flt.get("dterm_lpf1"),"dterm_lpf2":flt.get("dterm_lpf2","--"),"dyn_notch":flt.get("dyn_notch_count",2),"dyn_notch_min":flt.get("dyn_notch_min"),"dyn_notch_max":flt.get("dyn_notch_max"),"rpm_filter":flt.get("rpm_filter",True),"anti_gravity":flt.get("anti_gravity",5)},
        "notes":data.get("notes",""),
    }

def get_preset_groups():
    groups = {}
    for key, p in PRESETS.items():
        s = p.get("size",0)
        if s<=2.5: g="🐜 Nano/Micro"
        elif s<=3.5: g="🪲 Whoop/Cine"
        elif s<=4.5: g="🐝 Mini 4\""
        elif s<=5.5: g="🚀 5\" All-S"
        elif s<=6.5: g="⚡ 6\" Heavy"
        elif s<=7.5: g="🌍 7\" Mid-LR"
        elif s<=9.0: g="🛰️ 8\" LR"
        else: g="🌏 10\"+ Ultra"
        groups.setdefault(g,[]).append((key,p.get("label",key)))
    return groups
