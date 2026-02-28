# analyzer/cli_surgeon.py
"""
CLI Surgeon - analyzer for Betaflight / Edge CLI 'diff all' or 'dump' outputs.

Provides:
  - parse_dump(text) -> params dict (raw strings)
  - analyze_dump(text) -> dict with keys:
       summary: str
       rules: list of {id, level, msg, suggestion}
       fix_commands: list of CLI commands (strings) - conservative suggestions
       params: dict of parsed parameters (string values)

Design goals:
  - Safe: NEVER executes user content.
  - Defensive parsing: supports many CLI formats and comments.
  - Extendable: add more rules easily.
"""
from typing import Dict, List, Any
import re
import json

# ----------------------
# Utilities / parsing
# ----------------------

_RE_SET = re.compile(r'^(?:set\s+)?([a-z0-9_\-]+)\s*=\s*(.+)$', re.I)
_RE_COMMENT = re.compile(r'(?:#|;).*?$')
_NUMERIC_RE = re.compile(r'^-?\d+(\.\d+)?$')

def _clean_line(line: str) -> str:
    """Strip BOM, whitespace, and inline comments."""
    if not line:
        return ''
    # remove inline comments starting with # or ;
    line = re.sub(_RE_COMMENT, '', line)
    return line.strip()

def _normalize_key(k: str) -> str:
    """Normalize key naming: lower, replace - with _, strip."""
    return k.lower().strip().replace('-', '_')

def _as_number_if_possible(s: str):
    """Return int/float if convertible, else original string."""
    s = s.strip()
    # remove trailing commas
    s = s.rstrip(',')
    # pure numeric?
    if re.match(r'^-?\d+$', s):
        try:
            return int(s)
        except Exception:
            pass
    if re.match(r'^-?\d+\.\d+$', s):
        try:
            return float(s)
        except Exception:
            pass
    return s

def parse_dump(text: str) -> Dict[str, Any]:
    """
    Parse dump/diff text into a dictionary of parameters.
    - Accepts lines like: "set min_throttle = 1000" or "min_throttle = 1000"
    - Preserves string values when non-numeric
    - For repeated keys (like serialX) keeps last one, but stores raw lines in '_raw_lines'
    """
    params: Dict[str, Any] = {}
    raw_lines: List[str] = []
    if not text:
        return params

    for raw in text.splitlines():
        ln = raw.rstrip('\n\r')
        raw_lines.append(ln)
        line = _clean_line(ln)
        if not line:
            continue

        m = _RE_SET.match(line)
        if m:
            key = _normalize_key(m.group(1))
            val = m.group(2).strip()
            # strip quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            # remove inline comments again (if spaces)
            val = re.sub(_RE_COMMENT, '', val).strip()
            # convert to number if fits
            val_conv = _as_number_if_possible(val)
            params[key] = val_conv
            continue

        # Some CLI dumps contain "feature: value" or "name value" lines; try basic 'key value' split
        parts = line.split(None, 1)
        if len(parts) == 2:
            key = _normalize_key(parts[0])
            val = parts[1].strip()
            val = re.sub(_RE_COMMENT, '', val).strip()
            val_conv = _as_number_if_possible(val)
            params.setdefault(key, val_conv)
            continue

    # include raw lines for advanced checks
    params['_raw_lines'] = raw_lines
    params['_raw_text_sample'] = text[:4096]
    return params

# ----------------------
# Rule checks
# ----------------------

def _add_rule(rules: List[Dict], rid: str, level: str, msg: str, suggestion: str):
    rules.append({"id": rid, "level": level, "msg": msg, "suggestion": suggestion})

def _find_any_text(text: str, tokens: List[str]) -> bool:
    """Case-insensitive search for any token in text."""
    txt = text.lower()
    return any(t.lower() in txt for t in tokens)

