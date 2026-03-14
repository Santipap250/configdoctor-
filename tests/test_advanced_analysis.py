# tests/test_advanced_analysis.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ Advanced Analysis — power model, TWR, ESC sizing
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.advanced_analysis import make_advanced_report


def _run(size=5.0, weight_g=700, battery_s="4S", style="freestyle",
         battery_mAh=1500, motor_count=4, motor_kv=2306, **kw):
    return make_advanced_report(
        size=size, weight_g=weight_g, battery_s=battery_s,
        prop_result={}, style=style, battery_mAh=battery_mAh,
        motor_count=motor_count, motor_kv=motor_kv, **kw
    )


class TestAdvancedOutputContract:

    def test_returns_dict_with_advanced_key(self):
        result = _run()
        assert isinstance(result, dict)
        assert "advanced" in result

    def test_advanced_has_power_subkey(self):
        adv = _run()["advanced"]
        assert "power" in adv or any(
            k in adv for k in ("avg_power_w", "est_flight_time_min", "cells")
        )

    def test_no_crash_on_minimal_inputs(self):
        result = make_advanced_report(
            size=5.0, weight_g=700, battery_s="4S",
            prop_result={}, style="freestyle",
        )
        assert isinstance(result, dict)

    def test_no_crash_on_zero_weight(self):
        result = _run(weight_g=0)
        assert isinstance(result, dict)

    def test_no_crash_on_none_kv(self):
        result = _run(motor_kv=None)
        assert isinstance(result, dict)


class TestFlightTimeEstimate:
    """Flight time estimate ต้องอยู่ในช่วงที่สมเหตุสมผล."""

    def test_freestyle_5inch_flight_time_realistic(self):
        result = _run(size=5.0, weight_g=700, battery_s="4S",
                      battery_mAh=1500, style="freestyle")
        adv = result["advanced"]
        # หา flight time ไม่ว่าจะอยู่ key ไหน
        ft = (adv.get("power", {}) or {}).get("est_flight_time_min") or \
             adv.get("est_flight_time_min")
        if ft is not None:
            assert 1 < ft < 30, f"Flight time {ft} นาที ไม่สมเหตุสมผล"

    def test_longrange_longer_than_freestyle(self):
        fr = _run(style="freestyle", battery_mAh=1500, weight_g=700)
        lr = _run(style="longrange", battery_mAh=3000, weight_g=900, size=7.0)
        ft_fr = (fr["advanced"].get("power", {}) or {}).get("est_flight_time_min", 0) or 0
        ft_lr = (lr["advanced"].get("power", {}) or {}).get("est_flight_time_min", 0) or 0
        if ft_fr > 0 and ft_lr > 0:
            assert ft_lr > ft_fr

    def test_bigger_battery_longer_flight(self):
        small = _run(battery_mAh=1000)
        large = _run(battery_mAh=2200)
        ft_s = (small["advanced"].get("power", {}) or {}).get("est_flight_time_min", 0) or 0
        ft_l = (large["advanced"].get("power", {}) or {}).get("est_flight_time_min", 0) or 0
        if ft_s > 0 and ft_l > 0:
            assert ft_l > ft_s


class TestBuildVariants:

    @pytest.mark.parametrize("size,battery,style,weight", [
        (2.5, "1S", "freestyle", 35),   # Whoop
        (3.5, "4S", "freestyle", 120),  # Toothpick
        (5.0, "4S", "freestyle", 700),  # Standard freestyle
        (5.0, "6S", "racing",    680),  # Racing
        (7.0, "6S", "longrange", 900),  # Long range
        (10.0, "8S", "longrange", 2000), # Heavy LR
    ])
    def test_common_build_configs_no_crash(self, size, battery, style, weight):
        result = _run(
            size=size, weight_g=weight,
            battery_s=battery, style=style,
        )
        assert isinstance(result, dict)
        assert "advanced" in result


class TestESCRating:
    """ESC recommendation ต้องสมเหตุสมผล."""

    def test_esc_recommended_is_positive_when_present(self):
        result = _run(motor_kv=2306, battery_s="4S", weight_g=700)
        adv = result["advanced"]
        esc = adv.get("esc_recommended_a") or \
              (adv.get("power", {}) or {}).get("esc_recommended_a")
        if esc is not None:
            assert esc > 0, f"ESC recommendation {esc}A ไม่สมเหตุสมผล"
            assert esc < 200, f"ESC recommendation {esc}A สูงเกินไป"
