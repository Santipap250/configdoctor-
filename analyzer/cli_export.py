"""
analyzer/cli_export.py
CLI Export utility สำหรับ ConfigDoctor
ทำให้ผู้ใช้สามารถ export configuration เป็น CLI snippet
"""

def build_cli_diff(analysis):
    """
    สร้าง CLI diff output จาก analysis dict
    
    Args:
        analysis (dict): ผลจาก analyze_drone() 
    
    Returns:
        str: CLI snippet พร้อมให้ copy-paste
    """
    try:
        # สมมุติ analysis ม���: pid, filter, style, weight_class
        pid = analysis.get("pid", {})
        filt = analysis.get("filter", {})
        style = analysis.get("style", "freestyle")
        
        # ประมาณ CLI format
        lines = [
            "# OBIXConfig Doctor - Generated PID/Filter Diff",
            f"# Style: {style}",
            f"# Weight Class: {analysis.get('weight_class', 'unknown')}",
            "",
            "# --- PID Configuration ---",
        ]
        
        # Roll
        roll = pid.get("roll", {})
        lines.append(f"set p_roll = {roll.get('p', 0)}")
        lines.append(f"set i_roll = {roll.get('i', 0)}")
        lines.append(f"set d_roll = {roll.get('d', 0)}")
        
        # Pitch
        pitch = pid.get("pitch", {})
        lines.append(f"set p_pitch = {pitch.get('p', 0)}")
        lines.append(f"set i_pitch = {pitch.get('i', 0)}")
        lines.append(f"set d_pitch = {pitch.get('d', 0)}")
        
        # Yaw
        yaw = pid.get("yaw", {})
        lines.append(f"set p_yaw = {yaw.get('p', 0)}")
        lines.append(f"set i_yaw = {yaw.get('i', 0)}")
        
        # Filter
        lines.append("")
        lines.append("# --- Filter Configuration ---")
        lines.append(f"set gyro_lpf2_hz = {filt.get('gyro_lpf2', 90)}")
        lines.append(f"set dterm_lpf1_hz = {filt.get('dterm_lpf1', 120)}")
        if filt.get('dyn_notch'):
            lines.append(f"set dyn_notch_range_hz = {filt.get('dyn_notch', 200)}")
        
        lines.append("")
        lines.append("save")
        
        return "\n".join(lines)
    except Exception as e:
        return f"# Error building CLI diff: {e}"


def build_snapshot_meta(analysis):
    """
    สร้าง metadata snapshot จาก analysis
    
    Args:
        analysis (dict): ผลจาก analyze_drone()
    
    Returns:
        dict: metadata dict พร้อม timestamp, style, weight_class, etc.
    """
    try:
        from datetime import datetime
        
        meta = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
            "style": analysis.get("style", "unknown"),
            "weight_class": analysis.get("weight_class", "unknown"),
            "pid": analysis.get("pid", {}),
            "filter": analysis.get("filter", {}),
            "preset_used": analysis.get("preset_used", "custom"),
            "warnings_count": len(analysis.get("warnings", [])),
        }
        
        # optional: thrust_ratio
        if "thrust_ratio" in analysis:
            meta["thrust_ratio"] = analysis["thrust_ratio"]
        
        return meta
    except Exception as e:
        return {"error": str(e)}
