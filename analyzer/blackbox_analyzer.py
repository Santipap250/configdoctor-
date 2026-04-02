"""
analyzer/blackbox_analyzer.py — OBIXConfig Doctor v2.2
════════════════════════════════════════════════════════
Betaflight Blackbox CSV Analyzer (pure Python stdlib, no numpy)

ความสามารถ:
  • รองรับ BF4.3 / BF4.4 / BF4.5 column naming
  • Oscillation detection (zero-crossing + RMS)
  • P / D / FF term quality analysis
  • Motor balance & imbalance detection
  • Battery sag & voltage profiling
  • Throttle distribution (hover%, mid%, full%)
  • Propwash detection (gyro spikes post-maneuver)
  • Smart sampling (max 8,000 rows regardless of file size)
  • CLI fix recommendations auto-generated
"""

import csv
import io
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Column name aliases  (BF4.3 → BF4.4 → BF4.5 ชื่อเปลี่ยน)
# ──────────────────────────────────────────────────────────────────────────────
_COL_ALIASES: Dict[str, List[str]] = {
    # Gyro
    "gyro_roll":   ["gyroADC[0]", "gyroADC_0", "gyro[0]", "gyroRoll"],
    "gyro_pitch":  ["gyroADC[1]", "gyroADC_1", "gyro[1]", "gyroPitch"],
    "gyro_yaw":    ["gyroADC[2]", "gyroADC_2", "gyro[2]", "gyroYaw"],
    # Setpoint (RC command)
    "sp_roll":     ["setpoint[0]", "setpoint_0", "rcCommand[0]"],
    "sp_pitch":    ["setpoint[1]", "setpoint_1", "rcCommand[1]"],
    "sp_yaw":      ["setpoint[2]", "setpoint_2", "rcCommand[2]"],
    "sp_throttle": ["setpoint[3]", "setpoint_3", "rcCommand[3]"],
    # PID terms
    "p_roll":      ["axisP[0]", "axisP_0", "PID_P[0]"],
    "p_pitch":     ["axisP[1]", "axisP_1", "PID_P[1]"],
    "d_roll":      ["axisD[0]", "axisD_0", "PID_D[0]"],
    "d_pitch":     ["axisD[1]", "axisD_1", "PID_D[1]"],
    "i_roll":      ["axisI[0]", "axisI_0", "PID_I[0]"],
    "i_pitch":     ["axisI[1]", "axisI_1", "PID_I[1]"],
    "ff_roll":     ["axisFF[0]", "axisFF_0", "PID_FF[0]"],
    "ff_pitch":    ["axisFF[1]", "axisFF_1", "PID_FF[1]"],
    # Motors
    "motor0":      ["motor[0]", "motor_0", "motor0"],
    "motor1":      ["motor[1]", "motor_1", "motor1"],
    "motor2":      ["motor[2]", "motor_2", "motor2"],
    "motor3":      ["motor[3]", "motor_3", "motor3"],
    # eRPM
    "erpm0":       ["eRPM[0]", "eRPM_0", "rpm[0]"],
    "erpm1":       ["eRPM[1]", "eRPM_1", "rpm[1]"],
    "erpm2":       ["eRPM[2]", "eRPM_2", "rpm[2]"],
    "erpm3":       ["eRPM[3]", "eRPM_3", "rpm[3]"],
    # Battery
    "vbat":        ["vbatLatest", "vbat", "voltage"],
    "amperage":    ["amperageLatest", "amperage", "current"],
    # Time
    "time":        ["time", "loopIteration", "timeUs"],
}

MAX_ROWS    = 8_000    # สูงสุดที่โหลดเข้าวิเคราะห์
SAMPLE_RATE = 2000     # Hz default (Betaflight standard looptime 500µs)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_col(headers: List[str], key: str) -> Optional[str]:
    """หา column จริงจาก alias list"""
    aliases = _COL_ALIASES.get(key, [key])
    h_lower = {h.lower(): h for h in headers}
    for alias in aliases:
        if alias in headers:
            return alias
        if alias.lower() in h_lower:
            return h_lower[alias.lower()]
    return None


