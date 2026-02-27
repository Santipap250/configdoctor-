# app.py - OBIXConfig Doctor (v1.0.1beta - patched)
# ============================================================
# FIXES APPLIED:
# [FIX-1]  All Flask/stdlib imports moved to top of file
#           (was: jsonify/send_file imported on line 602 AFTER
#            /analyze_cli route that uses jsonify → NameError at runtime)
# [FIX-2]  _normalize_style() — maps preset styles like "micro",
#           "whoop","cine","mini","heavy" → "freestyle"/"racing"/"longrange"
#           (was: unknown styles silently fell into longrange PID baseline)
# [FIX-3]  analysis["size"], analysis["prop_size"], analysis["pitch"],
#           analysis["motor_kv"] now written to analysis dict after
#           baseline detection so rule_engine rules 5/6/8 can read them
# [FIX-4]  effect.setdefault() simplified (removed redundant double-get)
# [FIX-5]  Added /vtx-smartaudio route for vtx_smartaudio.html template
# [FIX-6]  hover_throttle in advanced_analysis wrapper already protected
#           by None-check in analyze() — confirmed safe, no change needed
# ============================================================

# ── All imports at the top (CRITICAL: was split mid-file) ──────────────────
from flask import (Flask, render_template, request, send_from_directory,
                   abort, send_file, jsonify, url_for)
from analyzer.prop_logic import analyze_propeller
from analyzer.thrust_logic import calculate_thrust_weight, estimate_battery_runtime
from logic.presets import PRESETS, detect_class_from_size, get_baseline_for_class
from datetime import datetime
from werkzeug.utils import secure_filename
from analyzer.cli_surgeon import analyze_dump as cli_analyze_dump
import os
import io
import time
import json
import hashlib
import logging

# ── Optional modules (graceful fallback) ─────────────────────────────────
try:
    from analyzer.rule_engine import evaluate_rules
except Exception as e:
    evaluate_rules = None
    print("rule_engine import failed:", e)

try:
    from analyzer.cli_export import build_cli_diff, build_snapshot_meta
    CLI_EXPORT_AVAILABLE = True
except Exception as e:
    CLI_EXPORT_AVAILABLE = False
    print("cli_export import failed:", e)
    def build_cli_diff(a): return "# cli_export not available"
    def build_snapshot_meta(a): return {}

try:
    from analyzer.advanced_analysis import make_advanced_report
    ADV_ANALYSIS_AVAILABLE = True
except Exception as e:
    print("advanced_analysis import failed:", e)
    def make_advanced_report(*args, **kwargs): return {"advanced": {}}
    ADV_ANALYSIS_AVAILABLE = False

# ── Style normalizer (FIX-2) ──────────────────────────────────────────────
# Preset styles like "micro","whoop","cine","mini","heavy" don't match the
# 3 valid styles that analyze_drone() and prop_logic understand.
_STYLE_MAP = {
    "micro":      "freestyle",
    "whoop":      "freestyle",
    "cine":       "longrange",
    "mini":       "freestyle",
    "heavy":      "freestyle",
    "heavy_5":    "freestyle",
    "mid_lr":     "longrange",
    "long_range": "longrange",
    "longrange":  "longrange",
    "racing":     "racing",
    "freestyle":  "freestyle",
}

def _normalize_style(s: str) -> str:
    """Return a canonical style string: freestyle | racing | longrange."""
    return _STYLE_MAP.get(str(s).lower().strip(), "freestyle")

# ── Cell string parser (shared helper) ───────────────────────────────────
def _cells_from_str(s):
    try:
        c = int(str(s).upper().replace("S", "").strip())
        return max(3, min(c, 8))
    except Exception:
        return None

# ── Flask app setup ───────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

FORCE_SECURE = os.environ.get("FORCE_SECURE", "0") in ("1", "true", "True")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=FORCE_SECURE,
)
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', '0') in ('1', 'true', 'True')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("configdoctor")