def basic_checks(params: Dict[str, Any]) -> List[Dict]:
    """
    Run a set of heuristic checks and return list of rule dicts.
    Each rule: {id, level, msg, suggestion}
    """
    rules: List[Dict] = []
    raw_text = '\n'.join(params.get('_raw_lines', []))
    # --- min throttle / mincommand ---
    min_candidates = []
    for k in ('min_throttle', 'mincommand', 'min_throttle_percent', 'min_throttle_raise'):
        if k in params:
            min_candidates.append((k, params[k]))
    if min_candidates:
        # choose first numeric
        for k, v in min_candidates:
            try:
                val = float(v)
                if val < 1000:
                    _add_rule(
                        rules,
                        'min_throttle_low',
                        'warning',
                        f'{k} ต่ำ ({val}) — อาจทำให้มอเตอร์ stutter/idle หรือไม่สามารถ ARM ได้ในกรณีบางเครื่อง',
                        'พิจารณาปรับ min_throttle / min_command เป็นประมาณ 1000-1020 ขึ้นอยู่กับ ESC/motor; ทดสอบ hover หลังปรับ'
                    )
                elif val > 1100:
                    _add_rule(
                        rules,
                        'min_throttle_high',
                        'info',
                        f'{k} ค่อนข้างสูง ({val}) — อาจทำให้ช่วงใช้งาน throttle เริ่มชิดกับ endpoint',
                        'หากรู้สึก throttle deadband ให้ลดเล็กน้อยและทดสอบ'
                    )
                break
            except Exception:
                continue

    # --- failsafe ---
    failsafe_keys = [k for k in params.keys() if 'failsafe' in k]
    if not failsafe_keys and not _find_any_text(raw_text, ['failsafe', 'failsafe_delay', 'failsafe_action']):
        _add_rule(
            rules,
            'no_failsafe',
            'warning',
            'ไม่พบการตั้งค่า failsafe ที่ชัดเจน',
            'ตั้ง failsafe action (เช่น land หรือ drop), failsafe_delay และ failsafe_throttle ใน Betaflight CLI หรือ GUI'
        )
    else:
        # If present, check some values
        # Failsafe throttle example: check for extremely high throttle in failsafe_throttle
        ff = None
        for k in ('failsafe_throttle', 'failsafe_throttle_percent'):
            if k in params:
                ff = params[k]
                break
        if ff is not None:
            try:
                fval = float(ff)
                if fval > 1200:
                    _add_rule(
                        rules,
                        'failsafe_throttle_high',
                        'warning',
                        f'failsafe_throttle สูง ({fval}) — อาจทำให้โดรนไม่ลงเมื่อ signal lost',
                        'ตั้งค่า failsafe_throttle ให้อยู่ในระดับที่ทำให้มอเตอร์หยุดหมุนหรือทรงตัวขึ้นกับ action ที่ต้องการ'
                    )
            except Exception:
                pass

    # --- looptime ---
    if 'looptime' in params:
        try:
            lt = int(params['looptime'])
            if lt < 1000:
                _add_rule(
                    rules,
                    'looptime_low',
                    'warning',
                    f'looptime ต่ำ ({lt} µs) — บาง ESC/CPU อาจไม่รองรับหรือทำให้ instability',
                    'หากพบ instability ให้พิจารณาขยับ looptime ขึ้น (เช่น 1000-2000) ตาม CPU/ESC ความสามารถ'
                )
            if lt > 4000:
                _add_rule(
                    rules,
                    'looptime_high',
                    'warning',
                    f'looptime สูง ({lt} µs) — อาจเพิ่ม input lag',
                    'ลด looptime หากต้องการ latency ต่ำลง (ตรวจสอบว่า ESC/CPU รองรับ)'
                )
        except Exception:
            pass

    # --- gyro / sample rate ---
    # Keys could be gyro_sample_rate, gyro_hz
    for k in ('gyro_sample_rate','gyro_hz','gyro_hz'):
        if k in params:
            try:
                g = int(params[k])
                if g < 1000:
                    _add_rule(
                        rules,
                        'gyro_rate_low',
                        'info',
                        f'{k} ต่ำ ({g} Hz) — อาจมีผลต่อการตอบสนอง',
                        'พิจารณาใช้ค่า gyro/sample rate ที่เหมาะสมกับ looptime และ firmware'
                    )
            except Exception:
                pass

    # ── PID extremes ──
    # BF4.4/4.5: I-term ปกติ = 80-100, P ปกติ max ~80, D ปกติ max ~60
    # แยก threshold ตาม P/I/D เพื่อไม่ให้ I=90 ถูก flag ผิด
    _PID_THRESHOLDS = {
        'i': 130,    # I สูงกว่า 130 ถึงจะ critical (BF4.4 I ปกติ = 80-100)
        'd': 80,     # D สูงกว่า 80 = critical
        'p': 100,    # P สูงกว่า 100 = critical
    }
    pid_keys = [k for k in params.keys() if re.match(r'^(p|i|d)(_|-)?(roll|pitch|yaw|[xyz])?$', k) or re.match(r'^pid[_\-]?[pid]?', k)]
    for k in pid_keys:
        v = params.get(k)
        try:
            num = float(v)
            # กำหนด threshold ตามชนิด (P/I/D)
            axis_char = k[0].lower()
            threshold = _PID_THRESHOLDS.get(axis_char, 100)
            if num > threshold:
                _add_rule(
                    rules,
                    f'pid_high_{k}',
                    'critical',
                    f'{k} สูงมาก ({num}) — อาจเกิด oscillation / motor stress (threshold {threshold})',
                    'ลดค่า P/I/D ลง หรือย้อนกลับค่าเดิมหากเป็นการ import ผิดพลาด; ทดสอบการบินหลังปรับ'
                )
            if num == 0:
                _add_rule(
                    rules,
                    f'pid_zero_{k}',
                    'info',
                    f'{k} = 0 — อาจทำให้แกนที่เกี่ยวข้องไม่มีการควบคุม',
                    'ตรวจสอบว่าค่า 0 ถูกตั้งใจหรือไม่'
                )
        except Exception:
            continue

    # --- ESC / motor protocol detection (look for tokens) ---
    esc_tokens = ['dshot', 'oneshot', 'multishot', 'brushed']
    found_esc = None
    for t in esc_tokens:
        if _find_any_text(raw_text, [t]):
            found_esc = t
            break
    if found_esc:
        _add_rule(
            rules,
            'esc_protocol_detected',
            'info',
            f'ตรวจพบ ESC protocol hint: {found_esc}',
            'ตรวจสอบความเข้ากันได้ของ ESC กับค่าที่ตั้ง (เช่น DShot600 ต้องใช้ ESC ที่รองรับ)'
        )

    # --- RPM / filtering ---
    rpm_keys = [k for k in params.keys() if 'rpm' in k or 'bypass' in k and 'rpm' in k]
    if any('rpm' in k for k in params.keys()) or _find_any_text(raw_text, ['rpm_filter','dterm_notch','biquad']):
        _add_rule(
            rules,
            'filter_present',
            'info',
            'พบการตั้งค่า filter / rpm filter / notch / biquad',
            'ตรวจสอบการตั้งค่า filter ให้เหมาะสมกับมอเตอร์และ props เพื่อหลีกเลี่ยง oscillation'
        )

    # --- Serial / Telemetry / Receiver ---
    serial_like = [k for k in params.keys() if k.startswith('serial') or 'telemetry' in k or 'serialrx' in k or 'uart' in k]
    if not serial_like and not _find_any_text(raw_text, ['serial', 'telemetry', 'uart', 'serialrx', 'receiver']):
        _add_rule(
            rules,
            'no_serial_telemetry',
            'info',
            'ไม่พบการตั้งค่า serial/telemetry/receiver ที่ชัดเจนใน dump',
            'ถ้าต่อ ELRS/FrSky/OSD ให้ตั้งค่า serial port/telemetry ใน Betaflight'
        )

    # --- VTX / OSD checks ---
    if _find_any_text(raw_text, ['vtx', 'smartaudio', 'tbs_tramp', 'tramp', 'pitmode', 'vtx_power']):
        _add_rule(
            rules,
            'vtx_config',
            'info',
            'พบ token เกี่ยวกับ VTX (SmartAudio / TBS) — ตรวจสอบการตั้งค่า power/channel/pitmode',
            'ตรวจสอบว่ power/antenna/OSD settings ตรงกับ hardware และกฏท้องถิ่น'
        )

    # --- Arming checks (basic) ---
    # look for arming kill flags or disabled arming conditions
    if _find_any_text(raw_text, ['arm_disabled', 'arming_disabled', 'arm:']):
        _add_rule(
            rules,
            'arming_flags',
            'info',
            'พบการตั้งค่าเกี่ยวกับการ arming (arm_disabled / arming flags)',
            'ตรวจสอบว่า switch, lvp, battery thresholds และ safety settings ถูกต้อง'
        )

    # ══════════════════════════════════════════════════════════════════
    # NEW CHECKS v2.0 — ตรวจ parameters สำคัญที่ขาดไป
    # ══════════════════════════════════════════════════════════════════

    # --- DShot Protocol ---
    pwm_proto = str(params.get('motor_pwm_protocol', '')).upper()
    if pwm_proto:
        if pwm_proto in ('DISABLED', 'STANDARD', 'ONESHOT125', 'ONESHOT42', 'MULTISHOT'):
            _add_rule(
                rules, 'protocol_old', 'warning',
                f'motor_pwm_protocol = {pwm_proto} — เป็น analog protocol รุ่นเก่า',
                'เปลี่ยนเป็น DSHOT300 หรือ DSHOT600: set motor_pwm_protocol = DSHOT600'
            )
        elif pwm_proto == 'DSHOT150':
            _add_rule(
                rules, 'protocol_dshot150', 'info',
                'motor_pwm_protocol = DSHOT150 — ใช้ได้แต่ช้ากว่า',
                'แนะนำ DSHOT300/600: set motor_pwm_protocol = DSHOT300'
            )

    # --- Bidirectional DShot ---
    bidir = str(params.get('dshot_bidir', '')).upper()
    rpm_filter_on = _find_any_text(raw_text, ['rpm_filter', 'gyro_rpm_notch'])
    if rpm_filter_on and bidir == 'OFF':
        _add_rule(
            rules, 'bidir_off_with_rpm', 'warning',
            'RPM filter เปิดอยู่ แต่ dshot_bidir = OFF — RPM filter ทำงานไม่ได้',
            'set dshot_bidir = ON (ต้องใช้ DSHOT300+ และ ESC firmware รองรับ)'
        )
    if bidir == 'ON' and pwm_proto and 'DSHOT' not in pwm_proto:
        _add_rule(
            rules, 'bidir_no_dshot', 'danger',
            f'dshot_bidir = ON แต่ protocol = {pwm_proto} — ไม่ compatible กัน',
            'set motor_pwm_protocol = DSHOT600 ให้ตรงกับ bidir'
        )

    # --- iterm_relax ---
    iterm_relax = str(params.get('iterm_relax', '')).upper()
    if iterm_relax == 'OFF':
        _add_rule(
            rules, 'iterm_relax_off', 'warning',
            'iterm_relax = OFF — I-term wind up ระหว่าง maneuver ทำให้ bounce-back',
            'set iterm_relax = RPH | set iterm_relax_type = SETPOINT'
        )

    # --- TPA ---
    tpa_rate = params.get('tpa_rate', None)
    tpa_breakpoint = params.get('tpa_breakpoint', None)
    if tpa_rate is not None:
        try:
            tpa_val = float(tpa_rate)
            if tpa_val > 70:
                _add_rule(rules, 'tpa_high', 'warning',
                    f'tpa_rate = {int(tpa_val)}% สูงมาก — D-term ถูกลดมากที่ full throttle',
                    'ปกติ 30-60%: set tpa_rate = 50 | set tpa_breakpoint = 1600')
            elif tpa_val == 0:
                _add_rule(rules, 'tpa_zero', 'info',
                    'tpa_rate = 0 — D-term ไม่ถูก attenuate ที่ full throttle',
                    'set tpa_rate = 40 | set tpa_breakpoint = 1600')
        except (TypeError, ValueError):
            pass
    if tpa_breakpoint is not None:
        try:
            if int(tpa_breakpoint) < 1400:
                _add_rule(rules, 'tpa_breakpoint_low', 'warning',
                    f'tpa_breakpoint = {tpa_breakpoint} ต่ำมาก — TPA เริ่มเร็วเกินไป',
                    'set tpa_breakpoint = 1600')
        except (TypeError, ValueError):
            pass

    # --- vbat_pid_gain ---
    vbat_pid = str(params.get('vbat_pid_gain', '')).upper()
    if vbat_pid == 'OFF':
        _add_rule(rules, 'vbat_pid_off', 'info',
            'vbat_pid_gain = OFF — PID จะเปลี่ยนตามแรงดันแบต (ตอนแบตอ่อน response ต่างออกไป)',
            'set vbat_pid_gain = ON เพื่อ compensate PID ให้คงที่')

    # --- thrust_linear ---
    thrust_lin = params.get('thrust_linear', None)
    if thrust_lin is not None:
        try:
            tl = int(thrust_lin)
            if tl == 0:
                _add_rule(rules, 'thrust_linear_zero', 'info',
                    'thrust_linear = 0 — mid-stick response sluggish กว่า full stick',
                    'set thrust_linear = 25 เพื่อ stick feel สม่ำเสมอขึ้น')
            elif tl > 75:
                _add_rule(rules, 'thrust_linear_high', 'warning',
                    f'thrust_linear = {tl} สูงมาก — low throttle response hyperactive',
                    'set thrust_linear = 30')
        except (TypeError, ValueError):
            pass

    # ─────────────────────────────────────────────────────────────────
    # BUG FIX v2.1: Filter param naming (BF4.4+ uses *_static_hz)
    # Real dumps: gyro_lpf1_STATIC_hz / dterm_lpf1_STATIC_hz
    # cli_surgeon was reading 'gyro_lpf1_hz' (non-existent param)
    # ─────────────────────────────────────────────────────────────────
    _FILTER_ALIASES = {
        'gyro_lpf1_hz':  ['gyro_lpf1_hz',  'gyro_lpf1_static_hz',  'gyro_lowpass_hz'],
        'dterm_lpf1_hz': ['dterm_lpf1_hz', 'dterm_lpf1_static_hz', 'dterm_lowpass_hz'],
    }
    def _get_filter_param(p, aliases_map, key):
        """Return first found value from aliases, or None."""
        for alias in aliases_map.get(key, [key]):
            if alias in p:
                return p[alias]
        return None

    gyro_hz  = _get_filter_param(params, _FILTER_ALIASES, 'gyro_lpf1_hz')
    dterm_hz = _get_filter_param(params, _FILTER_ALIASES, 'dterm_lpf1_hz')

    # BF4.4+ Simplified Filter: when simplified_gyro_filter = ON,
    # static_hz is 0 and actual freq = multiplier / 100 * 250 Hz
    simplified_on = str(params.get('simplified_gyro_filter', '')).upper() == 'ON'
    simplified_mult = params.get('simplified_gyro_filter_multiplier', None)
    if simplified_on and simplified_mult is not None:
        try:
            gyro_hz = round(int(simplified_mult) / 100.0 * 250)
        except (TypeError, ValueError):
            pass
    simplified_dterm_on = str(params.get('simplified_dterm_filter', '')).upper() == 'ON'
    simplified_dterm_mult = params.get('simplified_dterm_filter_multiplier', None)
    if simplified_dterm_on and simplified_dterm_mult is not None:
        try:
            dterm_hz = round(int(simplified_dterm_mult) / 100.0 * 120)
        except (TypeError, ValueError):
            pass

    # Dynamic filter range (BF4.4+)
    gyro_dyn_min = params.get('gyro_lpf1_dyn_min_hz', None)
    gyro_dyn_max = params.get('gyro_lpf1_dyn_max_hz', None)
    dterm_dyn_min = params.get('dterm_lpf1_dyn_min_hz', None)
    dterm_dyn_max = params.get('dterm_lpf1_dyn_max_hz', None)
    is_dynamic_gyro  = gyro_dyn_min is not None and int(gyro_dyn_min) > 0
    is_dynamic_dterm = dterm_dyn_min is not None and int(dterm_dyn_min) > 0

    # Use dyn min as effective Hz if dynamic mode active
    if is_dynamic_gyro and gyro_hz == 0:
        gyro_hz = gyro_dyn_min
    if is_dynamic_dterm and dterm_hz == 0:
        dterm_hz = dterm_dyn_min

    # Filter checks
    if gyro_hz is not None:
        try:
            ghz = float(gyro_hz)
            mode_desc = "dynamic" if is_dynamic_gyro else ("simplified" if simplified_on else "static")
            if ghz > 400:
                _add_rule(rules, 'gyro_lpf_very_high', 'warning',
                    f'Gyro LPF1 = {int(ghz)}Hz ({mode_desc}) — สูงมาก แทบไม่ filter',
                    'แนะนำ 150-300Hz: set gyro_lpf1_static_hz = 200 หรือใช้ Simplified filter')
            elif ghz > 0 and ghz < 80:
                _add_rule(rules, 'gyro_lpf_very_low', 'warning',
                    f'Gyro LPF1 = {int(ghz)}Hz ({mode_desc}) — ต่ำมาก อาจเพิ่ม latency',
                    'ลองเพิ่ม: set gyro_lpf1_static_hz = 150')
        except (TypeError, ValueError):
            pass

    if dterm_hz is not None:
        try:
            dhz = float(dterm_hz)
            if dhz > 200:
                _add_rule(rules, 'dterm_lpf_high', 'warning',
                    f'D-term LPF1 = {int(dhz)}Hz — สูง อาจ amplify noise ใน D-term',
                    'แนะนำ 80-150Hz: set dterm_lpf1_static_hz = 110')
            elif dhz > 0 and dhz < 60:
                _add_rule(rules, 'dterm_lpf_low', 'info',
                    f'D-term LPF1 = {int(dhz)}Hz — ต่ำมาก อาจทำให้ D-term sluggish',
                    'ลองเพิ่ม: set dterm_lpf1_static_hz = 100')
        except (TypeError, ValueError):
            pass

    if simplified_on:
        _add_rule(rules, 'simplified_filter_on', 'info',
            f'Simplified Gyro Filter ON (multiplier={simplified_mult}) → effective ~{gyro_hz}Hz — BF4.4+ default',
            'ตรวจสอบ filter multiplier ให้เหมาะกับ noise level ของ build คุณ')

    # --- motor_poles ---
    motor_poles = params.get('motor_poles', None)
    if motor_poles is not None:
        try:
            poles = int(motor_poles)
            if poles not in (12, 14, 24, 28, 32):
                _add_rule(rules, 'motor_poles_unusual', 'info',
                    f'motor_poles = {poles} ผิดปกติ (FPV motors ทั่วไป 14 poles)',
                    'ตรวจ motor spec: set motor_poles = 14')
        except (TypeError, ValueError):
            pass

    # --- feedforward ---
    for ff_k in [k for k in params if 'feedforward' in k
                 and k not in ('feedforward_transition','feedforward_averaging','feedforward_smooth_factor')]:
        try:
            ff_val = float(params[ff_k])
            axis = ff_k.replace('feedforward_', '')
            if ff_val > 80:
                _add_rule(rules, f'ff_high_{axis}', 'warning',
                    f'{ff_k} = {int(ff_val)} สูงมาก — อาจ overshoot ใน freestyle',
                    f'set {ff_k} = 35')
            elif ff_val == 0 and 'yaw' not in ff_k:
                _add_rule(rules, f'ff_zero_{axis}', 'info',
                    f'{ff_k} = 0 — stick response ช้า ไม่มี feedforward',
                    f'set {ff_k} = 30')
        except (TypeError, ValueError):
            continue

    # --- anti_gravity_gain ---
    ag = params.get('anti_gravity_gain', None)
    if ag is not None:
        try:
            ag_val = float(ag)
            if ag_val > 25:
                _add_rule(rules, 'anti_gravity_high', 'warning',
                    f'anti_gravity_gain = {ag_val} สูงมาก — oscillation ตอน throttle punch',
                    'set anti_gravity_gain = 8')
        except (TypeError, ValueError):
            pass

    return rules