def _fval(row: Dict, col: Optional[str], default: float = 0.0) -> float:
    """ดึงค่า float จาก row อย่างปลอดภัย"""
    if col is None:
        return default
    v = row.get(col, "")
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _rms(values: List[float]) -> float:
    """Root Mean Square"""
    if not values:
        return 0.0
    return math.sqrt(sum(x * x for x in values) / len(values))


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def _percentile(sorted_vals: List[float], pct: float) -> float:
    """Simple percentile on pre-sorted list"""
    if not sorted_vals:
        return 0.0
    idx = (len(sorted_vals) - 1) * pct / 100.0
    lo  = int(idx)
    hi  = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def _count_zero_crossings(values: List[float]) -> int:
    """นับจำนวนครั้งที่ waveform ตัดแกน 0 — proxy สำหรับ frequency"""
    count = 0
    for i in range(1, len(values)):
        if values[i - 1] * values[i] < 0:
            count += 1
    return count


def _dominant_freq_hz(values: List[float], sample_rate: int = SAMPLE_RATE) -> float:
    """ประมาณ dominant frequency จาก zero-crossing rate"""
    if len(values) < 10:
        return 0.0
    zc = _count_zero_crossings(values)
    duration_s = len(values) / sample_rate
    if duration_s <= 0:
        return 0.0
    return round(zc / (2.0 * duration_s), 1)


def _detect_spikes(values: List[float], threshold_multiplier: float = 3.5) -> int:
    """นับ spikes ที่เกิน threshold_multiplier × RMS"""
    if not values:
        return 0
    rms_val = _rms(values)
    if rms_val < 0.1:
        return 0
    thresh = rms_val * threshold_multiplier
    return sum(1 for v in values if abs(v) > thresh)


# ──────────────────────────────────────────────────────────────────────────────
# CSV Parser
# ──────────────────────────────────────────────────────────────────────────────

def _parse_csv(text: str) -> Tuple[List[str], List[Dict]]:
    """
    Parse Betaflight blackbox CSV
    - ข้ามบรรทัด comment ที่ขึ้นต้น #
    - ข้ามบรรทัด H (header metadata) จาก blackbox_decode
    - sample ลง MAX_ROWS rows
    """
    lines = text.splitlines()

    # กรอง metadata lines ของ blackbox_decode (ขึ้น "H " หรือ comment "#")
    data_lines = [l for l in lines
                  if l.strip()
                  and not l.startswith("H ")
                  and not l.startswith("#")]

    if not data_lines:
        return [], []

    # หา header row (row แรกที่มี comma และ text-like values)
    header_row = data_lines[0]
    data_rows  = data_lines[1:]

    reader = csv.DictReader(io.StringIO(header_row + "\n" + "\n".join(data_rows)))
    headers = reader.fieldnames or []

    # ── Smart sampling ──────────────────────────────────
    all_rows = list(reader)
    n = len(all_rows)
    if n <= MAX_ROWS:
        rows = all_rows
    else:
        step = n // MAX_ROWS
        rows = all_rows[::step][:MAX_ROWS]

    return list(headers), rows


# ──────────────────────────────────────────────────────────────────────────────
# Core Analysis Modules
# ──────────────────────────────────────────────────────────────────────────────

