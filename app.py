# app.py - improved for configdoctor
from flask import Flask, render_template, request, send_from_directory, abort
from analyzer.prop_logic import analyze_propeller
from analyzer.thrust_logic import calculate_thrust_weight, estimate_battery_runtime
from logic.presets import PRESETS, detect_class_from_size, get_baseline_for_class
from datetime import datetime
import os
import hashlib
import logging
from werkzeug.utils import secure_filename

# optional modules (lazy / tolerant)
try:
    from analyzer.rule_engine import evaluate_rules
except Exception as e:
    evaluate_rules = None
    print("rule_engine import failed:", e)

try:
    from analyzer.advanced_analysis import make_advanced_report
    ADV_ANALYSIS_AVAILABLE = True
except Exception as e:
    print("advanced_analysis import failed:", e)
    def make_advanced_report(*args, **kwargs):
        return {"advanced": {}}
    ADV_ANALYSIS_AVAILABLE = False

# helper: แปลง "4S" -> int cells (3..8)
def _cells_from_str(s):
    try:
        c = int(str(s).upper().replace("S","").strip())
        if c < 3:
            return 3
        if c > 8:
            return 8
        return c
    except Exception:
        return None

# app setup
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("configdoctor")

# template helper
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime_filter(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ''

# ===============================
# Validation helper
# ===============================
def validate_input(size, weight, prop_size, pitch, blades, battery):
    warnings = []
    # normalize numeric inputs as far as possible
    try:
        size = float(size)
    except Exception:
        warnings.append("ขนาด (size) ต้องเป็นตัวเลข")
        size = 0.0

    # size range
    if not (1 <= size <= 10):
        warnings.append("ขนาดโดรนควรอยู่ระหว่าง 1–10 นิ้ว")

    # weight (single canonical check)
    try:
        weight = float(weight)
        if weight <= 0 or weight > 30000:
            warnings.append("น้ำหนักโดรนควรอยู่ระหว่าง 1–30000 กรัม")
    except Exception:
        warnings.append("น้ำหนัก (weight) ต้องเป็นตัวเลข")

    # prop size sanity
    try:
        prop_size = float(prop_size)
        if prop_size > (size + 4):
            warnings.append("ขนาดใบพัดดูใหญ่กว่าปกติสำหรับเฟรมที่ระบุ")
    except Exception:
        pass

    # pitch sanity
    try:
        pitch = float(pitch)
        if not (1.5 <= pitch <= 8.0):
            warnings.append("Pitch ใบพัดอยู่นอกช่วงที่ใช้ทั่วไป")
    except Exception:
        pass

    # blades
    try:
        blades = int(blades)
        if blades not in (2,3,4):
            warnings.append("จำนวนใบพัดควรเป็น 2, 3 หรือ 4")
    except Exception:
        warnings.append("จำนวนใบพัด (blades) ต้องเป็นจำนวนเต็ม")

    # battery cells (use helper)
    try:
        cells = _cells_from_str(battery)
        if cells is None or cells < 3 or cells > 8:
            warnings.append("แบตควรอยู่ในช่วง 3S ถึง 8S")
    except Exception:
        warnings.append("แบตรูปแบบผิด (เช่น 3S, 4S, 6S, 8S)")

    return warnings

# ===============================
# classify weight
# ===============================
def classify_weight(size, weight):
    try:
        size = float(size)
        weight = float(weight)
    except Exception:
        return "ไม่ระบุ"

    if size >= 5:
        if weight < 650:
            return "เบา"
        elif weight <= 900:
            return "กลาง"
        else:
            return "หนัก"
    return "ไม่ระบุ"

# ===============================
# main analyze_drone (simple baseline)
# ===============================
def analyze_drone(size, battery, style, prop_result, weight):
    analysis = {}
    try:
        sz = float(size)
    except Exception:
        sz = size

    analysis["overview"] = f'โดรน {sz}" แบต {battery}, สไตล์ {style}, ใบพัด: {prop_result.get("summary","-") if isinstance(prop_result, dict) else "-"}'
    analysis["weight_class"] = classify_weight(size, weight)
    analysis["basic_tips"] = [
        "ตรวจสอบใบพัดไม่บิดงอ",
        "ขันน็อตมอเตอร์ให้แน่น",
        "เช็คจุดบัดกรี ESC และแบตเตอรี่"
    ]

    # baseline PID/filter per style
    if style == "freestyle":
        pid = {"roll":{"p":48,"i":52,"d":38},"pitch":{"p":48,"i":52,"d":38},"yaw":{"p":40,"i":45,"d":0}}
        filter_desc = {"gyro_lpf2":90,"dterm_lpf1":120,"dyn_notch":2}
        extra_tips = ["Freestyle — ตอบสนองไว สมดุล"]
    elif style == "racing":
        pid = {"roll":{"p":55,"i":45,"d":42},"pitch":{"p":55,"i":45,"d":42},"yaw":{"p":50,"i":40,"d":0}}
        filter_desc = {"gyro_lpf2":120,"dterm_lpf1":150,"dyn_notch":3}
        extra_tips = ["Racing — ตอบสนองสูง"]
    else:
        pid = {"roll":{"p":42,"i":50,"d":32},"pitch":{"p":42,"i":50,"d":32},"yaw":{"p":35,"i":45,"d":0}}
        filter_desc = {"gyro_lpf2":70,"dterm_lpf1":90,"dyn_notch":1}
        extra_tips = ["Long Range — นิ่ง ประหยัดไฟ"]

    analysis["pid"] = pid
    analysis["filter"] = filter_desc
    analysis["extra_tips"] = extra_tips

    # thrust_ratio (best-effort)
    try:
        motor_load = prop_result.get("effect", {}).get("motor_load", 0)
        analysis["thrust_ratio"] = calculate_thrust_weight(motor_load, float(weight))
    except Exception:
        analysis["thrust_ratio"] = 0

    # battery estimate fallback
    try:
        analysis["battery_est"] = estimate_battery_runtime(weight, battery)
    except Exception:
        analysis["battery_est"] = 0

    return analysis

# ===============================
# ROUTES
# ===============================
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
        # helpers
        def safe_float(x, default=0.0):
            try: return float(x)
            except Exception: return default
        def safe_int(x, default=0):
            try: return int(x)
            except Exception: return default

        # read inputs
        preset_key = request.form.get("preset", "").strip()
        size = safe_float(request.form.get("size"), 5.0)
        battery = request.form.get("battery", "4S")
        style = request.form.get("style", "freestyle")
        weight = safe_float(request.form.get("weight"), 1000.0)
        prop_size = safe_float(request.form.get("prop_size"), 5.0)
        blade_count = safe_int(request.form.get("blades"), 3)
        prop_pitch = safe_float(request.form.get("pitch"), 4.0)

        # optional extras
        battery_mAh = safe_int(request.form.get("battery_mAh"), None)
        motor_count = safe_int(request.form.get("motor_count"), 4)
        payload_g = None
        try:
            pg = request.form.get("payload_g", None)
            payload_g = float(pg) if pg not in (None, "", "None") else None
        except Exception:
            payload_g = None

        prop_thrust_g = None
        try:
            pth = request.form.get("prop_thrust_g", None)
            prop_thrust_g = float(pth) if pth not in (None, "", "None") else None
        except Exception:
            prop_thrust_g = None

        motor_kv = safe_int(request.form.get("motor_kv"), None)
        esc_current_limit_a = None
        try:
            ecil = request.form.get("esc_current_limit_a", None)
            esc_current_limit_a = float(ecil) if ecil not in (None, "", "None") else None
        except Exception:
            esc_current_limit_a = None

        # override preset
        if preset_key:
            p = PRESETS.get(preset_key)
            if p:
                size = float(p.get("size", size))
                battery = p.get("battery", battery)
                style = p.get("style", style)
                weight = float(p.get("weight", weight))
                prop_size = float(p.get("prop_size", prop_size))
                prop_pitch = float(p.get("pitch", prop_pitch))
                blade_count = int(p.get("blades", blade_count))

        # validation
        warnings = validate_input(size, weight, prop_size, prop_pitch, blade_count, battery)

        # prop analysis
        try:
            prop_result = analyze_propeller(prop_size, prop_pitch, blade_count, style)
        except Exception:
            prop_result = {"summary": "prop analysis not available", "effect": {"motor_load": 0, "noise": 0}, "recommendation": ""}

        # main analysis baseline
        try:
            analysis = analyze_drone(size, battery, style, prop_result, weight)
        except Exception:
            analysis = {"style": style, "weight_class": "unknown", "thrust_ratio":0, "flight_time":0, "summary":"analysis fallback", "basic_tips":[]}

        # detect class & baseline
        try:
            cls_det = detect_class_from_size(size)
            if isinstance(cls_det, (tuple, list)):
                detected_class, class_meta = cls_det[0], cls_det[1]
            else:
                detected_class = cls_det
                class_meta = {}
        except Exception:
            detected_class = "unknown"
            class_meta = {}

        baseline_ctrl = get_baseline_for_class(detected_class) or {}
        pid_baseline = baseline_ctrl.get("pid", {})
        filter_baseline = baseline_ctrl.get("filter", {})

        P = pid_baseline.get("P", pid_baseline.get("p", 0))
        I = pid_baseline.get("I", pid_baseline.get("i", 0))
        D = pid_baseline.get("D", pid_baseline.get("d", 0))

        analysis["preset_used"] = preset_key or "custom"
        analysis["detected_class"] = detected_class
        analysis["class_meta"] = class_meta
        analysis["baseline_control"] = baseline_ctrl
        analysis["pid_baseline"] = {
            "roll": {"p": P, "i": I, "d": D},
            "pitch": {"p": P, "i": I, "d": D},
            "yaw": {"p": int(P * 0.6) if P else 0, "i": int(I * 0.6) if I else 0, "d": 0}
        }
        analysis["filter_baseline"] = {
            "gyro_lpf2": filter_baseline.get("gyro_cutoff", filter_baseline.get("gyro_lpf2")),
            "dterm_lpf1": filter_baseline.get("dterm_lowpass", filter_baseline.get("dterm_lpf1")),
            "dyn_notch": filter_baseline.get("notch", filter_baseline.get("dyn_notch"))
        }

        analysis.setdefault("style", style)
        analysis.setdefault("summary", analysis.get("overview", ""))

        # ---- rule engine (optional) ----
        if evaluate_rules:
            try:
                analysis["rules"] = evaluate_rules(analysis)
            except Exception as e:
                logger.exception("Rule engine error")
                analysis["rules"] = []
        else:
            analysis["rules"] = []

        # ---- advanced analysis (optional) ----
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
                    payload_g=payload_g
                )
                if isinstance(adv, dict):
                    # merge safely - prefer existing analysis keys if missing in adv
                    analysis.update(adv)
                    adv_power = adv.get("advanced", {}).get("power", {})
                    analysis["thrust_ratio"] = adv.get("advanced", {}).get("thrust_ratio", analysis.get("thrust_ratio",0))
                    analysis["est_flight_time_min"] = adv_power.get("est_flight_time_min", analysis.get("battery_est"))
                    analysis["est_flight_time_min_aggr"] = adv_power.get("est_flight_time_min_aggressive", None)
            except Exception:
                logger.exception("Advanced analysis error")

        # normalize warnings => template expects list of {level,msg}
        norm_warnings = []
        for w in warnings:
            if isinstance(w, dict):
                lvl = w.get("level","warning")
                msg = w.get("msg", str(w))
            else:
                lvl = "warning"
                msg = str(w)
            norm_warnings.append({"level": lvl, "msg": msg})
        analysis["warnings"] = norm_warnings

        # ensure prop_result.effect keys
        effect = prop_result.get("effect", {})
        effect.setdefault("motor_load", effect.get("motor_load", 0))
        effect.setdefault("noise", effect.get("noise", 0))
        effect.setdefault("grip", effect.get("grip", "unknown"))
        prop_result["effect"] = effect
        analysis["prop_result"] = prop_result

        # debug log keys
        try:
            logger.info("analysis keys: %s", list(analysis.keys()))
        except Exception:
            pass

    # end POST handling
    return render_template("index.html", analysis=analysis)

