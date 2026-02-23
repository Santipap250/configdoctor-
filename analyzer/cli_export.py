# analyzer/cli_export.py
"""
CLI Export utility สำหรับ ConfigDoctor
ทำให้ผู้ใช้สามารถ export configuration เป็น CLI snippet แบบ Betaflight
และสร้าง snapshot metadata พร้อมสำหรับบันทึก

Functions:
  - build_cli_diff(analysis): สร้าง Betaflight CLI diff format
  - build_snapshot_meta(analysis): สร้าง metadata snapshot
  - build_osd_cli(osd_model): สร้าง CLI format สำหรับ OSD layout
  - validate_cli_snippet(cli_text): ตรวจสอบ CLI syntax พื้นฐาน
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def build_cli_diff(analysis: Dict[str, Any]) -> str:
    """
    สร้าง Betaflight CLI diff output จาก analysis dict
    
    Args:
        analysis (dict): ผลจาก analyze_drone() ที่มี keys:
            - pid: dict of roll/pitch/yaw PID values
            - filter: dict of filter configuration
            - style: flight style (freestyle/racing/longrange)
            - weight_class: detected drone class
            - prop_result: propeller analysis result (optional)
    
    Returns:
        str: CLI snippet พร้อมให้ copy-paste ไป Betaflight Configurator
    
    Example:
        >>> analysis = {
        ...     'pid': {'roll': {'p': 40, 'i': 45, 'd': 25}, ...},
        ...     'filter': {'gyro_lpf2': 90, 'dterm_lpf1': 120},
        ...     'style': 'freestyle'
        ... }
        >>> cli = build_cli_diff(analysis)
        >>> print(cli)
        # ... CLI commands ...
    """
    try:
        pid = analysis.get("pid", {})
        filt = analysis.get("filter", {})
        style = analysis.get("style", "freestyle").lower()
        weight_class = analysis.get("weight_class", "unknown")
        prop_result = analysis.get("prop_result", {})
        
        # เตรียม lines สำหรับ CLI
        lines = [
            "# OBIXConfig Doctor - Generated PID/Filter Diff",
            f"# Style: {style}",
            f"# Weight Class: {weight_class}",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        
        # เพิ่มข้อมูลใบพัด (ถ้ามี)
        if prop_result and isinstance(prop_result, dict):
            prop_summary = prop_result.get("summary", "")
            if prop_summary:
                lines.append(f"# Propeller: {prop_summary}")
        
        lines.append("")
        lines.append("# Start command batch")
        lines.append("batch start")
        lines.append("")
        
        # ===== PID Configuration =====
        lines.append("# --- PID Configuration ---")
        lines.append("# Roll")
        roll = pid.get("roll", {})
        p_roll = int(roll.get("p", 0))
        i_roll = int(roll.get("i", 0))
        d_roll = int(roll.get("d", 0))
        lines.append(f"set p_roll = {p_roll}")
        lines.append(f"set i_roll = {i_roll}")
        lines.append(f"set d_roll = {d_roll}")
        
        lines.append("")
        lines.append("# Pitch")
        pitch = pid.get("pitch", {})
        p_pitch = int(pitch.get("p", 0))
        i_pitch = int(pitch.get("i", 0))
        d_pitch = int(pitch.get("d", 0))
        lines.append(f"set p_pitch = {p_pitch}")
        lines.append(f"set i_pitch = {i_pitch}")
        lines.append(f"set d_pitch = {d_pitch}")
        
        lines.append("")
        lines.append("# Yaw")
        yaw = pid.get("yaw", {})
        p_yaw = int(yaw.get("p", 0))
        i_yaw = int(yaw.get("i", 0))
        lines.append(f"set p_yaw = {p_yaw}")
        lines.append(f"set i_yaw = {i_yaw}")
        lines.append(f"set d_yaw = 0")
        
        # ===== Filter Configuration =====
        lines.append("")
        lines.append("# --- Filter Configuration ---")
        
        gyro_lpf2 = filt.get("gyro_lpf2", filt.get("gyro_cutoff", 90))
        dterm_lpf1 = filt.get("dterm_lpf1", filt.get("dterm_lowpass", 120))
        dyn_notch = filt.get("dyn_notch", filt.get("notch", None))
        
        lines.append(f"set gyro_lpf2_hz = {int(gyro_lpf2)}")
        lines.append(f"set dterm_lpf1_hz = {int(dterm_lpf1)}")
        
        if dyn_notch and dyn_notch != "None":
            try:
                dyn_notch_val = int(dyn_notch)
                lines.append(f"set dyn_notch_range_hz = {dyn_notch_val}")
            except (ValueError, TypeError):
                pass
        
        # ===== Flight Characteristics =====
        lines.append("")
        lines.append("# --- Flight Characteristics ---")
        
        # เพิ่มข้อเสนอแนะตามสไตล์
        style_configs = {
            "freestyle": {
                "roll_expo": 20,
                "pitch_expo": 22,
                "yaw_expo": 22,
                "roll_srate": 64,
                "pitch_srate": 64,
                "yaw_srate": 64,
            },
            "racing": {
                "roll_expo": 25,
                "pitch_expo": 25,
                "yaw_expo": 25,
                "roll_srate": 80,
                "pitch_srate": 80,
                "yaw_srate": 80,
            },
            "longrange": {
                "roll_expo": 15,
                "pitch_expo": 15,
                "yaw_expo": 15,
                "roll_srate": 40,
                "pitch_srate": 40,
                "yaw_srate": 40,
            },
            "cine": {
                "roll_expo": 12,
                "pitch_expo": 12,
                "yaw_expo": 12,
                "roll_srate": 35,
                "pitch_srate": 35,
                "yaw_srate": 35,
            },
        }
        
        style_config = style_configs.get(style, style_configs["freestyle"])
        
        lines.append(f"# Recommended rates & expo for {style}")
        lines.append(f"set roll_expo = {style_config.get('roll_expo', 20)}")
        lines.append(f"set pitch_expo = {style_config.get('pitch_expo', 22)}")
        lines.append(f"set yaw_expo = {style_config.get('yaw_expo', 22)}")
        lines.append(f"set roll_srate = {style_config.get('roll_srate', 64)}")
        lines.append(f"set pitch_srate = {style_config.get('pitch_srate', 64)}")
        lines.append(f"set yaw_srate = {style_config.get('yaw_srate', 64)}")
        
        # ===== Warnings & Notes =====
        lines.append("")
        lines.append("# --- IMPORTANT NOTES ---")
        lines.append("# These are conservative BASELINE settings.")
        lines.append("# Test these values on actual flights before permanent use.")
        lines.append("# Adjust PID values +/- 5-10% based on flight behavior:")
        lines.append("#   - If too loose: increase P & D")
        lines.append("#   - If too tight/oscillating: decrease P & D")
        lines.append("#   - If sluggish: increase I")
        lines.append("")
        
        # Add warnings from analysis if any
        if "warnings" in analysis and analysis["warnings"]:
            lines.append("# WARNINGS from ConfigDoctor:")
            for warn in analysis.get("warnings", []):
                if isinstance(warn, dict):
                    msg = warn.get("msg", str(warn))
                else:
                    msg = str(warn)
                lines.append(f"# ⚠️  {msg}")
            lines.append("")
        
        # ===== Final Commands =====
        lines.append("# End batch and save")
        lines.append("batch end")
        lines.append("save")
        lines.append("")
        lines.append("# Configuration saved successfully!")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error building CLI diff: {e}", exc_info=True)
        return f"# Error building CLI diff: {e}\n# Please check the analysis data and try again."


def build_snapshot_meta(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    สร้าง metadata snapshot จาก analysis dict
    เอาไว้เก็บบันทึก หรือ export พร้อม CLI diff
    
    Args:
        analysis (dict): ผลจาก analyze_drone()
    
    Returns:
        dict: metadata dict ที่มีข้อมูล:
            - timestamp: เวลาสร้าง
            - version: เวอร์ชัน ConfigDoctor
            - style: flight style
            - weight_class: drone class
            - pid: PID baseline values
            - filter: filter configuration
            - prop_result: propeller analysis
            - warnings_count: จำนวน warnings
            - thrust_ratio: TWR (ถ้ามี)
            - battery: battery configuration
    """
    try:
        meta = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
            "application": "OBIXConfig Doctor",
            
            # ข้อมูลหลัก
            "style": analysis.get("style", "unknown"),
            "weight_class": analysis.get("weight_class", "unknown"),
            "detected_class": analysis.get("detected_class", "unknown"),
            
            # PID & Filter
            "pid": analysis.get("pid", {}),
            "pid_baseline": analysis.get("pid_baseline", {}),
            "filter": analysis.get("filter", {}),
            "filter_baseline": analysis.get("filter_baseline", {}),
            
            # Propeller & Thrust
            "prop_result": analysis.get("prop_result", {}),
            "thrust_ratio": analysis.get("thrust_ratio", None),
            
            # Battery & Power
            "battery": analysis.get("battery", None),
            "weight": analysis.get("weight", None),
            
            # Preset Used
            "preset_used": analysis.get("preset_used", "custom"),
            
            # Status
            "warnings_count": len(analysis.get("warnings", [])),
            "warnings": analysis.get("warnings", []),
            
            # Optional: Advanced analysis
            "advanced": analysis.get("advanced", None),
            "est_flight_time_min": analysis.get("est_flight_time_min", None),
        }
        
        # Filter out None values for cleaner output
        meta = {k: v for k, v in meta.items() if v is not None or k == "advanced"}
        
        return meta
        
    except Exception as e:
        logger.error(f"Error building snapshot metadata: {e}", exc_info=True)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def build_osd_cli(osd_model: Dict[str, Any]) -> str:
    """
    สร้าง CLI format สำหรับ OSD layout configuration
    (สำหรับผู้ที่ต้องการ export OSD setup)
    
    Args:
        osd_model (dict): OSD model dict ที่มี items list
    
    Returns:
        str: CLI-style commands สำหรับ OSD
    
    Example:
        >>> osd_model = {
        ...     'width': 640,
        ...     'height': 360,
        ...     'items': [
        ...         {'id': 'it1', 'type': 'text', 'label': 'SPEED', 'x': 10, 'y': 10},
        ...     ]
        ... }
        >>> cli = build_osd_cli(osd_model)
    """
    try:
        lines = [
            "# OBIXConfig OSD Layout CLI Export",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Canvas Size: {osd_model.get('width', 640)}x{osd_model.get('height', 360)}",
            "",
            "batch start",
            "",
        ]
        
        items = osd_model.get("items", [])
        for i, item in enumerate(items, start=1):
            item_type = item.get("type", "text").upper()
            label = item.get("label", f"ITEM{i}").replace('"', '\\"')
            x = int(item.get("x", 0))
            y = int(item.get("y", 0))
            size = int(item.get("size", 14))
            color = item.get("color", "#ffffff")
            
            lines.append(f"# OSD Item {i}: {item_type}")
            lines.append(f"# set osd_item_{i}_type = {item_type}")
            lines.append(f"# set osd_item_{i}_pos = {x},{y}")
            lines.append(f"# set osd_item_{i}_size = {size}")
            lines.append(f"# set osd_item_{i}_color = {color}")
            lines.append(f"# set osd_item_{i}_label = {label}")
            lines.append("")
        
        lines.append("batch end")
        lines.append("save")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error building OSD CLI: {e}", exc_info=True)
        return f"# Error building OSD CLI: {e}"


