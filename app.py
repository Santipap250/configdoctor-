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

# ===============================
# ROUTE: VTX Range Calculator (multi-model)
# ===============================
from flask import jsonify
import math

# helper: wavelength (m) from MHz
def _lambda_m(freq_mhz):
    return 300.0 / float(freq_mhz)

# Path loss (dB) models
def path_loss_fspl(d_m, freq_mhz):
    """Free-space path loss (d in meters, f in MHz)"""
    lam = _lambda_m(freq_mhz)
    # FSPL = 20*log10(4*pi*d / lambda)
    if d_m <= 0:
        return 0.0
    return 20.0 * math.log10(4.0 * math.pi * d_m / lam)

def path_loss_two_ray(d_m, freq_mhz, ht_m=0.3, hr_m=0.3):
    """Two-ray ground approximation (valid for moderate/large d)
       Uses far-field large-distance approx:
       PL_two_ray(dB) = 40*log10(d) - 20*log10(ht) - 20*log10(hr) - 20*log10(lambda/(4*pi))
       (d in meters, ht/hr in meters)
    """
    lam = _lambda_m(freq_mhz)
    if d_m <= 0:
        return 0.0
    const = 20.0 * math.log10(lam / (4.0 * math.pi))
    return 40.0 * math.log10(d_m) - 20.0 * math.log10(ht_m) - 20.0 * math.log10(hr_m) - const

def path_loss_hata(d_m, freq_mhz, ht_m=1.0, hr_m=1.0, city_type="urban"):
    """Okumura-Hata model (classic). Valid approx 150 - 1500 MHz and d in km.
       Reference formula (urban); includes small-city correction a(hr).
       We include 'urban', 'suburban', 'rural' variants.
    """
    d_km = max(0.001, d_m / 1000.0)
    f = float(freq_mhz)
    # a(hr) correction (for small/medium cities)
    # a(hr) = (1.1*log10(f) - 0.7)*hr - (1.56*log10(f) - 0.8)
    a_hr = (1.1 * math.log10(f) - 0.7) * hr_m - (1.56 * math.log10(f) - 0.8)
    # Hata urban basic:
    L = 69.55 + 26.16 * math.log10(f) - 13.82 * math.log10(ht_m) - a_hr + (44.9 - 6.55 * math.log10(ht_m)) * math.log10(d_km)
    if city_type == "suburban":
        # correction for suburban
        L = L - 2 * (math.log10(f / 28.0))**2 - 5.4
    elif city_type == "rural":
        # rural modification (ITU simplified)
        L = L - 4.78 * (math.log10(f))**2 + 18.33 * math.log10(f) - 40.94
    return L

def path_loss_itu_simple(d_m, freq_mhz, terrain="land"):
    """Very simple ITU fallback: FSPL plus an environment loss term.
       This is NOT full ITU-R P.1546 but gives usable correction bands.
    """
    base = path_loss_fspl(d_m, freq_mhz)
    env_extra = {
        "land": 0.0,
        "suburban": 8.0,
        "urban": 15.0,
        "forest": 20.0
    }.get(terrain, 0.0)
    return base + env_extra

# numeric solver: find d such that path_loss(d) ~= allowed_loss (binary search)
def solve_distance_for_loss(allowed_loss_db, freq_mhz, model, model_args=None, d_min=0.5, d_max=1e6):
    model_args = model_args or {}
    low = d_min
    high = d_max
    # if even at max distance loss < allowed, return max
    def pl_at(d):
        if model == "fspl":
            return path_loss_fspl(d, freq_mhz)
        elif model == "two_ray":
            return path_loss_two_ray(d, freq_mhz, **model_args)
        elif model == "hata":
            return path_loss_hata(d, freq_mhz, **model_args)
        elif model == "itu_simple":
            return path_loss_itu_simple(d, freq_mhz, **model_args)
        else:
            return path_loss_fspl(d, freq_mhz)

    # check monotonicity: generally path loss increases with d for these models
    # If allowed_loss is lower than PL at d_min => distance < d_min
    if pl_at(low) > allowed_loss_db:
        return low
    # if even at high PL < allowed => return high
    if pl_at(high) <= allowed_loss_db:
        return high

    for _ in range(60):
        mid = (low + high) / 2.0
        pl = pl_at(mid)
        if pl > allowed_loss_db:
            high = mid
        else:
            low = mid
    return (low + high) / 2.0

