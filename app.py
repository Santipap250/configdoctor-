from flask import Flask, render_template, request
from analyzer.prop_logic import analyze_propeller
from analyzer.thrust_logic import calculate_thrust_weight, estimate_battery_runtime
from analyzer.battery_logic import analyze_battery
from logic.presets import PRESETS, detect_class_from_size, get_baseline_for_class
from analyzer.drone_class import detect_drone_class

app = Flask(__name__)

# ===============================
# VALIDATE INPUT
# ===============================
def validate_input(size, weight, prop_size, pitch, blades):
    warnings = []

    if not (1 <= size <= 10):
        warnings.append("ขนาดโดรนควรอยู่ระหว่าง 1–10 นิ้ว")

    if weight <= 0 or weight > 3000:
        warnings.append("น้ำหนักโดรนควรอยู่ระหว่าง 1–3000 กรัม")

    if prop_size > size:
        warnings.append("ขนาดใบพัดใหญ่กว่าขนาดโดรน อาจติดเฟรม")

    if not (2.0 <= pitch <= 6.5):
        warnings.append("Pitch ใบพัดอยู่นอกช่วงที่ใช้ทั่วไป")

    if blades not in [2, 3, 4]:
        warnings.append("จำนวนใบพัดผิดปกติ")

    return warnings

# ===============================
# CLASSIFY WEIGHT
# ===============================
def classify_weight(size, weight):
    if size >= 5:
        if weight < 650:
            return "เบา"
        elif weight <= 900:
            return "กลาง"
        else:
            return "หนัก"
    return "ไม่ระบุ"

# ===============================
# LOGIC วิเคราะห์โดรน
# ===============================
def analyze_drone(size, battery, style, prop_result, weight):
    analysis = {}

    analysis["overview"] = (
        f'โดรน {size}" แบต {battery}, สไตล์ {style}, ใบพัด: {prop_result["summary"]}'
    )

   
    analysis["weight_class"] = classify_weight(size, weight)

    analysis["basic_tips"] = [
        "ตรวจสอบใบพัดไม่บิดงอ",
        "ขันน็อตมอเตอร์ให้แน่น",
        "เช็คจุดบัดกรี ESC และแบตเตอรี่"
    ]

    # PID + Filter
    if style == "freestyle":
        pid = {
            "roll": {"p":48,"i":52,"d":38},
            "pitch":{"p":48,"i":52,"d":38},
            "yaw":{"p":40,"i":45,"d":0}
        }
        filter_desc = {"gyro_lpf2":90,"dterm_lpf1":120,"dyn_notch":2}
        extra_tips = ["Freestyle, สมดุล แรงพอดี"]

    elif style == "racing":
        pid = {
            "roll": {"p":55,"i":45,"d":42},
            "pitch":{"p":55,"i":45,"d":42},
            "yaw":{"p":50,"i":40,"d":0}
        }
        filter_desc = {"gyro_lpf2":120,"dterm_lpf1":150,"dyn_notch":3}
        extra_tips = ["Racing, ตอบสนองไว"]

    else:
        pid = {
            "roll": {"p":42,"i":50,"d":32},
            "pitch":{"p":42,"i":50,"d":32},
            "yaw":{"p":35,"i":45,"d":0}
        }
        filter_desc = {"gyro_lpf2":70,"dterm_lpf1":90,"dyn_notch":1}
        extra_tips = ["Long Range, Smooth, ประหยัดแบต"]

    analysis["pid"] = pid
    analysis["filter"] = filter_desc
    analysis["extra_tips"] = extra_tips
    analysis["thrust_ratio"] = calculate_thrust_weight(
        prop_result["effect"]["motor_load"], weight
    )
    analysis["battery_est"] = estimate_battery_runtime(weight, battery)

# --- Detect drone class and attach baseline (safe, non-destructive) ---
    try:
        cls_key, cls_meta = detect_drone_class(size, weight)
        if cls_key and cls_meta:
            # attach a readable class and meta
            analysis["detected_class"] = cls_key
            analysis["class_meta"] = {"description": cls_meta.get("description", "")}

            # attach baseline PID/filter separately (do not overwrite analysis['pid'])
            analysis["pid_baseline"] = cls_meta.get("pid", {})
            analysis["filter_baseline"] = cls_meta.get("filter", {})

            # small note for template / UI
            analysis.setdefault("extra_tips", []).append(
                f"System detected class '{cls_key}' — baseline PID/filter suggested."
            )
    except Exception:
        # be tolerant: do not raise, just skip class detection
        pass
    return analysis
# ===============================
# ROUTE: Landing Page
# ===============================
@app.route("/landing")
def landing():
    return render_template("landing.html")

# ===============================
# ROUTE: หน้า Loading
# ===============================
@app.route("/")
def loading():
    return render_template("loading.html")

# ===============================
# ROUTE: เช็ค backend
# ===============================
@app.route("/ping")
def ping():
    return "pong"