def validate_cli_snippet(cli_text: str) -> Dict[str, Any]:
    """
    ตรวจสอบ CLI snippet เบื้องต้น
    (ไม่ใช่ validation ที่สมบูรณ์ แต่ check syntax พื้นฐาน)
    
    Args:
        cli_text (str): CLI snippet text
    
    Returns:
        dict: ผลการ validate
            - is_valid (bool): ถูกต้องหรือไม่
            - errors (list): รายการ error (ถ้ามี)
            - warnings (list): รายการ warning
            - stats (dict): สถิติ (จำนวน commands, comments, etc.)
    """
    try:
        lines = cli_text.strip().split("\n")
        errors = []
        warnings = []
        stats = {
            "total_lines": len(lines),
            "command_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
        }
        
        # Required keywords
        has_batch_start = False
        has_batch_end = False
        has_save = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                stats["blank_lines"] += 1
                continue
            
            if line.startswith("#"):
                stats["comment_lines"] += 1
                continue
            
            stats["command_lines"] += 1
            
            if line.lower() == "batch start":
                has_batch_start = True
            elif line.lower() == "batch end":
                has_batch_end = True
            elif line.lower() == "save":
                has_save = True
            elif line.startswith("set "):
                # Validate set command format
                parts = line.split("=", 1)
                if len(parts) != 2:
                    errors.append(f"Invalid set command format: {line}")
            else:
                warnings.append(f"Unknown command: {line}")
        
        # Validation rules
        if not has_batch_start:
            warnings.append("Missing 'batch start' command")
        if not has_batch_end:
            warnings.append("Missing 'batch end' command")
        if not has_save:
            errors.append("Missing 'save' command - configuration will not be saved!")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,
        }
        
    except Exception as e:
        logger.error(f"Error validating CLI snippet: {e}", exc_info=True)
        return {
            "is_valid": False,
            "errors": [str(e)],
            "warnings": [],
            "stats": {},
        }