# About & changelog
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/changelog")
def changelog():
    return render_template("changelog.html")

# Downloads
@app.route('/downloads/<fc>/<filename>')
def download_diff(fc, filename):
    safe_fc = secure_filename(fc)
    safe_fn = secure_filename(filename)

    base_root = os.path.realpath(os.path.join(app.root_path, 'static', 'downloads', 'diff_all'))
    base_dir = os.path.realpath(os.path.join(base_root, safe_fc))
    file_path = os.path.realpath(os.path.join(base_dir, safe_fn))

    # ensure requested file is under downloads root
    if not file_path.startswith(base_root + os.sep):
        abort(404)
    if not os.path.isfile(file_path):
        abort(404)

    return send_from_directory(base_dir, safe_fn, as_attachment=True)

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
                # chunked sha256
                hobj = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        hobj.update(chunk)
                h = hobj.hexdigest()[:16]
                items.append({'fc': fc, 'filename': fn, 'size': size, 'mtime': mtime, 'sha': h})
    return render_template('downloads.html', items=items)

# ===============================
# ROUTE: VTX (Band / Channel / Power guide)
# ===============================
@app.route("/vtx")
def vtx():
    # หากต้องการส่งข้อมูลไดนามิก ให้เติม context dict
    return render_template("vtx.html")

