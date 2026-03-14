# tests/test_cli_surgeon.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ CLI Surgeon — parser, analyzer, comparator
# CLI Surgeon เป็น feature หลักที่ user ใช้บ่อยที่สุด
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.cli_surgeon import parse_dump, analyze_dump, compare_dumps


# ══════════════════════════════════════════════════════════════
# parse_dump — Raw parser
# ══════════════════════════════════════════════════════════════
class TestParseDump:
    """ทดสอบ parse_dump() ทุก format."""

    def test_basic_set_statement(self):
        result = parse_dump("set p_roll = 48\n")
        assert result.get("p_roll") == 48

    def test_numeric_values_are_int(self):
        result = parse_dump("set min_throttle = 1070\n")
        assert isinstance(result.get("min_throttle"), int)

    def test_float_values_are_float(self):
        result = parse_dump("set motor_idle_speed = 5.5\n")
        assert isinstance(result.get("motor_idle_speed"), float)

    def test_string_values_preserved(self):
        result = parse_dump("set motor_pwm_protocol = DSHOT600\n")
        assert result.get("motor_pwm_protocol") == "DSHOT600"

    def test_comment_lines_ignored(self):
        result = parse_dump(
            "# This is a comment\n"
            "set p_roll = 55\n"
            "; another comment style\n"
        )
        assert result.get("p_roll") == 55
        assert "#" not in str(result.keys())

    def test_inline_comments_stripped(self):
        result = parse_dump("set p_roll = 55 # was 48 before\n")
        assert result.get("p_roll") == 55

    def test_empty_string_returns_empty_dict(self):
        result = parse_dump("")
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_whitespace_only_returns_empty_dict(self):
        result = parse_dump("   \n\n\t  \n")
        assert isinstance(result, dict)

    def test_multiple_pid_values(self, minimal_dump):
        result = parse_dump(minimal_dump)
        assert result.get("p_roll") == 48
        assert result.get("i_roll") == 90
        assert result.get("d_roll") == 38
        assert result.get("p_pitch") == 52
        assert result.get("p_yaw") == 40

    def test_without_set_prefix(self):
        """รองรับ format ที่ไม่มี 'set' prefix."""
        result = parse_dump("p_roll = 60\n")
        assert result.get("p_roll") == 60

    def test_dshot_bidir_parsed(self, full_dump):
        result = parse_dump(full_dump)
        assert result.get("dshot_bidir") == "ON"

    def test_large_dump_no_crash(self):
        """dump ขนาด 500 บรรทัดต้องไม่ crash."""
        lines = [f"set param_{i} = {i}\n" for i in range(500)]
        result = parse_dump("".join(lines))
        assert len(result) >= 490  # อาจมี override บางส่วน

    def test_malformed_lines_skipped(self):
        """บรรทัดที่ format ผิดต้องถูก skip ไม่ crash."""
        result = parse_dump(
            "set p_roll = 48\n"
            "this is not a valid line at all !!!\n"
            "===garbage===\n"
            "set d_roll = 38\n"
        )
        assert result.get("p_roll") == 48
        assert result.get("d_roll") == 38