def export_to_json(analysis: Dict[str, Any], include_cli: bool = True) -> str:
    """
    Export analysis + snapshot + optional CLI เป็น JSON format
    
    Args:
        analysis (dict): ผลจาก analyze_drone()
        include_cli (bool): รวม CLI diff ใน JSON หรือไม่
    
    Returns:
        str: JSON string
    """
    try:
        export_data = {
            "metadata": build_snapshot_meta(analysis),
        }
        
        if include_cli:
            export_data["cli_diff"] = build_cli_diff(analysis)
        
        # Add raw analysis (useful for debugging)
        export_data["analysis_keys"] = list(analysis.keys())
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}", exc_info=True)
        return json.dumps({
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }, indent=2)


def export_to_csv_row(analysis: Dict[str, Any]) -> str:
    """
    Export analysis เป็น CSV row format (สำหรับ batch analysis)
    
    Args:
        analysis (dict): ผลจาก analyze_drone()
    
    Returns:
        str: CSV-formatted row
    
    Example CSV Header:
        timestamp,style,weight_class,p_roll,i_roll,d_roll,gyro_lpf2,dterm_lpf1,thrust_ratio,warnings_count
    """
    try:
        pid = analysis.get("pid", {})
        filt = analysis.get("filter", {})
        
        row = [
            datetime.now().isoformat(),
            analysis.get("style", ""),
            analysis.get("weight_class", ""),
            int(pid.get("roll", {}).get("p", 0)),
            int(pid.get("roll", {}).get("i", 0)),
            int(pid.get("roll", {}).get("d", 0)),
            int(filt.get("gyro_lpf2", filt.get("gyro_cutoff", 0))),
            int(filt.get("dterm_lpf1", filt.get("dterm_lowpass", 0))),
            analysis.get("thrust_ratio", ""),
            len(analysis.get("warnings", [])),
        ]
        
        # Escape and join
        csv_row = ",".join([f'"{str(v).replace(chr(34), chr(34)+chr(34))}"' if isinstance(v, str) else str(v) for v in row])
        return csv_row
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}", exc_info=True)
        return ""