# --- Motor × Prop recommender helper + route ---
def _recommend_motor_prop(form):
    try:
        size = float(form.get('size') or 5.0)
        weight_g = float(form.get('weight') or 900)
        battery = form.get('battery') or "4S"
        battery_mAh = int(form.get('battery_mAh') or 1500)
        prop_size = float(form.get('prop_size') or 5.0)
        blades = int(form.get('blades') or 3)
        pitch = float(form.get('pitch') or 4.0)
        motor_count = int(form.get('motor_count') or 4)
        style = form.get('style') or 'freestyle'
    except Exception:
        size = 5.0; weight_g = 900; battery="4S"; battery_mAh=1500
        prop_size = 5.0; blades=3; pitch=4.0; motor_count=4; style='freestyle'

    try:
        cells = int(str(battery).upper().replace('S',''))
    except Exception:
        cells = 4

    # target TWR by style
    if style == 'racing':
        target_twr = 2.2
    elif style == 'freestyle':
        target_twr = 2.0
    else:
        target_twr = 1.6

    total_thrust_g = max(1.0, weight_g * target_twr)
    thrust_per_motor = total_thrust_g / max(1, motor_count)

    # stator / KV mapping (coarse)
    if prop_size <= 3.5:
        stator = "1104–1407 (micro/whoop)"
        kv_hint = {3:4000,4:3500,5:3000,6:2600,7:2200,8:2000}
    elif prop_size <= 4.5:
        stator = "1407–1806 (light 3-4\")"
        kv_hint = {3:3500,4:3000,5:2600,6:2200,7:2000,8:1800}
    elif prop_size <= 5.5:
        stator = "1806–2207 (5\")"
        kv_hint = {3:3000,4:2500,5:2000,6:1700,7:1500,8:1200}
    elif prop_size <= 7.0:
        stator = "2207–2408 (6\")"
        kv_hint = {3:2600,4:2200,5:1800,6:1500,7:1200,8:1000}
    else:
        stator = "big stator (7–10\")"
        kv_hint = {3:2200,4:1800,5:1500,6:1200,7:1000,8:900}

    base_kv = kv_hint.get(cells, kv_hint.get(4))
    low_kv = int(base_kv * 0.75)
    high_kv = int(base_kv * 1.25)
    kv_range = f"{low_kv}–{high_kv} KV"

    style_power = {'freestyle':550.0, 'racing':700.0, 'longrange':300.0}
    p_per_kg = style_power.get(style, 500.0)
    est_hover_power_w = (p_per_kg * (weight_g/1000.0))
    pack_v = cells * 3.7
    est_current_a = round(est_hover_power_w / max(0.1, pack_v), 2)

    batt_wh = (battery_mAh / 1000.0) * pack_v
    avg_power = est_hover_power_w * 1.1
    est_flight_time_min = int(max(0, round((batt_wh / max(0.1, avg_power)) * 60.0)))

    tips = []
    if thrust_per_motor < 200:
        tips.append("มอเตอร์โหลดต่ำ — อาจโอเวอร์พาวเวอร์สำหรับเฟรมขนาดเล็ก")
    if thrust_per_motor > 600:
        tips.append("มอเตอร์ถูกโหลดสูง — เลือกสเตเตอร์ใหญ่ขึ้นหรือใบพัดขนาดใหญ่ขึ้น")
    if cells >= 7 and base_kv > 1600:
        tips.append("ระวัง KV สูงบนแรงดันสูง (7S+) — อาจทำให้มอเตอร์ร้อน")
    tips.append("เริ่มจากค่าแนะนำแล้วปรับจูนจริงขณะบิน")

    sample_cli = f"""# OBIX: motor×prop sample (for {cells}S)
set throttle_limit_percent = {'90' if style=='freestyle' else '80'}
# Recommended stator: {stator}
# KV range: {kv_range}
save
"""

    result = {
        "twr_display": f"{round(total_thrust_g/weight_g,2)} (target {target_twr})",
        "total_thrust_g": int(total_thrust_g),
        "thrust_per_motor": int(thrust_per_motor),
        "kv_range": kv_range,
        "stator": stator,
        "est_current_a": est_current_a,
        "est_flight_time_min": est_flight_time_min,
        "tips": tips,
        "sample_cli": sample_cli
    }
    return result