# ----------------------
# Fix generation (conservative!)
# ----------------------

def suggest_cli_fixes(rules: List[Dict], params: Dict[str, Any]) -> List[str]:
    """
    From rules and params, produce a conservative list of CLI commands safe to copy-paste.
    Always append a 'save' at the end if any change suggested.
    """
    fixes: List[str] = []
    suggested_changes = []

    # Helper: push a set command
    def push_set(key: str, value: Any):
        # format value
        v = value
        if isinstance(v, str):
            v_str = v
        else:
            # numbers -> canonical formatting
            v_str = str(v)
        fixes.append(f"set {key} = {v_str}")
        suggested_changes.append((key, v_str))

    # Lint through rules
    for r in rules:
        rid = r.get('id', '')
        if rid == 'min_throttle_low':
            # conservative: set min_throttle to 1000 if present
            if 'min_throttle' in params:
                push_set('min_throttle', 1000)
            elif 'mincommand' in params:
                push_set('mincommand', 1000)
            else:
                push_set('min_throttle', 1000)
        elif rid.startswith('pid_high_'):
            # reduce P by 20% where possible
            # id like pid_high_p_roll or pid_high_p_roll depending on generation
            # look for key in params
            # get target key from rule msg if possible
            # fallback: find numeric pid keys and reduce top ones
            # We'll attempt to parse a key from id
            possible_key = rid.replace('pid_high_','')
            # if possible_key exists, compute new val
            if possible_key in params:
                try:
                    cur = float(params[possible_key])
                    newv = round(cur * 0.8, 3)
                    push_set(possible_key, newv)
                except Exception:
                    pass
        elif rid == 'no_failsafe':
            # provide example conservative failsafe
            push_set('failsafe_delay', 10)
            push_set('failsafe_off_delay', 60)
            push_set('failsafe_throttle', 1000)
            # no automatic suggestion to change action (land/drop) to avoid risky commands
        elif rid == 'failsafe_throttle_high':
            # reduce somewhat
            if 'failsafe_throttle' in params:
                try:
                    cur = float(params['failsafe_throttle'])
                    newv = max(1000, int(cur * 0.9))
                    push_set('failsafe_throttle', newv)
                except Exception:
                    pass
        elif rid == 'looptime_low':
            # suggest changing to 1000 (conservative)
            if 'looptime' in params:
                push_set('looptime', 1000)
        elif rid == 'looptime_high':
            if 'looptime' in params:
                push_set('looptime', 2000)

    # If we didn't suggest any specific sets but rules indicate checks, add a conservative checklist comment
    if not fixes and rules:
        fixes.append('# Suggested actions (manual): review rules above, adjust PIDs and filter settings carefully')
    # always ensure save if any set commands
    if any(f.startswith('set ') for f in fixes):
        if fixes[-1] != 'save':
            fixes.append('save')

    return fixes