@app.route("/vtx-calc", methods=["POST"])
def vtx_calc():
    try:
        # read form values (defaults tuned for FPV)
        power_mw = float(request.form.get("power_mw", 200.0))   # mW
        freq_mhz = float(request.form.get("freq_mhz", 5800.0))
        tx_gain_db = float(request.form.get("tx_gain_db", 2.0))
        rx_gain_db = float(request.form.get("rx_gain_db", 2.0))
        rx_sens_dbm = float(request.form.get("rx_sens_dbm", -90.0))
        margin_db = float(request.form.get("margin_db", 10.0))
        model = request.form.get("model", "fspl")

        # optional model params
        ht_m = float(request.form.get("ht_m", 0.03))   # tx antenna height (m) small VTX on quad ~0.03-0.1
        hr_m = float(request.form.get("hr_m", 1.5))    # rx antenna height (m) - pilot goggles ~1-1.8
        city_type = request.form.get("city_type", "urban")
        terrain = request.form.get("terrain", "land")

        # compute tx dBm
        tx_dbm = 10.0 * math.log10(max(power_mw, 0.001))  # convert mW->dBm
        # allowed path loss = Pt + Gt + Gr - (Rx_sens + margin)
        allowed_loss_db = tx_dbm + tx_gain_db + rx_gain_db - (rx_sens_dbm + margin_db)

        # pick model args
        model_args = {}
        if model == "two_ray":
            model_args = {"ht_m": max(0.01, ht_m), "hr_m": max(0.01, hr_m)}
        elif model == "hata":
            model_args = {"ht_m": max(1.0, ht_m), "hr_m": max(1.0, hr_m), "city_type": city_type}
        elif model == "itu_simple":
            model_args = {"terrain": terrain}

        # solve for distance (meters)
        est_d_m = solve_distance_for_loss(allowed_loss_db, freq_mhz, model, model_args=model_args, d_min=0.5, d_max=2e6)

        # also compute PL at that distance and received power
        if model == "fspl":
            pl_db = path_loss_fspl(est_d_m, freq_mhz)
        elif model == "two_ray":
            pl_db = path_loss_two_ray(est_d_m, freq_mhz, **model_args)
        elif model == "hata":
            pl_db = path_loss_hata(est_d_m, freq_mhz, **model_args)
        else:
            pl_db = path_loss_itu_simple(est_d_m, freq_mhz, **model_args)

        rx_dbm = tx_dbm + tx_gain_db + rx_gain_db - pl_db

        # return structured JSON (used by JS)
        return jsonify({
            "ok": True,
            "inputs": {
                "power_mw": power_mw,
                "freq_mhz": freq_mhz,
                "tx_dbm": round(tx_dbm,2),
                "tx_gain_db": tx_gain_db,
                "rx_gain_db": rx_gain_db,
                "rx_sens_dbm": rx_sens_dbm,
                "margin_db": margin_db,
                "model": model,
                "ht_m": ht_m,
                "hr_m": hr_m,
                "city_type": city_type,
                "terrain": terrain
            },
            "results": {
                "allowed_path_loss_db": round(allowed_loss_db,2),
                "estimated_distance_m": round(est_d_m,1),
                "path_loss_db_at_distance": round(pl_db,2),
                "rx_dbm_at_distance": round(rx_dbm,2)
            },
            "explain": {
                "model_help": {
                    "fspl": "Free-space (ITU-R reference): good baseline in unobstructed LOS. PL(dB)=20log10(4πd/λ).",
                    "two_ray": "Two-ray ground: includes direct + ground-reflection interference; tends to dominate at larger distances where PL∝d^4.",
                    "hata": "Okumura–Hata (empirical): built for 150–1500 MHz, uses antenna heights and city type; caution above its frequency validity.",
                    "itu_simple": "Simple ITU-style correction: FSPL + environment extra loss (urban/forest/suburban). Not a full ITU-R P.1546 implementation."
                }
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

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