# ===============================
# ROUTE: แอพจริง
# ===============================
@app.route("/app", methods=["GET", "POST"])
def index():
    analysis = None

    if request.method == "POST":
        # Read preset (if any) and form inputs safely
        preset_key = request.form.get("preset", "").strip()

        def safe_float(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return default

        def safe_int(x, default=0):
            try:
                return int(x)
            except Exception:
                return default

        # read inputs with fallbacks
        size = safe_float(request.form.get("size"), 5.0)
        battery = request.form.get("battery", "4S")
        style = request.form.get("style", "freestyle")
        weight = safe_float(request.form.get("weight"), 1.0)
        prop_size = safe_float(request.form.get("prop_size"), 5.0)
        blade_count = safe_int(request.form.get("blades"), 3)
        prop_pitch = safe_float(request.form.get("pitch"), 4.0)

        # override with preset if selected
        if preset_key:
            p = PRESETS.get(preset_key)
            if p:
                size = safe_float(p.get("size", size))
                battery = p.get("battery", battery)
                style = p.get("style", style)
                weight = safe_float(p.get("weight", weight))
                prop_size = safe_float(p.get("prop_size", prop_size))
                prop_pitch = safe_float(p.get("pitch", prop_pitch))
                blade_count = safe_int(p.get("blades", blade_count))

        # validation
        warnings = validate_input(size, weight, prop_size, prop_pitch, blade_count)

        # prop analysis
        try:
            prop_result = analyze_propeller(prop_size, prop_pitch, blade_count, style)
        except Exception:
            prop_result = {"summary": "prop analysis not available", "effect": {"motor_load": 0, "noise": 0}, "recommendation": ""}

        # main analysis
        try:
            analysis = analyze_drone(size, battery, style, prop_result, weight)
        except Exception:
            analysis = {
                "style": style,
                "weight_class": "unknown",
                "thrust_ratio": 0,
                "flight_time": 0,
                "summary": "analysis fallback (internal error)",
                "basic_tips": []
            }

        # detect class (some versions return tuple)
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

        # ==== Normalize & preserve fields expected by template ====
        # ensure 'style' is present (template uses analysis.style)
        analysis.setdefault("style", style)

        # provide a short summary field (template references analysis.summary)
        analysis.setdefault("summary", analysis.get("overview", ""))

        # normalize warnings to objects with level/msg because template expects w.level and w.msg
        norm_warnings = []
        for w in warnings:
            if isinstance(w, dict):
                lvl = w.get("level", "warning")
                msg = w.get("msg", str(w))
            else:
                lvl = "warning"
                msg = str(w)
            norm_warnings.append({"level": lvl, "msg": msg})
        analysis["warnings"] = norm_warnings

        # ensure prop_result.effect contains keys used by template (motor_load, noise, grip)
        effect = prop_result.get("effect", {})
        if "motor_load" not in effect:
            effect["motor_load"] = effect.get("motor_load", 0)
        if "noise" not in effect:
            effect["noise"] = effect.get("noise", 0)
        if "grip" not in effect:
            effect["grip"] = effect.get("grip", 0)
        prop_result["effect"] = effect
        analysis["prop_result"] = prop_result

        # (optional) debug print to server logs
        try:
            print("DEBUG: analysis keys ->", list(analysis.keys()))
            print("DEBUG: battery_est ->", analysis.get("battery_est"))
        except Exception:
            pass

    return render_template("index.html", analysis=analysis)

# ===============================
# ROUTE: About page
# ===============================
@app.route("/about")
def about():
    # ถ้าส่ง data ไปยัง template ใส่ใน context dict ได้
    return render_template("about.html")

# ===============================
# ROUTE: Changelog page
# ===============================
@app.route("/changelog")
def changelog():
    # ในอนาคตถ้าต้องการดึง changelog จากไฟล์หรือ DB ให้ใส่ logic ที่นี่
    return render_template("changelog.html")
# ===============================
# RUN
# ===============================
import os
import os, hashlib
from werkzeug.utils import secure_filename
from flask import send_from_directory, abort, render_template

# ดาวน์โหลดไฟล์จริง (attachment)
@app.route('/downloads/<fc>/<filename>')
def download_diff(fc, filename):
    safe_fc = secure_filename(fc)
    safe_fn = secure_filename(filename)
    base_dir = os.path.join(app.root_path, 'static', 'downloads', 'diff_all', safe_fc)
    file_path = os.path.join(base_dir, safe_fn)
    if not os.path.isfile(file_path):
        abort(404)
    return send_from_directory(base_dir, safe_fn, as_attachment=True)

# หน้าแสดงรายการดาวน์โหลด (scan โฟลเดอร์ static/downloads/diff_all)
@app.route('/downloads')
def downloads_index():
    base = os.path.join(app.root_path, 'static', 'downloads', 'diff_all')
    items = []
    if os.path.isdir(base):
        for fc in sorted(os.listdir(base)):
            fcdir = os.path.join(base, fc)
            if not os.path.isdir(fcdir):
                continue
            for fn in sorted(os.listdir(fcdir)):
                path = os.path.join(fcdir, fn)
                size = os.path.getsize(path)
                mtime = int(os.path.getmtime(path))
                # short sha256 แสดงคร่าว ๆ
                with open(path, 'rb') as f:
                    h = hashlib.sha256(f.read()).hexdigest()[:16]
                items.append({
                    'fc': fc,
                    'filename': fn,
                    'size': size,
                    'mtime': mtime,
                    'sha': h
                })
    return render_template('downloads.html', items=items)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False
    )