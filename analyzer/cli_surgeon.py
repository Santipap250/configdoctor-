# analyzer/cli_surgeon.py
"""
CLI Surgeon: parse Betaflight 'diff all' / 'dump' and produce rules + suggested CLI fixes.
เบื้องต้นใช้ rule-based checks; ขยาย rule ในอนาคตได้ง่าย
"""
import re
from typing import List, Dict

# พยายามนำเข้า rule_engine / cli_export (มีในโปรเจกต์)
try:
    from analyzer.rule_engine import evaluate_rules
except Exception:
    evaluate_rules = None

try:
    from analyzer.cli_export import build_cli_diff, validate_cli_snippet
except Exception:
    build_cli_diff = None
    validate_cli_snippet = None

def parse_dump(text: str) -> Dict[str,str]:
    """ดึงคู่ key=value จาก dump (ง่ายๆ)"""
    params = {}
    for line in text.splitlines():
        line = line.strip()
        # รูปแบบ: set name = value
        m = re.match(r'^(?:set\s+)?([a-z0-9_\-]+)\s*=\s*(.+)$', line, re.I)
        if m:
            key = m.group(1).lower()
            val = m.group(2).strip()
            # ตัด comment ถ้ามี
            val = re.split(r'\s+#', val)[0].strip()
            params[key] = val
    return params

def basic_checks(params: Dict[str,str]) -> List[Dict]:
    rules = []
    # min_throttle / mincommand
    for k in ('min_throttle', 'mincommand', 'min_throttle_percent'):
        if k in params:
            try:
                v = float(params[k])
                if v < 1000:
                    rules.append({
                        "id":"min_throttle_low",
                        "level":"warning",
                        "msg":f"min_throttle/command ต่ำ ({v}) -> อาจเกิด motor stutter/idle",
                        "suggestion":"ตรวจสอบค่า min_throttle/min_command ใน Betaflight CLI; ถ้าเกิด stutter ให้เพิ่มเล็กน้อย"
                    })
                elif v > 1100:
                    rules.append({
                        "id":"min_throttle_high",
                        "level":"info",
                        "msg":f"min_throttle ค่อนข้างสูง ({v})",
                        "suggestion":"ถ้าพบ throttle deadband ให้ลดค่าลงเพื่อการตอบสนองที่ดีขึ้น"
                    })
            except:
                pass

    # failsafe
    if not any(k for k in params.keys() if 'failsafe' in k or 'failsafe' in k):
        rules.append({
            "id":"no_failsafe",
            "level":"warning",
            "msg":"ไม่พบการตั้งค่า failsafe ชัดเจน",
            "suggestion":"ตั้งค่า failsafe action/delay ตามคู่มือ (เช่น land หรือ drop)"
        })

    # looptime
    if 'looptime' in params:
        try:
            lt = int(params['looptime'])
            if lt < 1000:
                rules.append({
                    "id":"looptime_low",
                    "level":"warning",
                    "msg":f"looptime ต่ำ ({lt} µs) — อาจไม่เหมาะกับบาง ESC/CPU",
                    "suggestion":"พิจารณาเพิ่ม looptime หากพบ instability"
                })
            if lt > 4000:
                rules.append({
                    "id":"looptime_high",
                    "level":"warning",
                    "msg":f"looptime สูง ({lt} µs) — อาจทำให้ input lag",
                    "suggestion":"ลด looptime เพื่อให้การตอบสนองดีขึ้น (ถ้าฮาร์ดแวร์รองรับ)"
                })
        except:
            pass

    # PID extremes (ตัวอย่างเช็ก p gain สูงมาก)
    for axis in ('roll','pitch','yaw'):
        pk = f'p_{axis}'
        if pk in params:
            try:
                pv = float(params[pk])
                if pv > 80:
                    rules.append({
                        "id":"pid_high_"+axis,
                        "level":"danger",
                        "msg":f"P_{axis} สูงมาก ({pv})",
                        "suggestion":"ตรวจสอบว่าค่าดังกล่าวตั้งใจหรือเกิดจาก import ผิดพลาด"
                    })
            except:
                pass

    return rules

def suggest_cli_fixes(rules: List[Dict], params: Dict[str,str]) -> List[str]:
    """สร้างชุดคำสั่ง CLI แก้ไขแบบ conservative (ตัวอย่าง)"""
    fixes = []
    for r in rules:
        if r['id'] == 'min_throttle_low':
            # set min_throttle to 1000 (เป็นตัวอย่าง conservative)
            fixes.append('set min_throttle = 1000')
        if r['id'].startswith('pid_high_'):
            axis = r['id'].split('_')[-1]
            # ลด P ลง 20% เป็นตัวอย่าง
            key = f'p_{axis}'
            try:
                cur = float(params.get(key, 0))
                new = round(cur * 0.8, 3)
                fixes.append(f'set {key} = {new}')
            except:
                pass
    return fixes

def analyze_dump(text: str) -> Dict:
    params = parse_dump(text)
    rules = []
    # ถ้ามี engine ที่มีอยู่ ให้ใช้ (rule_engine.evaluate_rules คาดว่าคืน list)
    if evaluate_rules:
        try:
            # evaluate_rules คาดรับ analysis dict; ถ้าไม่มี full analysis ให้ส่ง params ดิบ
            rules = evaluate_rules({"cli_params": params})
        except Exception:
            rules = basic_checks(params)
    else:
        rules = basic_checks(params)

    fix_cmds = suggest_cli_fixes(rules, params)

    # ผลสรุป
    summary = f"พารามิเตอร์ที่อ่านได้: {len(params)} รายการ"
    return {
        "summary": summary,
        "rules": rules,
        "fix_commands": fix_cmds,
        "params": params
    }