# ----------------------
# Public analyze function
# ----------------------

def analyze_dump(text: str) -> Dict[str, Any]:
    """
    Main entry point for server or local usage.
    Returns:
      {
        "summary": "...",
        "rules": [...],
        "fix_commands": [...],
        "params": {...}
      }
    """
    params = parse_dump(text)
    rules = basic_checks(params)
    fixes = suggest_cli_fixes(rules, params)

    # Compose summary
    cnt_params = len([k for k in params.keys() if not k.startswith('_')])
    severity = 'ok'
    levels = [r.get('level', '') for r in rules]
    if any(l in ('critical','danger') for l in levels):
        severity = 'critical'
    elif any(l == 'warning' for l in levels):
        severity = 'warning'
    elif any(l == 'info' for l in levels):
        severity = 'info'

    summary = f"พารามิเตอร์ที่อ่านได้: {cnt_params} รายการ · severity: {severity}"
    # return normalized structure
    return {
        'summary': summary,
        'rules': rules,
        'fix_commands': fixes,
        'params': {k: v for k, v in params.items()}
    }

# ----------------------
# CLI/test helper
# ----------------------
if __name__ == '__main__':
    import sys
    example = """# sample diff all
set min_throttle = 980
set looptime = 500
set p_roll = 95
set p_pitch = 30
set failsafe_throttle = 1300
set gyro_sample_rate = 2000
set serialrx_provider = CRSF
# end
"""
    txt = example
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r', encoding='utf8') as f:
                txt = f.read()
        except Exception as e:
            print("Cannot read file:", e)
            sys.exit(1)
    out = analyze_dump(txt)
    print(json.dumps(out, ensure_ascii=False, indent=2))
