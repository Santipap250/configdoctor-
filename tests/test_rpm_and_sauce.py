# tests/test_rpm_filter.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ RPM Filter Calculator
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.rpm_filter_calc import calculate_rpm_filter


class TestRPMFilterContract:

    REQUIRED = {"kv", "cells", "prop_size", "rpm_unloaded_max", "rpm_loaded_max"}

    def test_returns_required_keys(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        missing = self.REQUIRED - set(result.keys())
        assert not missing

    def test_kv_in_result_matches_input(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        assert result["kv"] == 2306

    def test_cells_parsed_correctly(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        assert result["cells"] == 4

    def test_rpm_unloaded_is_positive(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        assert result["rpm_unloaded_max"] > 0

    def test_rpm_loaded_less_than_unloaded(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        assert result["rpm_loaded_max"] <= result["rpm_unloaded_max"]

    def test_throttle_table_is_list_or_dict(self):
        result = calculate_rpm_filter(2306, "4S", 5.0)
        assert isinstance(result.get("throttle_table"), (list, dict))


class TestRPMFilterPhysics:

    def test_higher_kv_higher_rpm(self):
        r1 = calculate_rpm_filter(1600, "4S", 5.0)
        r2 = calculate_rpm_filter(2800, "4S", 5.0)
        assert r2["rpm_unloaded_max"] > r1["rpm_unloaded_max"]

    def test_higher_cells_higher_rpm(self):
        r4 = calculate_rpm_filter(2306, "4S", 5.0)
        r6 = calculate_rpm_filter(2306, "6S", 5.0)
        assert r6["rpm_unloaded_max"] > r4["rpm_unloaded_max"]

    @pytest.mark.parametrize("kv,battery,prop", [
        (4000, "1S", 2.5),  # Whoop
        (3000, "4S", 3.0),  # Toothpick
        (2306, "4S", 5.0),  # Standard
        (1800, "6S", 5.0),  # 6S freestyle
        (1600, "6S", 6.0),  # 6S power
        (1200, "6S", 7.0),  # LR 7"
    ])
    def test_common_configs_no_crash(self, kv, battery, prop):
        result = calculate_rpm_filter(kv, battery, prop)
        assert isinstance(result, dict)
        assert "error" not in result


# ══════════════════════════════════════════════════════════════
# test_secret_sauce.py — Secret Sauce Generator
# ══════════════════════════════════════════════════════════════
from analyzer.secret_sauce import generate_secret_sauce


def _sauce(style="freestyle", battery="4S", cls="freestyle", kv=2306, size=5.0):
    return generate_secret_sauce(
        cls_key=cls, style=style, battery=battery,
        size_inch=size, weight_g=700, motor_kv=kv,
        prop_size=5.1,
        pid={"roll": {"p": 48, "i": 90, "d": 38},
             "pitch": {"p": 52, "i": 90, "d": 40},
             "yaw":   {"p": 40, "i": 90, "d": 0}},
        flt={"gyro_lpf1": 250, "anti_gravity": 5},
    )


class TestSecretSauceContract:

    def test_returns_required_keys(self):
        result = _sauce()
        assert {"cli", "insights", "params"} <= set(result.keys())

    def test_cli_is_nonempty_string(self):
        result = _sauce()
        assert isinstance(result["cli"], str) and len(result["cli"]) > 50

    def test_cli_contains_save_command(self):
        result = _sauce()
        assert "save" in result["cli"]

    def test_cli_contains_iterm_relax(self):
        result = _sauce()
        assert "iterm_relax" in result["cli"]

    def test_cli_contains_feedforward(self):
        result = _sauce()
        assert "feedforward" in result["cli"]

    def test_cli_contains_d_min(self):
        result = _sauce()
        assert "d_min" in result["cli"]

    def test_insights_is_nonempty_list(self):
        result = _sauce()
        assert isinstance(result["insights"], list)
        assert len(result["insights"]) >= 3

    def test_each_insight_has_required_fields(self):
        result = _sauce()
        for insight in result["insights"]:
            assert "icon" in insight and "title" in insight and "body" in insight

    def test_params_is_dict_with_values(self):
        result = _sauce()
        params = result["params"]
        assert isinstance(params, dict)
        assert len(params) >= 5


class TestSecretSaucePhysics:

    def test_racing_has_higher_feedforward_than_longrange(self):
        race = _sauce(style="racing")
        lr   = _sauce(style="longrange")
        ff_race = race["params"].get("feedforward", 0)
        ff_lr   = lr["params"].get("feedforward", 0)
        assert ff_race > ff_lr

    def test_hv_has_motor_output_limit(self):
        result = _sauce(battery="6S")
        limit = result["params"].get("motor_output_limit", "100%")
        # 6S ควรมี limit < 100%
        limit_val = int(str(limit).replace("%", ""))
        assert limit_val < 100

    def test_4s_no_motor_limit_reduction(self):
        result = _sauce(battery="4S")
        limit = result["params"].get("motor_output_limit", "100%")
        limit_val = int(str(limit).replace("%", ""))
        assert limit_val == 100

    def test_iterm_cutoff_higher_for_whoops(self):
        standard = _sauce(cls="freestyle",   size=5.0)
        whoop    = _sauce(cls="nano",        size=2.5)
        cutoff_std   = standard["params"].get("iterm_relax_cutoff", 0)
        cutoff_whoop = whoop["params"].get("iterm_relax_cutoff", 0)
        assert cutoff_whoop >= cutoff_std

    @pytest.mark.parametrize("style,battery", [
        ("freestyle", "4S"), ("racing", "4S"), ("longrange", "6S"),
        ("freestyle", "6S"), ("racing",  "6S"), ("longrange", "4S"),
        ("freestyle", "1S"), ("freestyle", "8S"),
    ])
    def test_all_style_battery_combos_no_crash(self, style, battery):
        result = _sauce(style=style, battery=battery)
        assert isinstance(result, dict)
        assert "cli" in result