@app.route('/motor-prop', methods=['GET','POST'])
def motor_prop():
    if request.method == 'POST':
        result = _recommend_motor_prop(request.form)
        return render_template('motor_prop.html', result=result)
    return render_template('motor_prop.html')

from flask import send_file, jsonify
import io, json

@app.route('/osd', methods=['GET', 'POST'])
def osd_designer():
    # GET: หน้าออกแบบ, POST: optional save preview request
    return render_template('osd.html')

@app.route('/osd/export', methods=['POST'])
def osd_export():
    # รับ JSON layout จาก client แล้วส่งไฟล์ .txt (หรือ JSON) ให้ดาวน์โหลด
    layout = request.get_json() or {}
    # สร้าง Betaflight OSD layout string (ตัวอย่างง่าย)
    # ให้ผู้ใช้แก้ template นี้ต่อได้
    bf_lines = []
    bf_lines.append('# OBIX OSD export')
    bf_lines.append(f'# width:{layout.get("width",640)} height:{layout.get("height",480)}')
    for item in layout.get('items', []):
        bf_lines.append(f'osd add {item["type"]} {item["x"]} {item["y"]} {item.get("options","")}')
    bf_content = "\n".join(bf_lines)
    buf = io.BytesIO(bf_content.encode('utf-8'))
    buf.seek(0)
    return send_file(buf,
                     as_attachment=True,
                     download_name="obix_osd_layout.txt",
                     mimetype="text/plain")

