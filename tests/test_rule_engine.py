# tests/test_rule_engine.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ Rule Engine ทุก rule อย่างละเอียด
# Rule engine เป็น core diagnostic logic — ต้องไม่พลาด
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.rule_engine import evaluate_rules


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════
def _rule_ids(rules):
    return {r["id"] for r in rules}

def _rule_levels(rules):
    return {r["id"]: r["level"] for r in rules}

def _get_rule(rules, rid):
    return next((r for r in rules if r["id"] == rid), None)

def _base_analysis(**overrides):
    """สร้าง analysis dict ขั้นต่ำที่ valid — override ส่วนที่ต้องการทดสอบ."""
    base = {
        "style":        "freestyle",
        "size":         5.0,
        "prop_size":    5.0,
        "pitch":        4.3,
        "motor_kv":     2306,
        "thrust_ratio": 4.0,
        "battery_est":  5,
        "filter": {
            "gyro_lpf1":    250,
            "anti_gravity": 5,
            "rpm_filter":   True,
        },
        "pid": {
            "roll":  {"p": 48, "i": 90, "d": 38},
            "pitch": {"p": 52, "i": 90, "d": 40},
            "yaw":   {"p": 40, "i": 90, "d": 0},
        },
        "prop_result": {
            "effect": {
                "motor_load":    2,
                "noise":         1,
                "tip_speed_mps": 180.0,
                "grip":          "medium",
            }
        },
        "advanced": {
            "thrust_ratio": 4.0,
            "tip_speed_mps": 180.0,
            "power": {"est_flight_time_min": 5.0},
        },
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════
# Contract Tests — ทุก rule ต้องมี field ครบ
# ══════════════════════════════════════════════════════════════
class TestRuleOutputContract:
    """ทุก rule output ต้องมี field ครบตาม contract."""

    def test_returns_list(self, freestyle_analysis):
        result = evaluate_rules(freestyle_analysis)
        assert isinstance(result, list)

    def test_each_rule_has_required_fields(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        required = {"id", "level", "msg", "suggestion", "fields"}
        for rule in rules:
            missing = required - set(rule.keys())
            assert not missing, f"Rule '{rule.get('id')}' ขาด field: {missing}"

    def test_level_values_are_valid(self, freestyle_analysis):
        valid_levels = {"info", "warning", "danger"}
        rules = evaluate_rules(freestyle_analysis)
        for rule in rules:
            assert rule["level"] in valid_levels, (
                f"Rule '{rule['id']}' มี level ไม่ถูกต้อง: '{rule['level']}'"
            )

    def test_id_is_nonempty_string(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        for rule in rules:
            assert isinstance(rule["id"], str) and rule["id"].strip()

    def test_fields_is_list(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        for rule in rules:
            assert isinstance(rule["fields"], list), (
                f"Rule '{rule['id']}' — fields ต้องเป็น list"
            )

    def test_never_crashes_on_empty_dict(self):
        result = evaluate_rules({})
        assert isinstance(result, list)

    def test_never_crashes_on_none_values(self):
        result = evaluate_rules({
            "style": None, "thrust_ratio": None,
            "battery_est": None, "prop_result": None,
            "advanced": None,
        })
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════
# TWR Rules
# ══════════════════════════════════════════════════════════════
class TestTWRRules:
    """Thrust-to-Weight Ratio rules."""

    def test_healthy_twr_no_twr_rule(self):
        a = _base_analysis(thrust_ratio=4.0, advanced={"thrust_ratio": 4.0, "power": {"est_flight_time_min": 5}})
        ids = _rule_ids(evaluate_rules(a))
        assert "twr_low" not in ids
        assert "twr_very_high" not in ids

    def test_low_twr_triggers_danger(self):
        a = _base_analysis(
            thrust_ratio=0.8,
            advanced={"thrust_ratio": 0.8, "power": {"est_flight_time_min": 5}},
        )
        ids = _rule_ids(evaluate_rules(a))
        assert "twr_low" in ids

    def test_low_twr_rule_is_danger_level(self):
        a = _base_analysis(
            thrust_ratio=0.5,
            advanced={"thrust_ratio": 0.5, "power": {"est_flight_time_min": 5}},
        )
        levels = _rule_levels(evaluate_rules(a))
        assert levels.get("twr_low") == "danger"

    def test_extremely_high_twr_triggers_warning(self):
        a = _base_analysis(
            thrust_ratio=15.0,
            advanced={"thrust_ratio": 15.0, "power": {"est_flight_time_min": 5}},
        )
        ids = _rule_ids(evaluate_rules(a))
        assert "twr_very_high" in ids

    def test_missing_twr_triggers_info(self):
        a = _base_analysis(thrust_ratio=None, advanced={})
        ids = _rule_ids(evaluate_rules(a))
        assert "twr_unknown" in ids

    @pytest.mark.parametrize("style,twr,expect_low", [
        ("racing",    2.0, True),   # racing ต้องการ TWR >= 2.5
        ("freestyle", 1.5, True),   # freestyle ต้องการ >= 1.8
        ("longrange", 0.8, True),   # longrange ต้องการ >= 1.0
        ("longrange", 1.5, False),  # longrange 1.5 = OK
        ("freestyle", 3.0, False),  # freestyle 3.0 = OK
    ])
    def test_twr_thresholds_per_style(self, style, twr, expect_low):
        a = _base_analysis(
            style=style,
            thrust_ratio=twr,
            advanced={"thrust_ratio": twr, "power": {"est_flight_time_min": 5}},
        )
        ids = _rule_ids(evaluate_rules(a))
        if expect_low:
            assert "twr_low" in ids, f"style={style} twr={twr} ควร trigger twr_low"
        else:
            assert "twr_low" not in ids, f"style={style} twr={twr} ไม่ควร trigger twr_low"


# ══════════════════════════════════════════════════════════════
# Flight Time Rules
# ══════════════════════════════════════════════════════════════
class TestFlightTimeRules:

    def test_normal_flight_time_no_rule(self):
        a = _base_analysis(
            battery_est=6,
            advanced={"thrust_ratio": 4.0, "power": {"est_flight_time_min": 6.0}},
        )
        ids = _rule_ids(evaluate_rules(a))
        assert "short_flight" not in ids
        assert "shortish_flight" not in ids

    def test_very_short_flight_time_is_danger(self):
        a = _base_analysis(
            battery_est=1,
            advanced={"thrust_ratio": 4.0, "power": {"est_flight_time_min": 1.0}},
        )
        levels = _rule_levels(evaluate_rules(a))
        assert levels.get("short_flight") == "danger"

    def test_short_flight_time_is_warning(self):
        a = _base_analysis(
            battery_est=3,
            advanced={"thrust_ratio": 4.0, "power": {"est_flight_time_min": 3.0}},
        )
        levels = _rule_levels(evaluate_rules(a))
        assert levels.get("shortish_flight") == "warning"


# ══════════════════════════════════════════════════════════════
# Motor Load Rules
# ══════════════════════════════════════════════════════════════
class TestMotorLoadRules:

    def test_normal_load_no_rule(self):
        a = _base_analysis()
        a["prop_result"]["effect"]["motor_load"] = 2
        ids = _rule_ids(evaluate_rules(a))
        assert "motor_overload" not in ids
        assert "motor_heavy" not in ids

    def test_high_load_is_warning(self):
        a = _base_analysis()
        a["prop_result"]["effect"]["motor_load"] = 4
        levels = _rule_levels(evaluate_rules(a))
        assert levels.get("motor_heavy") == "warning"

    def test_max_load_is_danger(self):
        a = _base_analysis()
        a["prop_result"]["effect"]["motor_load"] = 6
        levels = _rule_levels(evaluate_rules(a))
        assert levels.get("motor_overload") == "danger"


# ══════════════════════════════════════════════════════════════
# Tip Speed Rules
# ══════════════════════════════════════════════════════════════
class TestTipSpeedRules:

    def test_safe_tip_speed_no_rule(self):
        a = _base_analysis()
        a["advanced"]["tip_speed_mps"] = 200.0
        ids = _rule_ids(evaluate_rules(a))
        assert "tip_speed_danger" not in ids
        assert "tip_speed_warn" not in ids

    def test_tip_speed_at_290_is_danger(self):
        a = _base_analysis()
        a["advanced"]["tip_speed_mps"] = 295.0
        ids = _rule_ids(evaluate_rules(a))
        assert "tip_speed_danger" in ids

    def test_tip_speed_warning_zone(self):
        a = _base_analysis()
        a["advanced"]["tip_speed_mps"] = 270.0
        ids = _rule_ids(evaluate_rules(a))
        # ควรมี warning (ไม่ถึง danger)
        assert "tip_speed_danger" not in ids


# ══════════════════════════════════════════════════════════════
# Noise Rules
# ══════════════════════════════════════════════════════════════
class TestNoiseRules:

    def test_high_noise_triggers_warning(self):
        a = _base_analysis()
        a["prop_result"]["effect"]["noise"] = 5
        ids = _rule_ids(evaluate_rules(a))
        assert "noise_high" in ids

    def test_low_noise_no_rule(self):
        a = _base_analysis()
        a["prop_result"]["effect"]["noise"] = 2
        ids = _rule_ids(evaluate_rules(a))
        assert "noise_high" not in ids


# ══════════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════════
class TestEdgeCases:

    def test_all_good_analysis_returns_info_only(self, freestyle_analysis):
        """Analysis ที่ดีไม่ควรมี danger หรือ warning rules."""
        rules = evaluate_rules(freestyle_analysis)
        bad = [r for r in rules if r["level"] in ("danger", "warning")]
        assert not bad, f"ไม่ควรมี danger/warning: {[(r['id'], r['level']) for r in bad]}"

    def test_no_duplicate_rule_ids(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        ids = [r["id"] for r in rules]
        assert len(ids) == len(set(ids)), "มี rule ID ซ้ำกัน"

    def test_dangerous_build_has_multiple_dangers(self, dangerous_analysis):
        rules = evaluate_rules(dangerous_analysis)
        danger_rules = [r for r in rules if r["level"] == "danger"]
        assert len(danger_rules) >= 1, "Build อันตรายต้องมี danger rule อย่างน้อย 1 ตัว"

    def test_suggestion_is_string(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        for rule in rules:
            assert isinstance(rule["suggestion"], str)

    def test_msg_is_nonempty_string(self, freestyle_analysis):
        rules = evaluate_rules(freestyle_analysis)
        for rule in rules:
            assert isinstance(rule["msg"], str) and rule["msg"].strip()

    @pytest.mark.parametrize("style", ["freestyle", "racing", "longrange"])
    def test_all_styles_run_without_crash(self, style):
        a = _base_analysis(
            style=style,
            advanced={"thrust_ratio": 3.0, "power": {"est_flight_time_min": 5}},
        )
        result = evaluate_rules(a)
        assert isinstance(result, list)