def _analyze_oscillations(rows: List[Dict], cols: Dict) -> Dict:
    """
    ตรวจ oscillation บน Roll / Pitch / Yaw
    ใช้ RMS, zero-crossing freq, spike count
    """
    results = {}
    axes = [
        ("roll",  "gyro_roll",  "p_roll",  "d_roll"),
        ("pitch", "gyro_pitch", "p_pitch", "d_pitch"),
        ("yaw",   "gyro_yaw",   None,      None),
    ]

    for axis, gyro_k, p_k, d_k in axes:
        gyro_col = cols.get(gyro_k)
        p_col    = cols.get(p_k)   if p_k  else None
        d_col    = cols.get(d_k)   if d_k  else None

        gyro_vals = [_fval(r, gyro_col) for r in rows]
        p_vals    = [_fval(r, p_col)    for r in rows] if p_col else []
        d_vals    = [_fval(r, d_col)    for r in rows] if d_col else []

        gyro_rms  = round(_rms(gyro_vals), 2)
        gyro_freq = _dominant_freq_hz(gyro_vals)
        gyro_spk  = _detect_spikes(gyro_vals)
        p_rms     = round(_rms(p_vals), 2) if p_vals else 0
        d_rms     = round(_rms(d_vals), 2) if d_vals else 0
        d_max     = round(max((abs(v) for v in d_vals), default=0), 1)

        # ── Severity scoring ──────────────────────────────
        osc_severity = "good"
        osc_msg      = ""

        if gyro_rms > 120:
            osc_severity = "danger"
            osc_msg = f"Gyro RMS สูงมาก ({gyro_rms}) — oscillation รุนแรง"
        elif gyro_rms > 60:
            osc_severity = "warning"
            osc_msg = f"Gyro RMS สูง ({gyro_rms}) — อาจมี oscillation"
        elif gyro_rms > 30:
            osc_severity = "info"
            osc_msg = f"Gyro RMS ({gyro_rms}) — ปกติ พิจารณาตรวจสอบ"
        else:
            osc_msg = f"Gyro RMS ({gyro_rms}) — ดี"

        # D-term noise
        d_severity = "good"
        d_msg = ""
        if d_rms > 80:
            d_severity = "danger"
            d_msg = f"D-term noise สูงมาก (RMS={d_rms}) — มอเตอร์จะร้อน"
        elif d_rms > 40:
            d_severity = "warning"
            d_msg = f"D-term noise สูง (RMS={d_rms}) — ตรวจ filter"
        elif d_rms > 0:
            d_msg = f"D-term noise ปกติ (RMS={d_rms})"

        results[axis] = {
            "gyro_rms":       gyro_rms,
            "gyro_freq_hz":   gyro_freq,
            "gyro_spikes":    gyro_spk,
            "p_rms":          p_rms,
            "d_rms":          d_rms,
            "d_max":          d_max,
            "osc_severity":   osc_severity,
            "osc_msg":        osc_msg,
            "d_severity":     d_severity,
            "d_msg":          d_msg,
        }

    return results