# ===============================
# Utility functions
# ===============================

def get_export_formats() -> Dict[str, str]:
    """ส่วนกลับรายการ export format ที่เป็นไปได้"""
    return {
        "cli": "Betaflight CLI (diff format)",
        "json": "JSON (complete data)",
        "csv": "CSV (tabular format)",
        "text": "Plain text (human-readable)",
    }


def format_pid_for_display(pid_dict: Dict[str, int]) -> str:
    """แปลง PID dict เป็น string readable format"""
    try:
        p = pid_dict.get("p", 0)
        i = pid_dict.get("i", 0)
        d = pid_dict.get("d", 0)
        return f"P:{p} I:{i} D:{d}"
    except Exception:
        return "N/A"


def compare_pid_sets(pid_current: Dict, pid_baseline: Dict) -> Dict[str, Any]:
    """เปรียบเทียบ PID sets และ return ความแตกต่าง"""
    try:
        diffs = {}
        for axis in ["roll", "pitch", "yaw"]:
            curr = pid_current.get(axis, {})
            base = pid_baseline.get(axis, {})
            
            p_diff = int(curr.get("p", 0)) - int(base.get("p", 0))
            i_diff = int(curr.get("i", 0)) - int(base.get("i", 0))
            d_diff = int(curr.get("d", 0)) - int(base.get("d", 0))
            
            diffs[axis] = {
                "p_diff": p_diff,
                "i_diff": i_diff,
                "d_diff": d_diff,
                "change_percent": (abs(p_diff) + abs(i_diff) + abs(d_diff)) / max(1, abs(int(base.get("p", 1)))) * 100,
            }
        
        return diffs
    except Exception as e:
        logger.error(f"Error comparing PID sets: {e}")
        return {}