# app.py — เพิ่มส่วนนี้ (วางใต้ route /osd หรือข้างๆ routes downloads)
import io
import json
from flask import make_response

def _generate_osd_text_from_model(model: dict) -> str:
    """
    แปลง model -> plain text (human readable) + pseudo-CLI lines.
    (ปรับให้ตรง Betaflight CLI ได้ภายหลัง)
    """
    lines = []
    lines.append("# OBIXConfig OSD export")
    lines.append("# Generated by OBIXConfig Doctor")
    lines.append("")
    w = model.get("width", 360)
    h = model.get("height", 240)
    lines.append(f"# Screen: {w}x{h}")
    lines.append("")

    items = model.get("items", [])
    for i, it in enumerate(items, start=1):
        it_type = it.get("type", "unknown")
        label = it.get("label", "")
        x = it.get("x", 0)
        y = it.get("y", 0)
        size = it.get("size", 14)
        color = it.get("color", "#ffffff")
        lines.append(f"# Item {i}: {it_type} '{label}' @ ({x},{y}) size={size} color={color}")
        # pseudo CLI line (informational) — จะต้องแมปจริงกับ Betaflight ถ้าต้องการตรงๆ
        lines.append(f'cli_add_item type={it_type} x={x} y={y} text="{label}" size={size} color="{color}"')
        lines.append("")
    lines.append("# End of export")
    return "\n".join(lines)