# ----------------------
# Version Detection (new)
# ----------------------

def detect_firmware_version(text: str) -> dict:
    """
    Detect firmware type and version from CLI dump header.
    Returns {'type': 'betaflight'|'inav'|'emuflight'|'unknown', 'version': '4.4.3'|None}
    """
    sample = text[:1000].upper()
    fw_type = 'unknown'
    fw_version = None

    if 'BETAFLIGHT' in sample:
        fw_type = 'betaflight'
    elif 'INAV' in sample:
        fw_type = 'inav'
    elif 'EMUFLIGHT' in sample:
        fw_type = 'emuflight'

    import re as _re
    m = _re.search(r'(\d+\.\d+\.\d+)', text[:500])
    if m:
        fw_version = m.group(1)

    # Determine if "modern" BF (4.4+) vs legacy for PID context
    is_modern_bf = False
    if fw_type == 'betaflight' and fw_version:
        try:
            parts = [int(x) for x in fw_version.split('.')]
            if parts[0] > 4 or (parts[0] == 4 and parts[1] >= 4):
                is_modern_bf = True
        except Exception:
            pass

    return {
        'type':         fw_type,
        'version':      fw_version,
        'is_modern_bf': is_modern_bf,
    }


# ----------------------
# Diff Comparator (new)
# ----------------------