# ── Template filter ───────────────────────────────────────────────────────
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime_filter(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ''

# ══════════════════════════════════════════════════════════════════════════
# Input validation
# ══════════════════════════════════════════════════════════════════════════
def validate_input(size, weight, prop_size, pitch, blades, battery):
    warnings = []
    try:
        size = float(size)
    except Exception:
        warnings.append("ขนาด (size) ต้องเป็นตัวเลข")
        size = 0.0

    if not (1 <= size <= 15):
        warnings.append("ขนาดโดรนควรอยู่ระหว่าง 1–15 นิ้ว")

    try:
        weight = float(weight)
        if weight <= 0 or weight > 8000:
            warnings.append("น้ำหนักโดรนควรอยู่ระหว่าง 1–8000 กรัม")
    except Exception:
        warnings.append("น้ำหนัก (weight) ต้องเป็นตัวเลข")

    try:
        prop_size = float(prop_size)
        if prop_size > (size + 4):
            warnings.append("ขนาดใบพัดดูใหญ่กว่าปกติสำหรับเฟรมที่ระบุ")
    except Exception:
        pass

    try:
        pitch = float(pitch)
        if not (1.5 <= pitch <= 8.0):
            warnings.append("Pitch ใบพัดอยู่นอกช่วงที่ใช้ทั่วไป")
    except Exception:
        pass

    try:
        blades = int(blades)
        if blades not in (2, 3, 4):
            warnings.append("จำนวนใบพัดควรเป็น 2, 3 หรือ 4")
    except Exception:
        warnings.append("จำนวนใบพัด (blades) ต้องเป็นจำนวนเต็ม")

    try:
        cells = _cells_from_str(battery)
        if cells is None or cells < 3 or cells > 8:
            warnings.append("แบตควรอยู่ในช่วง 3S ถึง 8S")
    except Exception:
        warnings.append("แบตรูปแบบผิด (เช่น 3S, 4S, 6S, 8S)")

    return warnings

# ══════════════════════════════════════════════════════════════════════════
# Weight classifier
# ══════════════════════════════════════════════════════════════════════════
def classify_weight(size, weight):
    try:
        size = float(size)
        weight = float(weight)
    except Exception:
        return "ไม่ระบุ"
    if size >= 5:
        if weight < 650:   return "เบา"
        if weight <= 900:  return "กลาง"
        return "หนัก"
    return "ไม่ระบุ"

# ══════════════════════════════════════════════════════════════════════════
# Core analysis function
# ══════════════════════════════════════════════════════════════════════════
def analyze_drone(size, battery, style, prop_result, weight):
    """style must be a normalized value: freestyle | racing | longrange"""
    analysis = {}
    try:
        sz = float(size)
    except Exception:
        sz = size

    analysis["overview"] = (
        f'โดรน {sz}" แบต {battery}, สไตล์ {style}, '
        f'ใบพัด: {prop_result.get("summary", "-") if isinstance(prop_result, dict) else "-"}'
    )
    analysis["weight_class"] = classify_weight(size, weight)
    analysis["basic_tips"] = [
        "ตรวจสอบใบพัดไม่บิดงอ",
        "ขันน็อตมอเตอร์ให้แน่น",
        "เช็คจุดบัดกรี ESC และแบตเตอรี่",
    ]

    if style == "freestyle":
        pid = {"roll": {"p":48,"i":52,"d":38}, "pitch": {"p":48,"i":52,"d":38}, "yaw": {"p":40,"i":45,"d":0}}
        filter_desc = {"gyro_lpf2": 90, "dterm_lpf1": 120, "dyn_notch": 2}
        extra_tips = ["Freestyle — ตอบสนองไว สมดุล"]
    elif style == "racing":
        pid = {"roll": {"p":55,"i":45,"d":42}, "pitch": {"p":55,"i":45,"d":42}, "yaw": {"p":50,"i":40,"d":0}}
        filter_desc = {"gyro_lpf2": 120, "dterm_lpf1": 150, "dyn_notch": 3}
        extra_tips = ["Racing — ตอบสนองสูง"]
    else:  # longrange / default
        pid = {"roll": {"p":42,"i":50,"d":32}, "pitch": {"p":42,"i":50,"d":32}, "yaw": {"p":35,"i":45,"d":0}}
        filter_desc = {"gyro_lpf2": 70, "dterm_lpf1": 90, "dyn_notch": 1}
        extra_tips = ["Long Range — นิ่ง ประหยัดไฟ"]

    analysis["pid"] = pid
    analysis["filter"] = filter_desc
    analysis["extra_tips"] = extra_tips

    try:
        motor_load = prop_result.get("effect", {}).get("motor_load", 0)
        analysis["thrust_ratio"] = calculate_thrust_weight(motor_load, float(weight))
    except Exception:
        analysis["thrust_ratio"] = 0

    try:
        analysis["battery_est"] = estimate_battery_runtime(weight, battery)
    except Exception:
        analysis["battery_est"] = 0

    return analysis

# ══════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════
@app.route('/fpv')
def fpv_hub():
    return render_template('fpv/index.html')

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/")
def loading():
    return render_template("loading.html")

@app.route("/ping")
def ping():
    return "pong"

@app.route("/app", methods=["GET", "POST"])
def index():
    analysis = None

    if request.method == "POST":
        def safe_float(x, default=0.0):
            try: return float(x)
            except Exception: return default

        def safe_int(x, default=0):
            try: return int(x)
            except Exception: return default

        # ── Read form inputs ─────────────────────────────────────────
        preset_key  = request.form.get("preset", "").strip()
        size        = safe_float(request.form.get("size"), 5.0)
        battery     = request.form.get("battery", "4S")
        style_raw   = request.form.get("style", "freestyle")
        weight      = safe_float(request.form.get("weight"), 1000.0)
        prop_size   = safe_float(request.form.get("prop_size"), 5.0)
        blade_count = safe_int(request.form.get("blades"), 3)
        prop_pitch  = safe_float(request.form.get("pitch"), 4.0)

        battery_mAh       = safe_int(request.form.get("battery_mAh"), None)
        motor_count       = safe_int(request.form.get("motor_count"), 4)

        payload_g = None
        try:
            pg = request.form.get("payload_g")
            payload_g = float(pg) if pg not in (None, "", "None") else None
        except Exception:
            payload_g = None

        prop_thrust_g = None
        try:
            pth = request.form.get("prop_thrust_g")
            prop_thrust_g = float(pth) if pth not in (None, "", "None") else None
        except Exception:
            prop_thrust_g = None

        motor_kv = safe_int(request.form.get("motor_kv"), None)

        esc_current_limit_a = None
        try:
            ecil = request.form.get("esc_current_limit_a")
            esc_current_limit_a = float(ecil) if ecil not in (None, "", "None") else None
        except Exception:
            esc_current_limit_a = None

        # ── Override from preset ──────────────────────────────────────
        if preset_key:
            p = PRESETS.get(preset_key)
            if p:
                size        = float(p.get("size",       size))
                battery     = p.get("battery",           battery)
                style_raw   = p.get("style",             style_raw)
                weight      = float(p.get("weight",      weight))
                prop_size   = float(p.get("prop_size",   prop_size))
                prop_pitch  = float(p.get("pitch",       prop_pitch))
                blade_count = int(p.get("blades",        blade_count))

        # ── Normalize style (FIX-2) ───────────────────────────────────
        style = _normalize_style(style_raw)

        # ── Validation ───────────────────────────────────────────────
        warnings = validate_input(size, weight, prop_size, prop_pitch, blade_count, battery)

        # ── Prop analysis ─────────────────────────────────────────────
        try:
            prop_result = analyze_propeller(prop_size, prop_pitch, blade_count, style)
        except Exception:
            prop_result = {
                "summary": "prop analysis not available",
                "effect": {"motor_load": 0, "noise": 0, "grip": "unknown", "efficiency": "unknown"},
                "recommendation": "",
            }

        # ── Core analysis ─────────────────────────────────────────────
        try:
            analysis = analyze_drone(size, battery, style, prop_result, weight)
        except Exception:
            analysis = {
                "style": style, "weight_class": "unknown", "thrust_ratio": 0,
                "flight_time": 0, "summary": "analysis fallback", "basic_tips": [],
            }

        # ── Drone class + baseline ────────────────────────────────────
        try:
            cls_det = detect_class_from_size(size)
            detected_class, class_meta = (cls_det[0], cls_det[1]) if isinstance(cls_det, (tuple, list)) else (cls_det, {})
        except Exception:
            detected_class, class_meta = "unknown", {}

        baseline_ctrl  = get_baseline_for_class(detected_class) or {}
        pid_baseline   = baseline_ctrl.get("pid", {})
        filter_baseline = baseline_ctrl.get("filter", {})

        P = pid_baseline.get("P", pid_baseline.get("p", 0))
        I = pid_baseline.get("I", pid_baseline.get("i", 0))
        D = pid_baseline.get("D", pid_baseline.get("d", 0))

        analysis["preset_used"]      = preset_key or "custom"
        analysis["detected_class"]   = detected_class
        analysis["class_meta"]       = class_meta
        analysis["baseline_control"] = baseline_ctrl
        analysis["pid_baseline"] = {
            "roll":  {"p": P, "i": I, "d": D},
            "pitch": {"p": P, "i": I, "d": D},
            "yaw":   {"p": int(P * 0.6) if P else 0, "i": int(I * 0.6) if I else 0, "d": 0},
        }
        analysis["filter_baseline"] = {
            "gyro_lpf2":  filter_baseline.get("gyro_cutoff",   filter_baseline.get("gyro_lpf2")),
            "dterm_lpf1": filter_baseline.get("dterm_lowpass", filter_baseline.get("dterm_lpf1")),
            "dyn_notch":  filter_baseline.get("notch",         filter_baseline.get("dyn_notch")),
        }
        analysis.setdefault("style",   style)
        analysis.setdefault("summary", analysis.get("overview", ""))

        # ── FIX-3: Store input fields so rule_engine can access them ──
        analysis["size"]      = size
        analysis["prop_size"] = prop_size
        analysis["pitch"]     = prop_pitch
        analysis["motor_kv"]  = motor_kv

        # ── Rule engine ───────────────────────────────────────────────
        if evaluate_rules:
            try:
                analysis["rules"] = evaluate_rules(analysis)
            except Exception:
                logger.exception("Rule engine error")
                analysis["rules"] = []
        else:
            analysis["rules"] = []

        # ── Advanced analysis ─────────────────────────────────────────
        if ADV_ANALYSIS_AVAILABLE:
            try:
                adv = make_advanced_report(
                    size=float(size),
                    weight_g=float(weight),
                    battery_s=battery,
                    prop_result=prop_result,
                    style=style,
                    battery_mAh=battery_mAh,
                    motor_count=motor_count,
                    measured_thrust_per_motor_g=prop_thrust_g,
                    motor_kv=motor_kv,
                    esc_current_limit_a=esc_current_limit_a,
                    blades=blade_count,
                    payload_g=payload_g,
                )
                if isinstance(adv, dict):
                    analysis.update(adv)
                    adv_power = adv.get("advanced", {}).get("power", {})
                    analysis["thrust_ratio"]          = adv.get("advanced", {}).get("thrust_ratio", analysis.get("thrust_ratio", 0))
                    analysis["est_flight_time_min"]   = adv_power.get("est_flight_time_min", analysis.get("battery_est"))
                    analysis["est_flight_time_min_aggr"] = adv_power.get("est_flight_time_min_aggressive")
            except Exception:
                logger.exception("Advanced analysis error")

        # ── Normalize warnings to [{level,msg}] ──────────────────────
        norm_warnings = []
        for w in warnings:
            if isinstance(w, dict):
                norm_warnings.append({"level": w.get("level", "warning"), "msg": w.get("msg", str(w))})
            else:
                norm_warnings.append({"level": "warning", "msg": str(w)})
        analysis["warnings"] = norm_warnings

        # ── FIX-4: Simplified setdefault (was double-get pattern) ─────
        effect = prop_result.get("effect", {})
        effect.setdefault("motor_load", 0)
        effect.setdefault("noise",      0)
        effect.setdefault("grip",       "unknown")
        prop_result["effect"] = effect
        analysis["prop_result"] = prop_result

        logger.info("analysis keys: %s", list(analysis.keys()))

    return render_template("index.html", analysis=analysis)

# About & changelog
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/changelog")
def changelog():
    return render_template("changelog.html")

# ── Downloads ─────────────────────────────────────────────────────────────
@app.route('/downloads/<fc>/<filename>')
def download_diff(fc, filename):
    safe_fc = secure_filename(fc)
    safe_fn = secure_filename(filename)
    base_root = os.path.realpath(os.path.join(app.root_path, 'static', 'downloads', 'diff_all'))

    if not safe_fc:
        abort(404)

    candidate_fc_dir = os.path.realpath(os.path.join(base_root, safe_fc))
    if not (candidate_fc_dir.startswith(base_root + os.sep) and os.path.isdir(candidate_fc_dir)):
        logger.warning("Invalid fc dir: %s", candidate_fc_dir)
        abort(404)

    file_path = os.path.realpath(os.path.join(candidate_fc_dir, safe_fn))
    if not file_path.startswith(candidate_fc_dir + os.sep):
        logger.warning("Path traversal attempt: %s/%s", fc, filename)
        abort(404)
    if not os.path.isfile(file_path):
        abort(404)

    return send_from_directory(candidate_fc_dir, safe_fn, as_attachment=True)

@app.route('/downloads')
def downloads_index():
    base = os.path.realpath(os.path.join(app.root_path, 'static', 'downloads', 'diff_all'))
    items = []
    if os.path.isdir(base):
        for fc in sorted(os.listdir(base)):
            fcdir = os.path.realpath(os.path.join(base, fc))
            if not os.path.isdir(fcdir):
                continue
            for fn in sorted(os.listdir(fcdir)):
                path = os.path.join(fcdir, fn)
                if not os.path.isfile(path):
                    continue
                size = os.path.getsize(path)
                mtime = int(os.path.getmtime(path))
                hobj = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        hobj.update(chunk)
                items.append({'fc': fc, 'filename': fn, 'size': size, 'mtime': mtime, 'sha': hobj.hexdigest()[:16]})
    return render_template('downloads.html', items=items)

# ── VTX routes ────────────────────────────────────────────────────────────
@app.route("/vtx")
def vtx():
    return render_template("vtx.html")

@app.route("/vtx-range")
def vtx_range():
    return render_template("vtx_range.html")

# FIX-5: Added missing route for vtx_smartaudio.html
@app.route("/vtx-smartaudio")
def vtx_smartaudio():
    return render_template("vtx_smartaudio.html")

# ── Motor × Prop recommender ──────────────────────────────────────────────
def _recommend_motor_prop(form):
    try:
        size         = float(form.get('size')        or 5.0)
        weight_g     = float(form.get('weight')      or 900)
        battery      = form.get('battery')           or "4S"
        battery_mAh  = int(form.get('battery_mAh')  or 1500)
        prop_size    = float(form.get('prop_size')   or 5.0)
        blades       = int(form.get('blades')        or 3)
        pitch        = float(form.get('pitch')       or 4.0)
        motor_count  = int(form.get('motor_count')   or 4)
        # FIX: normalize style for motor-prop page too
        style        = _normalize_style(form.get('style') or 'freestyle')
    except Exception:
        size = 5.0; weight_g = 900; battery = "4S"; battery_mAh = 1500
        prop_size = 5.0; blades = 3; pitch = 4.0; motor_count = 4; style = 'freestyle'

    try:
        cells = int(str(battery).upper().replace('S', ''))
    except Exception:
        cells = 4

    target_twr = {'racing': 2.2, 'freestyle': 2.0}.get(style, 1.6)

    total_thrust_g  = max(1.0, weight_g * target_twr)
    thrust_per_motor = total_thrust_g / max(1, motor_count)

    if prop_size <= 3.5:
        stator = "1104–1407 (micro/whoop)"
        kv_hint = {3:4000, 4:3500, 5:3000, 6:2600, 7:2200, 8:2000}
    elif prop_size <= 4.5:
        stator = "1407–1806 (light 3–4\")"
        kv_hint = {3:3500, 4:3000, 5:2600, 6:2200, 7:2000, 8:1800}
    elif prop_size <= 5.5:
        stator = "1806–2207 (5\")"
        kv_hint = {3:3000, 4:2500, 5:2000, 6:1700, 7:1500, 8:1200}
    elif prop_size <= 7.0:
        stator = "2207–2408 (6\")"
        kv_hint = {3:2600, 4:2200, 5:1800, 6:1500, 7:1200, 8:1000}
    else:
        stator = "big stator (7–10\")"
        kv_hint = {3:2200, 4:1800, 5:1500, 6:1200, 7:1000, 8:900}

    # Safe KV lookup: clamp cells to available range
    available_cells = sorted(kv_hint.keys())
    nearest_cell = min(available_cells, key=lambda c: abs(c - cells))
    base_kv = kv_hint.get(cells, kv_hint[nearest_cell])

    kv_range = f"{int(base_kv * 0.75)}–{int(base_kv * 1.25)} KV"

    style_power  = {'freestyle': 550.0, 'racing': 700.0, 'longrange': 300.0}
    p_per_kg     = style_power.get(style, 500.0)
    est_hover_w  = p_per_kg * (weight_g / 1000.0)
    pack_v       = cells * 3.7
    est_current  = round(est_hover_w / max(0.1, pack_v), 2)
    batt_wh      = (battery_mAh / 1000.0) * pack_v
    avg_power    = est_hover_w * 1.1
    est_flight   = int(max(0, round((batt_wh / max(0.1, avg_power)) * 60.0)))

    tips = []
    if thrust_per_motor < 200:
        tips.append("มอเตอร์โหลดต่ำ — อาจโอเวอร์พาวเวอร์สำหรับเฟรมขนาดเล็ก")
    if thrust_per_motor > 600:
        tips.append("มอเตอร์ถูกโหลดสูง — เลือกสเตเตอร์ใหญ่ขึ้นหรือใบพัดขนาดใหญ่ขึ้น")
    if cells >= 7 and base_kv > 1600:
        tips.append("ระวัง KV สูงบนแรงดันสูง (7S+) — อาจทำให้มอเตอร์ร้อน")
    tips.append("เริ่มจากค่าแนะนำแล้วปรับจูนจริงขณะบิน")

    sample_cli = (
        f"# OBIX: motor×prop sample (for {cells}S)\n"
        f"set throttle_limit_percent = {'90' if style=='freestyle' else '80'}\n"
        f"# Recommended stator: {stator}\n"
        f"# KV range: {kv_range}\n"
        "save\n"
    )

    return {
        "twr_display":       f"{round(total_thrust_g/weight_g, 2)} (target {target_twr})",
        "total_thrust_g":    int(total_thrust_g),
        "thrust_per_motor":  int(thrust_per_motor),
        "kv_range":          kv_range,
        "stator":            stator,
        "est_current_a":     est_current,
        "est_flight_time_min": est_flight,
        "tips":              tips,
        "sample_cli":        sample_cli,
    }

@app.route('/motor-prop', methods=['GET', 'POST'])
def motor_prop():
    if request.method == 'POST':
        result = _recommend_motor_prop(request.form)
        return render_template('motor_prop.html', result=result)
    return render_template('motor_prop.html')

# ── CLI Surgeon ───────────────────────────────────────────────────────────
@app.route('/cli_surgeon')
def cli_surgeon_page():
    return render_template('cli_surgeon.html')

@app.route('/analyze_cli', methods=['POST'])
def analyze_cli():
    try:
        data = request.get_json(force=True)
        dump = data.get('dump', '')
        if not dump:
            return jsonify({"error": "no dump provided"}), 400
        result = cli_analyze_dump(dump)
        return jsonify(result)
    except Exception as e:
        logger.exception("analyze_cli error")
        return jsonify({"error": str(e)}), 500

# ── OSD Designer ──────────────────────────────────────────────────────────
@app.route('/osd')
def osd_page():
    return render_template('osd.html')

def _timestamped_filename(prefix="obix_osd", ext="txt"):
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}.{ext}"