@app.route("/osd/export", methods=["POST"])
def osd_export():
    """
    รับ JSON POST จากหน้า osd.html แล้วส่งไฟล์ .txt ให้ดาวน์โหลด
    ตัวอย่าง payload expected:
    { "width":360, "height":240, "items": [ {id,type,label,x,y,size,color,options}, ... ] }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return ("invalid json", 400)

    if not isinstance(data, dict):
        return ("invalid payload", 400)

    # (Optional) เบื้องต้นตรวจขนาด payload เพื่อกัน abuse
    if len(json.dumps(data)) > 200000:  # ~200KB limit
        return ("payload too large", 413)

    text = _generate_osd_text_from_model(data)
    buf = io.BytesIO()
    buf.write(text.encode("utf-8"))
    buf.seek(0)

    # ส่งไฟล์ให้ดาวน์โหลด
    # modern Flask: use download_name (Flask >= 2.0). If older, replace download_name with attachment_filename.
    return send_file(
        buf,
        mimetype="text/plain",
        as_attachment=True,
        download_name="obix_osd_layout.txt"
    )

# ===== app.py : OSD export + save + cli generator =====
import io, json, time
from flask import send_file, jsonify
from werkzeug.utils import secure_filename

# helper: generate safe filename
def _timestamped_filename(prefix="obix_osd", ext="txt"):
    t = time.strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{t}.{ext}"

# generate plain text export (human readable + pseudo-cli)
def _generate_osd_text_from_model(model: dict) -> str:
    lines = []
    lines.append("# OBIXConfig OSD export (human readable + pseudo-CLI)")
    lines.append("# Generated by OBIXConfig Doctor")
    lines.append("")
    w = model.get("width", 360)
    h = model.get("height", 240)
    lines.append(f"# Screen: {w}x{h}")
    lines.append("")
    items = model.get("items", [])
    for i, it in enumerate(items, start=1):
        it_type = it.get("type", "unknown")
        label = it.get("label", "")
        x = it.get("x", 0)
        y = it.get("y", 0)
        size = it.get("size", 14)
        color = it.get("color", "#ffffff")
        lines.append(f"# Item {i}: {it_type} '{label}' @ ({x},{y}) size={size} color={color}")
        lines.append(f'cli_add_item type={it_type} x={x} y={y} text="{label}" size={size} color="{color}"')
        lines.append("")
    lines.append("# End of export")
    return "\n".join(lines)

# generate pseudo betaflight-like CLI (informational; requires manual mapping check)
def _generate_betaflight_cli_from_model(model: dict) -> str:
    lines = []
    lines.append("# OBIXConfig — PSEUDO Betaflight CLI (verify before use!)")
    lines.append("# This is a best-effort mapping. Please check Betaflight version & OSD layout syntax.")
    lines.append("")
    items = model.get("items", [])
    for i, it in enumerate(items, start=1):
        it_type = it.get("type", "unknown")
        label = it.get("label", "")
        x = it.get("x", 0)
        y = it.get("y", 0)
        size = it.get("size", 14)
        # Example mapping: we produce a comment + pseudo cmd. You can extend mapping table here.
        lines.append(f"# {i}. {it_type} '{label}' @ ({x},{y})")
        # safe pseudo-command (NOT guaranteed exact Betaflight syntax)
        lines.append(f'# --- pseudo: place {label} as {it_type} at x={x} y={y}')
        lines.append(f'//betaflight: osd_add {it_type} {x} {y} "{label}" size={size}')
        lines.append("")
    lines.append("# End pseudo CLI")
    return "\n".join(lines)


# route: /osd/export  (POST JSON) -> download or save
@app.route("/osd/export", methods=["POST"])
def osd_export():
    """
    POST JSON payload -> returns file.
    Query params:
      - format: "txt" (default) or "cli"
      - save: "1" to save on server in static/downloads/osd/ and return JSON with download_url
    """
    fmt = (request.args.get("format") or "txt").lower()
    save_flag = request.args.get("save") in ("1", "true", "yes")
    try:
        data = request.get_json(force=True)
    except Exception:
        return ("invalid json", 400)

    if not isinstance(data, dict):
        return ("invalid payload", 400)

    # simple size guard
    if len(json.dumps(data)) > 400000:  # ~400KB
        return ("payload too large", 413)

    if fmt == "cli":
        content = _generate_betaflight_cli_from_model(data)
        ext = "cli.txt"
    else:
        content = _generate_osd_text_from_model(data)
        ext = "txt"

    if save_flag:
        # save into static/downloads/osd/
        safe_dir = os.path.join(app.root_path, "static", "downloads", "osd")
        os.makedirs(safe_dir, exist_ok=True)
        fname = secure_filename(_timestamped_filename(prefix="obix_osd", ext=ext))
        full = os.path.join(safe_dir, fname)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        # url for download
        download_url = f"/static/downloads/osd/{fname}"
        return jsonify({"ok": True, "download_url": download_url, "filename": fname})

    # otherwise stream as attachment
    buf = io.BytesIO()
    buf.write(content.encode("utf-8"))
    buf.seek(0)
    return send_file(buf, mimetype="text/plain", as_attachment=True, download_name=f"obix_osd.{ext}")

# ===============================
# ERROR HANDLERS
# ===============================
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

@app.route("/healthz")
def healthz():
    return {"status":"ok", "advanced_analysis": bool(ADV_ANALYSIS_AVAILABLE)}

# Run (dev)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)