def compare_dumps(dump_a: str, dump_b: str) -> dict:
    """
    Compare two CLI dumps and return diff.
    Returns:
      {
        'only_in_a':   [(key, val), ...],  # keys in A but not B
        'only_in_b':   [(key, val), ...],  # keys in B but not A
        'changed':     [(key, val_a, val_b, explanation), ...],  # keys that changed
        'same':        [(key, val), ...],  # keys identical in both
        'summary':     str
      }
    """
    params_a = parse_dump(dump_a)
    params_b = parse_dump(dump_b)

    # Filter out internal keys
    def _clean(p):
        return {k: v for k, v in p.items() if not k.startswith('_')}

    a = _clean(params_a)
    b = _clean(params_b)

    keys_a = set(a.keys())
    keys_b = set(b.keys())
    all_keys = keys_a | keys_b

    only_in_a = []
    only_in_b = []
    changed   = []
    same      = []

    # Context explanations for common changed params
    _PARAM_EXPLAIN = {
        'p_roll':           'P term Roll — ตอบสนอง roll axis',
        'p_pitch':          'P term Pitch — ตอบสนอง pitch axis',
        'i_roll':           'I term Roll — lock-in roll',
        'i_pitch':          'I term Pitch — lock-in pitch',
        'd_roll':           'D term Roll — damp oscillation roll',
        'd_pitch':          'D term Pitch — damp oscillation pitch',
        'gyro_lpf1_hz':     'Gyro LPF1 cutoff frequency',
        'dterm_lpf1_hz':    'D-term LPF1 cutoff',
        'dyn_notch_count':  'Dynamic notch filter count',
        'anti_gravity_gain':'Anti-gravity gain ระหว่าง throttle punch',
        'feedforward_roll': 'Feedforward roll — stick response derivative',
        'min_throttle':     'Min throttle — มอเตอร์ idle speed',
        'failsafe_action':  'Failsafe action เมื่อ signal lost',
    }

    for k in sorted(all_keys):
        in_a = k in a
        in_b = k in b
        if in_a and not in_b:
            only_in_a.append((k, a[k]))
        elif in_b and not in_a:
            only_in_b.append((k, b[k]))
        else:
            va, vb = a[k], b[k]
            if str(va) != str(vb):
                explain = _PARAM_EXPLAIN.get(k, 'ค่าเปลี่ยนแปลง')
                # Determine direction
                try:
                    diff_val = float(vb) - float(va)
                    direction = '↑ เพิ่มขึ้น' if diff_val > 0 else '↓ ลดลง'
                    explain += f' ({direction} {abs(diff_val):.1f})'
                except Exception:
                    pass
                changed.append((k, va, vb, explain))
            else:
                same.append((k, va))

    summary = (
        f"เปรียบเทียบ: {len(changed)} ค่าเปลี่ยน, "
        f"{len(only_in_a)} เฉพาะใน Config A, "
        f"{len(only_in_b)} เฉพาะใน Config B, "
        f"{len(same)} ค่าเหมือนกัน"
    )

    return {
        'only_in_a': only_in_a,
        'only_in_b': only_in_b,
        'changed':   changed,
        'same':      same,
        'summary':   summary,
    }
