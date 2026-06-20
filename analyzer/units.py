# analyzer/units.py — OBIXConfig Doctor
# ============================================================
# Single source of truth for small shared parsing/unit helpers
# used across the Drone Analyzer pipeline (app.py, logic/presets.py,
# analyzer/thrust_logic.py, analyzer/rpm_filter_calc.py,
# analyzer/advanced_analysis.py).
#
# WHY THIS FILE EXISTS:
# Before this fix, FIVE different modules each had their own
# hand-rolled "parse battery string into cell count" function.
# They disagreed with each other on:
#   - valid clamp range (1–8 vs 1–12 vs 2–12)
#   - which string formats they could parse ("4S" vs "4s2p" vs "4S+")
# A user entering a perfectly normal battery label like "4S2P" or
# "6S 1500mAh" could silently get DIFFERENT cell counts in different
# parts of the same analysis, or — in app.py's case — could trigger
# an uncaught ValueError that silently discarded the entire propeller
# physics calculation for that request (see app.py _handle_analysis_post).
#
# This module replaces all of those with one tested implementation.
# ============================================================
from __future__ import annotations
import re
from typing import Optional, Union

# Real-world FPV battery packs run from 1S (tiny whoop) up to 12S
# (heavy long-range / cargo hex/octo builds), which is within the
# 1"-15" frame range this app explicitly supports.
MIN_CELLS = 1
MAX_CELLS = 12
DEFAULT_CELLS = 4

_CELL_RE = re.compile(r'(\d+)\s*[Ss]')


def cells_from_battery_string(
    battery: Optional[Union[str, int, float]],
    default: int = DEFAULT_CELLS,
    lo: int = MIN_CELLS,
    hi: int = MAX_CELLS,
) -> int:
    """
    Parse a battery label into a cell (S) count.

    Accepts: "4S", "4s", "6S+", "4s2p", "4S 1500mAh", "6S2P", plain "4",
    or a bare int/float. Falls back to `default` (clamped to [lo, hi])
    for anything unparseable, instead of raising — callers that need to
    know parsing failed should check `is_valid_battery_string()` first.
    """
    if battery is None:
        return max(lo, min(default, hi))
    try:
        # Bare numeric input (int, float, or numeric string with no "S")
        if isinstance(battery, (int, float)):
            return max(lo, min(int(battery), hi))
        s = str(battery).strip()
        m = _CELL_RE.search(s)
        if m:
            return max(lo, min(int(m.group(1)), hi))
        # No "S" suffix found — try parsing the whole string as a number
        # (handles plain "4" with no suffix at all).
        return max(lo, min(int(float(s)), hi))
    except (TypeError, ValueError):
        return max(lo, min(default, hi))


def is_valid_battery_string(battery: Optional[Union[str, int, float]]) -> bool:
    """True if `battery` contains a recognizable cell count at all (used by validation)."""
    if battery is None:
        return False
    if isinstance(battery, (int, float)):
        return True
    s = str(battery).strip()
    if _CELL_RE.search(s):
        return True
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


__all__ = ["cells_from_battery_string", "is_valid_battery_string", "MIN_CELLS", "MAX_CELLS", "DEFAULT_CELLS"]