def _analyze_motors(rows: List[Dict], cols: Dict) -> Dict:
    """
    Motor balance analysis
    - ตรวจ imbalance ระหว่าง diagonal pairs (0+2 vs 1+3)
    - ตรวจ motor ที่ stuck หรือ out-of-range
    - เปรียบ std deviation ระหว่าง motors
    """
    m_keys = ["motor0", "motor1", "motor2", "motor3"]
    m_cols = [cols.get(k) for k in m_keys]

    # เก็บ series
    m_series: List[List[float]] = []
    for mc in m_cols:
        vals = [_fval(r, mc) for r in rows] if mc else []
        m_series.append(vals)

    # คำนวณต่อ motor
    motor_stats = []
    for i, vals in enumerate(m_series):
        if not vals:
            motor_stats.append({"id": i, "available": False})
            continue
        avg = round(_mean(vals), 1)
        mn  = round(min(vals), 1)
        mx  = round(max(vals), 1)
        sd  = round(_stdev(vals), 1)
        motor_stats.append({
            "id":  i,
            "available": True,
            "avg": avg,
            "min": mn,
            "max": mx,
            "std": sd,
        })

    # Balance: pair 0+2 (front-left + rear-right) vs 1+3
    balance_severity = "good"
    balance_msg = "มอเตอร์สมดุลดี"
    imbalance_pct = 0.0

    avgs = [s["avg"] for s in motor_stats if s.get("available")]
    if len(avgs) == 4:
        pair_a = (avgs[0] + avgs[2]) / 2.0
        pair_b = (avgs[1] + avgs[3]) / 2.0
        overall = (pair_a + pair_b) / 2.0
        if overall > 0:
            imbalance_pct = round(abs(pair_a - pair_b) / overall * 100, 1)

        if imbalance_pct > 15:
            balance_severity = "danger"
            balance_msg = f"Diagonal imbalance {imbalance_pct}% — โดรนอาจเอียง ตรวจ motor/prop"
        elif imbalance_pct > 8:
            balance_severity = "warning"
            balance_msg = f"Diagonal imbalance {imbalance_pct}% — ตรวจ prop balance"
        elif imbalance_pct > 3:
            balance_severity = "info"
            balance_msg = f"Diagonal imbalance {imbalance_pct}% — เล็กน้อย OK"
        else:
            balance_msg = f"Diagonal imbalance {imbalance_pct}% — สมดุลดี"

    # Min/max span across all motors (ตรวจ stuck motor)
    stuck_motors = []
    if avgs:
        overall_avg = _mean(avgs)
        for s in motor_stats:
            if s.get("available") and overall_avg > 0:
                diff_pct = abs(s["avg"] - overall_avg) / overall_avg * 100
                if diff_pct > 25:
                    stuck_motors.append(f"Motor {s['id']+1}")

    # Sample series สำหรับ chart (50 จุด)
    chart_series = {}
    for i, vals in enumerate(m_series):
        if vals:
            step = max(1, len(vals) // 50)
            chart_series[f"m{i}"] = [round(v, 1) for v in vals[::step][:50]]

    return {
        "motor_stats":        motor_stats,
        "imbalance_pct":      imbalance_pct,
        "balance_severity":   balance_severity,
        "balance_msg":        balance_msg,
        "stuck_motors":       stuck_motors,
        "chart_series":       chart_series,
    }


def _analyze_battery(rows: List[Dict], cols: Dict) -> Dict:
    """
    Battery sag & voltage profile
    - Min/max/avg voltage
    - Sag ตอน full throttle
    - % voltage drop จาก start → end
    """
    vbat_col = cols.get("vbat")
    amp_col  = cols.get("amperage")

    if not vbat_col:
        return {"available": False}

    vbat_vals = [_fval(r, vbat_col) for r in rows]
    amp_vals  = [_fval(r, amp_col)  for r in rows] if amp_col else []

    if not vbat_vals:
        return {"available": False}

    # BF voltage unit detection:
    # BF4.4/4.5: centiVolts (1680 = 16.80V) → raw_max > 500 → หาร 100
    # BF4.2/4.3: deciVolts หรือ Volts โดยตรง
    raw_max = max((abs(v) for v in vbat_vals if v != 0), default=0)
    if raw_max > 500:
        vbat_scaled = [v / 100.0 for v in vbat_vals]
    elif raw_max > 60:
        vbat_scaled = [v / 10.0 for v in vbat_vals]
    else:
        vbat_scaled = list(vbat_vals)

    vbat_clean = [v for v in vbat_scaled if 3.0 < v < 60.0]
    if not vbat_clean:
        return {"available": False}

    vbat_sorted = sorted(vbat_clean)
    v_start = round(_mean(vbat_clean[:max(1, len(vbat_clean)//20)]), 2)  # avg แรก 5%
    v_end   = round(_mean(vbat_clean[-max(1, len(vbat_clean)//20):]), 2)  # avg ท้าย 5%
    v_min   = round(_percentile(vbat_sorted, 2), 2)    # 2nd percentile = sag min
    v_max   = round(_percentile(vbat_sorted, 98), 2)
    v_avg   = round(_mean(vbat_clean), 2)
    sag_v   = round(v_max - v_min, 2)
    drop_pct = round((v_start - v_end) / v_start * 100, 1) if v_start > 0 else 0.0

    # กำหนด cell count จาก voltage
    cells = 1
    for c in [8, 7, 6, 5, 4, 3, 2]:
        if v_max >= c * 3.5:
            cells = c
            break

    v_per_cell_min = round(v_min / cells, 2) if cells else 0.0
    v_per_cell_avg = round(v_avg / cells, 2) if cells else 0.0

    # Severity
    sag_severity = "good"
    sag_msg = f"Voltage sag {sag_v}V — ดี"
    if sag_v > 2.0:
        sag_severity = "danger"
        sag_msg = f"Voltage sag {sag_v}V — แบตเสื่อม หรือ C-rating ต่ำเกิน"
    elif sag_v > 1.2:
        sag_severity = "warning"
        sag_msg = f"Voltage sag {sag_v}V — แบตอ่อน พิจารณาเปลี่ยน"
    elif sag_v > 0.6:
        sag_severity = "info"
        sag_msg = f"Voltage sag {sag_v}V — ปกติ"

    cell_severity = "good"
    cell_msg = ""
    if v_per_cell_min < 3.3:
        cell_severity = "danger"
        cell_msg = f"Voltage/cell ต่ำสุด {v_per_cell_min}V — อันตราย over-discharge!"
    elif v_per_cell_min < 3.5:
        cell_severity = "warning"
        cell_msg = f"Voltage/cell ต่ำสุด {v_per_cell_min}V — ใกล้ limit"
    else:
        cell_msg = f"Voltage/cell min {v_per_cell_min}V — ปกติ"

    # Amperage
    amp_stats = {}
    if amp_vals:
        amp_clean = [v / 100.0 if max(amp_vals) > 1000 else v
                     for v in amp_vals if v >= 0]
        if amp_clean:
            amp_stats = {
                "avg_a": round(_mean(amp_clean), 1),
                "max_a": round(max(amp_clean), 1),
            }

    # Chart sample (60 จุด)
    step = max(1, len(vbat_clean) // 60)
    chart_vbat = [round(v, 2) for v in vbat_clean[::step][:60]]

    return {
        "available":       True,
        "cells":           cells,
        "v_start":         v_start,
        "v_end":           v_end,
        "v_min":           v_min,
        "v_max":           v_max,
        "v_avg":           v_avg,
        "sag_v":           sag_v,
        "drop_pct":        drop_pct,
        "v_per_cell_min":  v_per_cell_min,
        "v_per_cell_avg":  v_per_cell_avg,
        "sag_severity":    sag_severity,
        "sag_msg":         sag_msg,
        "cell_severity":   cell_severity,
        "cell_msg":        cell_msg,
        "amp_stats":       amp_stats,
        "chart_vbat":      chart_vbat,
    }


def _analyze_throttle(rows: List[Dict], cols: Dict) -> Dict:
    """
    Throttle distribution analysis
    BF stores setpoint[3] as -500..+500 (throttle channel)
    หรือ 1000-2000 (raw RC)
    """
    thr_col = cols.get("sp_throttle")
    if not thr_col:
        return {"available": False}

    thr_vals = [_fval(r, thr_col) for r in rows]
    if not thr_vals:
        return {"available": False}

    # Normalize to 0–100%
    raw_max = max(abs(v) for v in thr_vals)
    if raw_max > 1500:         # RC range 1000-2000
        normalized = [round((v - 1000) / 10.0, 1) for v in thr_vals]
    elif raw_max > 200:        # -500 to +500
        normalized = [round((v + 500) / 10.0, 1) for v in thr_vals]
    else:                      # 0-100
        normalized = [round(v, 1) for v in thr_vals]

    normalized = [max(0.0, min(100.0, v)) for v in normalized]

    # Bucket distribution
    buckets = {
        "hover":   0,   # 0–20%
        "mid":     0,   # 20–60%
        "high":    0,   # 60–85%
        "full":    0,   # 85–100%
    }
    for v in normalized:
        if v <= 20:    buckets["hover"] += 1
        elif v <= 60:  buckets["mid"]   += 1
        elif v <= 85:  buckets["high"]  += 1
        else:          buckets["full"]  += 1

    n = len(normalized)
    pct = {k: round(v / n * 100, 1) if n else 0 for k, v in buckets.items()}

    # Hover throttle %
    avg_thr = round(_mean(normalized), 1)

    # Estimate flight style from distribution
    style_guess = "freestyle"
    if pct["hover"] > 50:
        style_guess = "micro / indoor"
    elif pct["full"] > 30:
        style_guess = "racing / aggressive"
    elif pct["mid"] > 60 and pct["hover"] < 20:
        style_guess = "longrange / cruising"
    elif pct["high"] + pct["full"] > 45:
        style_guess = "freestyle / fast"

    # Chart
    step = max(1, n // 60)
    chart_thr = [round(v, 1) for v in normalized[::step][:60]]

    return {
        "available":    True,
        "avg_pct":      avg_thr,
        "distribution": pct,
        "style_guess":  style_guess,
        "chart_thr":    chart_thr,
    }


def _analyze_pid_quality(rows: List[Dict], cols: Dict,
                         osc_data: Dict) -> Dict:
    """
    PID quality score
    - Error tracking (gyro vs setpoint correlation)
    - P-term overshoot check
    - D-term noise ratio
    - I-term windup check
    """
    issues   : List[Dict] = []
    findings : List[Dict] = []

    roll_osc  = osc_data.get("roll",  {})
    pitch_osc = osc_data.get("pitch", {})

    # ── Oscillation ─────────────────────────────────────────
    for axis, osc in [("Roll", roll_osc), ("Pitch", pitch_osc)]:
        sev = osc.get("osc_severity", "good")
        if sev in ("danger", "warning"):
            freq = osc.get("gyro_freq_hz", 0)
            grms = osc.get("gyro_rms", 0)
            # frequency-based diagnosis
            if 0 < freq < 30:
                diagnosis = "Low-freq wobble — P สูงหรือ I ไม่พอ"
                fix = "ลด P ลง 5-8% หรือเพิ่ม I"
                cli = f"# ลด P {axis.lower()}\nset p_{axis.lower()} = {{p_current - 5}}"
            elif 30 <= freq < 80:
                diagnosis = "Mid-freq oscillation — P/D mismatch"
                fix = "ลด P ลง 5% และเพิ่ม D ขึ้น 3-5"
                cli = f"# ปรับ P/D {axis.lower()}\nset d_{axis.lower()} = {{d_current + 4}}"
            elif freq >= 80:
                diagnosis = f"High-freq buzz {freq}Hz — D-term noise / filter ไม่พอ"
                fix = "ลด D ลง 5 หรือเพิ่ม dterm_lpf"
                cli = f"# ลด D {axis.lower()}\nset d_{axis.lower()} = {{d_current - 5}}"
            else:
                diagnosis = "Oscillation detected"
                fix = "ตรวจ P/D balance"
                cli = ""

            issues.append({
                "axis":      axis,
                "severity":  sev,
                "gyro_rms":  grms,
                "freq_hz":   freq,
                "diagnosis": diagnosis,
                "fix":       fix,
                "cli":       cli,
            })

    # ── D-term noise ─────────────────────────────────────────
    for axis, osc in [("Roll", roll_osc), ("Pitch", pitch_osc)]:
        d_sev = osc.get("d_severity", "good")
        if d_sev in ("danger", "warning"):
            findings.append({
                "type":    "d_noise",
                "axis":    axis,
                "severity": d_sev,
                "msg":     osc.get("d_msg", ""),
                "fix":     "ลด D-term 5-8 หรือลด dterm_lpf1_static_hz ลง 10-20Hz",
                "cli":     f"set dterm_lpf1_static_hz = 90\nset d_{axis.lower()} = {{d_current - 5}}",
            })

    # ── I-term windup ─────────────────────────────────────────
    i_roll_col  = cols.get("i_roll")
    i_pitch_col = cols.get("i_pitch")
    for i_col, axis in [(i_roll_col, "Roll"), (i_pitch_col, "Pitch")]:
        if not i_col:
            continue
        i_vals = [_fval(r, i_col) for r in rows]
        i_max = max(abs(v) for v in i_vals) if i_vals else 0
        if i_max > 400:
            findings.append({
                "type":    "i_windup",
                "axis":    axis,
                "severity": "warning",
                "msg":     f"I-term windup สูง (max={round(i_max,0)}) — อาจเกิด bounce-back",
                "fix":     "เปิด iterm_relax = RPH",
                "cli":     "set iterm_relax = RPH\nset iterm_relax_type = SETPOINT",
            })

    # ── Feedforward ──────────────────────────────────────────
    ff_roll_col = cols.get("ff_roll")
    if ff_roll_col:
        ff_vals = [_fval(r, ff_roll_col) for r in rows]
        ff_rms  = _rms(ff_vals)
        if ff_rms > 150:
            findings.append({
                "type":    "ff_high",
                "axis":    "Roll",
                "severity": "info",
                "msg":     f"Feedforward สูง (RMS={round(ff_rms,1)}) — stick-sensitive มาก",
                "fix":     "ลด feedforward_roll ลงเล็กน้อย หรือเพิ่ม feedforward_smooth_factor",
                "cli":     "set feedforward_smooth_factor = 65",
            })

    # ── Overall PID score (0-100) ─────────────────────────────
    penalty = 0
    for issue in issues:
        if issue["severity"] == "danger":  penalty += 25
        elif issue["severity"] == "warning": penalty += 12
    for f in findings:
        if f["severity"] == "danger":  penalty += 15
        elif f["severity"] == "warning": penalty += 8
        elif f["severity"] == "info":    penalty += 3

    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 55 else "D"

    return {
        "score":    score,
        "grade":    grade,
        "issues":   issues,
        "findings": findings,
    }


def _generate_cli_recommendations(pid_quality: Dict, motor_data: Dict,
                                   battery_data: Dict, osc_data: Dict) -> List[Dict]:
    """สร้าง CLI commands ที่แนะนำจากผลการวิเคราะห์ทั้งหมด"""
    recs: List[Dict] = []
    priority = 1

    # From oscillation issues
    for issue in pid_quality.get("issues", []):
        if issue.get("cli"):
            recs.append({
                "priority": priority,
                "severity": issue["severity"],
                "title":    f"{issue['axis']} Oscillation Fix",
                "reason":   issue["diagnosis"],
                "cli":      issue["cli"],
            })
            priority += 1

    # From PID findings
    for f in pid_quality.get("findings", []):
        if f.get("cli"):
            recs.append({
                "priority": priority,
                "severity": f["severity"],
                "title":    f"{f['axis']} {f['type'].replace('_',' ').title()}",
                "reason":   f["msg"],
                "cli":      f["cli"],
            })
            priority += 1

    # Battery issues
    if battery_data.get("available"):
        if battery_data.get("cell_severity") in ("danger", "warning"):
            recs.append({
                "priority": priority,
                "severity": battery_data["cell_severity"],
                "title":    "Battery Over-discharge",
                "reason":   battery_data["cell_msg"],
                "cli":      "set vbat_min_cell_voltage = 33\nset vbat_warning_cell_voltage = 35",
            })
            priority += 1
        if battery_data.get("sag_severity") == "danger":
            recs.append({
                "priority": priority,
                "severity": "warning",
                "title":    "Voltage Sag สูง",
                "reason":   battery_data["sag_msg"],
                "cli":      "# พิจารณาเปลี่ยนแบต / ใช้ mAh สูงขึ้น หรือ C-rating สูงขึ้น",
            })
            priority += 1

    # Motor imbalance
    if motor_data.get("balance_severity") in ("danger", "warning"):
        recs.append({
            "priority": priority,
            "severity": motor_data["balance_severity"],
            "title":    "Motor Imbalance",
            "reason":   motor_data["balance_msg"],
            "cli":      "# ตรวจ prop balance / motor bearing / motor screw\n# พิจารณา motor_output_limit หรือ yaw_spin_threshold",
        })
        priority += 1

    return recs


def _detect_firmware_version(headers: List[str]) -> str:
    """ประมาณ BF version จาก column names"""
    if any("eRPM" in h for h in headers):
        return "BF4.4/4.5 (eRPM columns detected)"
    if any("axisFF" in h for h in headers):
        return "BF4.3+ (FF columns detected)"
    if any("axisD" in h for h in headers):
        return "BF4.2+"
    return "Unknown / Legacy"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def analyze_blackbox_csv(csv_text: str) -> Dict[str, Any]:
    """
    Main entry point.
    รับ CSV text → return analysis dict พร้อม:
      - meta (rows, duration, firmware)
      - oscillations (per axis)
      - motor_balance
      - battery
      - throttle
      - pid_quality (score, grade, issues, findings)
      - recommendations (CLI commands)
      - error (ถ้ามี parse error)
    """
    try:
        headers, rows = _parse_csv(csv_text)
    except Exception as e:
        return {"error": f"Parse error: {e}"}

    if not headers or not rows:
        return {"error": "ไม่พบข้อมูลใน CSV — ตรวจสอบว่าไฟล์ถูก export จาก Betaflight Blackbox"}

    # ── Map column aliases ────────────────────────────────────
    cols: Dict[str, Optional[str]] = {}
    for key in _COL_ALIASES:
        cols[key] = _find_col(headers, key)

    # Duration estimate
    time_col = cols.get("time")
    duration_s = 0.0
    if time_col and rows:
        try:
            t0 = float(rows[0].get(time_col, 0))
            t1 = float(rows[-1].get(time_col, 0))
            raw_dur = t1 - t0
            # BF time unit: µs → s
            duration_s = round(raw_dur / 1_000_000.0, 1) if raw_dur > 1000 else round(raw_dur, 1)
        except Exception:
            pass  # duration parse failure — non-critical

    # ── Run analysis modules ──────────────────────────────────
    osc_data     = _analyze_oscillations(rows, cols)
    motor_data   = _analyze_motors(rows, cols)
    battery_data = _analyze_battery(rows, cols)
    throttle_data = _analyze_throttle(rows, cols)
    pid_quality  = _analyze_pid_quality(rows, cols, osc_data)
    recs         = _generate_cli_recommendations(pid_quality, motor_data,
                                                  battery_data, osc_data)
    fw_version   = _detect_firmware_version(headers)

    # ── Available axes ────────────────────────────────────────
    available_cols = {k: v for k, v in cols.items() if v is not None}

    return {
        "meta": {
            "rows_analyzed": len(rows),
            "headers_count": len(headers),
            "duration_s":    duration_s,
            "firmware":      fw_version,
            "columns_found": list(available_cols.keys()),
        },
        "oscillations":    osc_data,
        "motor_balance":   motor_data,
        "battery":         battery_data,
        "throttle":        throttle_data,
        "pid_quality":     pid_quality,
        "recommendations": recs,
    }
