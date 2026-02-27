# analyzer/rpm_filter_calc.py — OBIXConfig Doctor
"""
RPM Filter Frequency Calculator for Betaflight FPV Drones.

Given motor KV and battery cell count, calculates:
- Estimated RPM at various throttle levels (20%, 50%, 70%, 100%)
- Harmonic frequencies (1×, 2×, 3×, 4×) for RPM filter notch setup
- Recommended dyn_notch_min, dyn_notch_max, dyn_notch_count values
- Ready-to-paste Betaflight CLI commands

Physics:
  RPM_unloaded = KV × V_full
  RPM_loaded   ≈ RPM_unloaded × load_factor (0.75 typical for FPV)
  Freq_Hz = RPM / 60

Note: These are estimates. Always verify with blackbox + RPM filter graph.
"""

from __future__ import annotations
from typing import Dict, Any, List

_NOMINAL_CELL_V = 3.7    # V (nominal for energy calcs)
_MAX_CELL_V     = 4.2    # V (fully charged)
_LOAD_FACTOR    = 0.75   # RPM under load vs unloaded (typical FPV)

# Throttle → fraction of max loaded RPM
_THROTTLE_LEVELS = {
    "20%":  0.20,
    "50%":  0.50,
    "70%":  0.70,
    "100%": 1.00,
}

_HARMONICS = [1, 2, 3, 4]


def _cells_from_str(s) -> int:
    try:
        c = int(str(s).upper().replace("S", "").strip())
        return max(2, min(c, 12))
    except Exception:
        return 4


def calculate_rpm_filter(kv: int, battery: str, prop_size: float = 5.0) -> Dict[str, Any]:
    """
    Calculate RPM filter frequencies for Betaflight notch setup.

    Args:
        kv:         Motor KV rating
        battery:    Battery string e.g. "4S", "6S", or integer cells
        prop_size:  Prop diameter in inches (for context/notes)

    Returns dict:
        throttle_table: list of {throttle, rpm, harmonics: [{n, hz}]}
        recommended:    {dyn_notch_min, dyn_notch_max, dyn_notch_count}
        cli_commands:   list of CLI strings ready to paste
        warnings:       list of warning strings
        notes:          contextual notes
    """
    cells = _cells_from_str(battery)
    v_max = cells * _MAX_CELL_V

    # Max unloaded RPM and loaded RPM
    rpm_unloaded_max = kv * v_max
    rpm_loaded_max   = rpm_unloaded_max * _LOAD_FACTOR

    throttle_table: List[Dict] = []
    all_freqs: List[float] = []

    for label, frac in _THROTTLE_LEVELS.items():
        rpm_at_throttle = rpm_loaded_max * frac
        harmonics = []
        for n in _HARMONICS:
            hz = round((rpm_at_throttle * n) / 60.0)
            harmonics.append({"n": n, "hz": hz, "label": f"{n}×"})
            all_freqs.append(hz)
        throttle_table.append({
            "throttle": label,
            "rpm": round(rpm_at_throttle),
            "harmonics": harmonics,
        })

    # Recommended notch window: cover 1× harmonic from 20% to 100% throttle
    min_1x = round(rpm_loaded_max * 0.20 / 60.0)
    max_1x = round(rpm_loaded_max * 1.00 / 60.0)

    # BF dyn_notch typically needs to cover 1× fundamental
    # Add 20% margins for variance and different flying conditions
    notch_min = max(60, round(min_1x * 0.80 / 10) * 10)   # round to 10Hz
    notch_max = min(1000, round(max_1x * 1.20 / 10) * 10)

    # Notch count: more harmonics = more notches needed
    # High KV + high cells → more harmonics significant
    notch_count = 3 if (cells >= 6 or kv >= 2200) else 2

    warnings: List[str] = []
    if cells >= 7 and kv > 1500:
        warnings.append(f"⚠️ KV {kv} สูงบน {cells}S — RPM harmonic จะอยู่ในย่านความถี่สูงมาก ระวัง motor ร้อน")
    if notch_max > 700:
        warnings.append(f"⚠️ Max harmonic freq สูง ({notch_max}Hz) — ตรวจสอบว่า RPM filter mode = ON ใน BF Configurator")
    if kv > 3000 and cells >= 4:
        warnings.append(f"⚠️ KV {kv} สูงมากบน {cells}S — ตรวจสอบ ESC motor demag และการ balance ใบพัดก่อน")

    # CLI commands
    cli_commands = [
        f"# === RPM Filter Setup (KV={kv}, {cells}S) ===",
        f"set dyn_notch_count = {notch_count}",
        f"set dyn_notch_min_hz = {notch_min}",
        f"set dyn_notch_max_hz = {notch_max}",
        f"set rpm_filter_harmonics = {notch_count}",
        f"set rpm_filter_min_hz = {notch_min}",
        "# ตรวจสอบใน Betaflight Configurator → Filters tab → RPM Filter = ON",
        "save",
    ]

    notes = [
        f"Motor max RPM (loaded, 100% throttle): {round(rpm_loaded_max):,} RPM",
        f"Fundamental frequency at max throttle: {round(rpm_loaded_max / 60):,} Hz",
        f"ค่าเหล่านี้เป็นค่าประมาณ — ควรยืนยันด้วย Blackbox + RPM Filter graph",
        f"Prop size {prop_size}\" ส่งผลต่อ actual RPM (ใบพัดใหญ่ = RPM ต่ำกว่า unloaded estimate)",
    ]

    return {
        "kv":             kv,
        "cells":          cells,
        "prop_size":      prop_size,
        "rpm_unloaded_max": round(rpm_unloaded_max),
        "rpm_loaded_max":   round(rpm_loaded_max),
        "throttle_table": throttle_table,
        "recommended": {
            "dyn_notch_min":   notch_min,
            "dyn_notch_max":   notch_max,
            "dyn_notch_count": notch_count,
        },
        "cli_commands": cli_commands,
        "warnings":     warnings,
        "notes":        notes,
    }