def _generate_osd_text_from_model(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=2)

def _generate_cli_from_model(model: dict) -> str:
    lines = ["# OBIXConfig pseudo CLI export"]
    for i, it in enumerate(model.get('items', []), start=1):
        lines.append(f"// {i}. {it.get('type')} '{it.get('label')}' @{it.get('x')},{it.get('y')} size={it.get('size')}")
        lines.append(f"// command: osd_add {it.get('type')} {it.get('x')} {it.get('y')} \"{it.get('label')}\" size={it.get('size')}")
    return "\n".join(lines)

@app.route('/osd/export', methods=['POST'])
def osd_export():
    fmt      = (request.args.get('format') or 'txt').lower()
    save_flag = str(request.args.get('save', '0')).lower() in ('1', 'true', 'yes')

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return ("Invalid JSON payload", 400)

    if fmt == 'cli':
        content, ext = _generate_cli_from_model(data), 'cli.txt'
    elif fmt == 'json':
        content, ext = json.dumps(data, ensure_ascii=False, indent=2), 'json'
    else:
        content, ext = _generate_osd_text_from_model(data), 'txt'

    if save_flag:
        out_dir = os.path.join(app.root_path, 'static', 'downloads', 'osd')
        os.makedirs(out_dir, exist_ok=True)
        fname = secure_filename(_timestamped_filename(prefix="obix_osd", ext=ext))
        path  = os.path.join(out_dir, fname)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return (f"Failed to save file: {e}", 500)
        return jsonify({"ok": True, "download_url": url_for('static', filename=f'downloads/osd/{fname}'), "filename": fname})

    buf = io.BytesIO()
    buf.write(content.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='text/plain', as_attachment=True, download_name=f"obix_osd.{ext}")

# ── Error handlers ────────────────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

@app.route("/healthz")
def healthz():
    return {"status": "ok", "advanced_analysis": bool(ADV_ANALYSIS_AVAILABLE)}

# ── Dev server ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=app.config.get('DEBUG', False),
    )
