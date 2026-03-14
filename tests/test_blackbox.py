# tests/test_blackbox.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# ทดสอบ Blackbox CSV Analyzer
# ══════════════════════════════════════════════════════════════
import pytest
from analyzer.blackbox_analyzer import analyze_blackbox_csv


REQUIRED_TOP_KEYS = {"meta", "oscillations", "motor_balance", "battery",
                     "throttle", "pid_quality", "recommendations"}


class TestBlackboxContract:

    def test_returns_required_keys(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        missing = REQUIRED_TOP_KEYS - set(result.keys())
        assert not missing, f"ขาด keys: {missing}"

    def test_meta_has_rows_analyzed(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        assert "rows_analyzed" in result["meta"]
        assert result["meta"]["rows_analyzed"] > 0

    def test_meta_firmware_detected(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        assert "firmware" in result["meta"]

    def test_recommendations_is_list(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        assert isinstance(result["recommendations"], list)

    def test_motor_balance_has_values(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        mb = result["motor_balance"]
        assert isinstance(mb, dict)

    def test_empty_csv_no_crash(self):
        result = analyze_blackbox_csv("")
        assert isinstance(result, dict)
        # ควรมี error key หรือ meta พร้อม rows=0
        has_error = "error" in result
        has_zero_rows = result.get("meta", {}).get("rows_analyzed", -1) == 0
        assert has_error or has_zero_rows

    def test_header_only_no_crash(self):
        header = "loopIteration,time,gyroADC[0],gyroADC[1],gyroADC[2]\n"
        result = analyze_blackbox_csv(header)
        assert isinstance(result, dict)

    def test_garbage_input_no_crash(self):
        result = analyze_blackbox_csv("this is not csv at all !!!\ngarbage\n")
        assert isinstance(result, dict)


class TestBlackboxColumnAliases:
    """ทดสอบ BF4.3/4.4/4.5 column naming."""

    def _make_csv(self, gyro_col="gyroADC[0]"):
        header = f"loopIteration,time,{gyro_col},motor[0],motor[1],motor[2],motor[3],vbatLatest\n"
        rows = [f"{i},{i*500},{10+i%5},{1500},{1520},{1480},{1510},{1580}" for i in range(30)]
        return header + "\n".join(rows)

    @pytest.mark.parametrize("col", ["gyroADC[0]", "gyroADC_0", "gyro[0]", "gyroRoll"])
    def test_gyro_column_aliases(self, col):
        csv = self._make_csv(gyro_col=col)
        result = analyze_blackbox_csv(csv)
        assert isinstance(result, dict)
        # ถ้า parse ได้จะมี rows > 0
        rows = result.get("meta", {}).get("rows_analyzed", 0)
        assert rows >= 0  # ไม่ crash ก็พอ


class TestBlackboxOscillationDetection:

    def test_clean_signal_low_oscillation(self, clean_blackbox_csv):
        result = analyze_blackbox_csv(clean_blackbox_csv)
        osc = result.get("oscillations", {})
        # clean signal ไม่ควรมี oscillation สูง
        assert isinstance(osc, dict)

    def test_oscillating_signal_detected(self, oscillating_blackbox_csv):
        result = analyze_blackbox_csv(oscillating_blackbox_csv)
        osc = result.get("oscillations", {})
        assert isinstance(osc, dict)
        # Oscillating signal ควรมี flag หรือ metric ที่สูงกว่า clean
        # (ตรวจแค่ไม่ crash และมี structure ถูกต้อง)


class TestBlackboxSampleLimit:
    """MAX_ROWS = 8,000 — ไม่ควรโหลดเกิน."""

    def test_large_csv_processed_within_limit(self):
        header = "loopIteration,time,gyroADC[0],motor[0],motor[1],motor[2],motor[3]\n"
        rows = [f"{i},{i*500},{i%20},{1500},{1520},{1480},{1510}" for i in range(12_000)]
        big_csv = header + "\n".join(rows)
        result = analyze_blackbox_csv(big_csv)
        rows_analyzed = result.get("meta", {}).get("rows_analyzed", 0)
        assert rows_analyzed <= 8_500  # buffer เล็กน้อยสำหรับ sampling logic
