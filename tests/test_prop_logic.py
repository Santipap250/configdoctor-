# tests/test_prop_logic.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ Prop Logic — physics calculations
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.prop_logic import analyze_propeller


REQUIRED_EFFECT_KEYS = {
    "noise", "motor_load", "efficiency", "grip",
    "est_g_per_w", "pitch_speed_kmh", "tip_speed_mps",
    "rpm_estimated", "notes",
}


class TestAnalyzePropellerContract:
    """Output contract — ทุก field ต้องมีครบ."""

    def test_returns_required_top_keys(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        assert {"summary", "recommendation", "effect"} <= set(result.keys())

    def test_effect_has_required_keys(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        missing = REQUIRED_EFFECT_KEYS - set(result["effect"].keys())
        assert not missing, f"effect ขาด keys: {missing}"

    def test_summary_is_string(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        assert isinstance(result["summary"], str) and result["summary"]

    def test_motor_load_is_numeric_0_to_6(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        ml = result["effect"]["motor_load"]
        assert isinstance(ml, (int, float))
        assert 0 <= ml <= 6

    def test_noise_is_numeric_0_to_5(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        noise = result["effect"]["noise"]
        assert isinstance(noise, (int, float))
        assert 0 <= noise <= 5

    def test_tip_speed_is_positive(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=2306, cells=4)
        ts = result["effect"]["tip_speed_mps"]
        assert ts is not None and ts > 0

    def test_rpm_estimated_is_positive(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=2306, cells=4)
        rpm = result["effect"]["rpm_estimated"]
        assert rpm is not None and rpm > 0

    def test_notes_is_list(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle")
        assert isinstance(result["effect"]["notes"], list)


class TestPropPhysics:
    """ทดสอบ physics — ค่าต้องสมเหตุสมผล."""

    def test_higher_pitch_increases_motor_load(self):
        low  = analyze_propeller(5.0, 3.0, 3, "freestyle", motor_kv=2306, cells=4)
        high = analyze_propeller(5.0, 6.0, 3, "freestyle", motor_kv=2306, cells=4)
        assert high["effect"]["motor_load"] >= low["effect"]["motor_load"]

    def test_4_blades_increases_noise_vs_3(self):
        tri  = analyze_propeller(5.0, 4.3, 3, "freestyle")
        quad = analyze_propeller(5.0, 4.3, 4, "freestyle")
        assert quad["effect"]["noise"] >= tri["effect"]["noise"]

    def test_higher_kv_increases_tip_speed(self):
        low  = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=1600, cells=4)
        high = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=2600, cells=4)
        ts_low  = low["effect"]["tip_speed_mps"] or 0
        ts_high = high["effect"]["tip_speed_mps"] or 0
        assert ts_high > ts_low

    def test_6s_has_higher_tip_speed_than_4s(self):
        s4 = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=2306, cells=4)
        s6 = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=2306, cells=6)
        ts4 = s4["effect"]["tip_speed_mps"] or 0
        ts6 = s6["effect"]["tip_speed_mps"] or 0
        assert ts6 > ts4

    @pytest.mark.parametrize("style", ["freestyle", "racing", "longrange"])
    def test_all_styles_run_without_crash(self, style):
        result = analyze_propeller(5.0, 4.3, 3, style, motor_kv=2306, cells=4)
        assert isinstance(result, dict)

    @pytest.mark.parametrize("size,blades", [
        (2.5, 2), (3.0, 3), (5.0, 3), (7.0, 3), (10.0, 2),
    ])
    def test_various_sizes_and_blades_no_crash(self, size, blades):
        result = analyze_propeller(size, 3.5, blades, "freestyle")
        assert isinstance(result, dict)


class TestPropEdgeCases:

    def test_zero_kv_no_crash(self):
        result = analyze_propeller(5.0, 4.3, 3, "freestyle", motor_kv=0, cells=4)
        assert isinstance(result, dict)

    def test_1s_battery_no_crash(self):
        result = analyze_propeller(2.5, 3.0, 3, "freestyle", motor_kv=4000, cells=1)
        assert isinstance(result, dict)

    def test_8s_battery_no_crash(self):
        result = analyze_propeller(7.0, 5.0, 3, "longrange", motor_kv=1200, cells=8)
        assert isinstance(result, dict)