# ══════════════════════════════════════════════════════════════
# analyze_dump — Full analysis pipeline
# ══════════════════════════════════════════════════════════════
class TestAnalyzeDump:
    """ทดสอบ analyze_dump() — output contract + rule quality."""

    REQUIRED_KEYS = {"summary", "rules", "fix_commands", "params"}

    def test_returns_required_keys(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        missing = self.REQUIRED_KEYS - set(result.keys())
        assert not missing, f"ขาด keys: {missing}"

    def test_summary_is_string(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        assert isinstance(result["summary"], str)

    def test_rules_is_list(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        assert isinstance(result["rules"], list)

    def test_fix_commands_is_list(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        assert isinstance(result["fix_commands"], list)

    def test_params_contains_pid(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        params = result["params"]
        assert params.get("p_roll") == 48
        assert params.get("i_roll") == 90

    def test_each_rule_has_id_level_msg(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        for rule in result["rules"]:
            assert "id" in rule and "level" in rule and "msg" in rule

    def test_fix_commands_are_strings(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        for cmd in result["fix_commands"]:
            assert isinstance(cmd, str)

    def test_dangerous_dump_has_rules(self, dangerous_dump):
        """Dump ที่มีค่าอันตรายต้องมี rules ออกมา."""
        result = analyze_dump(dangerous_dump)
        assert len(result["rules"]) > 0

    def test_dangerous_dump_has_fix_commands(self, dangerous_dump):
        result = analyze_dump(dangerous_dump)
        assert len(result["fix_commands"]) > 0

    def test_empty_dump_no_crash(self):
        result = analyze_dump("")
        assert isinstance(result, dict)

    def test_protocol_detection(self, minimal_dump):
        result = analyze_dump(minimal_dump)
        assert result["params"].get("motor_pwm_protocol") == "DSHOT600"

    def test_dshot_bidir_detected(self, full_dump):
        result = analyze_dump(full_dump)
        assert result["params"].get("dshot_bidir") == "ON"

    @pytest.mark.parametrize("bad_input", [
        None,
        123,
        [],
        "   ",
    ])
    def test_graceful_on_bad_input(self, bad_input):
        """Input ที่ไม่ถูกต้องต้องไม่ raise exception."""
        try:
            result = analyze_dump(bad_input or "")
            assert isinstance(result, dict)
        except Exception as e:
            pytest.fail(f"analyze_dump raise exception กับ input '{bad_input}': {e}")


# ══════════════════════════════════════════════════════════════
# compare_dumps — Diff engine
# ══════════════════════════════════════════════════════════════
class TestCompareDumps:
    """ทดสอบ compare_dumps() — diff ระหว่าง 2 CLI dump."""

    REQUIRED_KEYS = {"only_in_a", "only_in_b", "changed", "same", "summary"}

    def test_returns_required_keys(self, minimal_dump):
        result = compare_dumps(minimal_dump, minimal_dump)
        missing = self.REQUIRED_KEYS - set(result.keys())
        assert not missing

    def test_identical_dumps_all_same(self, minimal_dump):
        result = compare_dumps(minimal_dump, minimal_dump)
        assert result["changed"] == {}
        assert result["only_in_a"] == {}
        assert result["only_in_b"] == {}

    def test_detects_changed_pid_value(self, minimal_dump):
        dump_b = minimal_dump.replace("set p_roll = 48", "set p_roll = 55")
        result = compare_dumps(minimal_dump, dump_b)
        assert "p_roll" in result["changed"]

    def test_changed_value_shows_before_after(self, minimal_dump):
        dump_b = minimal_dump.replace("set p_roll = 48", "set p_roll = 55")
        result = compare_dumps(minimal_dump, dump_b)
        change = result["changed"].get("p_roll", {})
        # ค่า before ควรเป็น 48, after ควรเป็น 55
        assert change.get("a") == 48 or str(change.get("a")) == "48"
        assert change.get("b") == 55 or str(change.get("b")) == "55"

    def test_detects_param_only_in_a(self, minimal_dump):
        dump_b = "set p_roll = 48\nsave\n"
        result = compare_dumps(minimal_dump, dump_b)
        # minimal_dump มี param เพิ่มจาก dump_b
        assert len(result["only_in_a"]) > 0

    def test_detects_param_only_in_b(self, minimal_dump):
        dump_b = minimal_dump + "set extra_param = 999\n"
        result = compare_dumps(minimal_dump, dump_b)
        assert "extra_param" in result["only_in_b"]

    def test_summary_is_string(self, minimal_dump):
        result = compare_dumps(minimal_dump, minimal_dump)
        assert isinstance(result["summary"], str)

    def test_empty_inputs_no_crash(self):
        result = compare_dumps("", "")
        assert isinstance(result, dict)

    def test_multiple_changes_detected(self, minimal_dump):
        dump_b = (
            minimal_dump
            .replace("set p_roll = 48", "set p_roll = 60")
            .replace("set d_roll = 38", "set d_roll = 50")
            .replace("set p_yaw = 40",  "set p_yaw = 45")
        )
        result = compare_dumps(minimal_dump, dump_b)
        assert len(result["changed"]) >= 3
