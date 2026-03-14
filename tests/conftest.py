# tests/conftest.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# Shared pytest fixtures สำหรับทุก test module
# ══════════════════════════════════════════════════════════════
import sys
import os
import pytest

# ── Path setup ────────────────────────────────────────────────
# เพิ่ม project root เข้า sys.path เพื่อ import modules ได้
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════
# Flask App Fixture
# ══════════════════════════════════════════════════════════════
@pytest.fixture(scope="session")
def app():
    """Create Flask test app — session-scoped (สร้างครั้งเดียว)."""
    os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")
    os.environ.setdefault("FLASK_DEBUG", "0")
    import app as app_module
    app_module.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,   # ปิด CSRF ใน test — ทดสอบ CSRF แยกต่างหาก
        SECRET_KEY="test-secret-key",
    )
    return app_module.app


@pytest.fixture()
def client(app):
    """Flask test client สำหรับ HTTP-level tests."""
    return app.test_client()


# ══════════════════════════════════════════════════════════════
# CLI Dump Fixtures
# ══════════════════════════════════════════════════════════════
@pytest.fixture()
def minimal_dump():
    """Betaflight CLI dump เล็กที่สุดที่ parse ได้."""
    return (
        "set min_throttle = 1070\n"
        "set max_throttle = 2000\n"
        "set motor_pwm_protocol = DSHOT600\n"
        "set dshot_bidir = ON\n"
        "set p_roll = 48\n"
        "set i_roll = 90\n"
        "set d_roll = 38\n"
        "set p_pitch = 52\n"
        "set i_pitch = 90\n"
        "set d_pitch = 40\n"
        "set p_yaw = 40\n"
        "set i_yaw = 90\n"
        "set d_yaw = 0\n"
        "save\n"
    )


@pytest.fixture()
def full_dump(minimal_dump):
    """Betaflight CLI dump ที่สมบูรณ์กว่า — มี filter + VTX."""
    return (
        minimal_dump
        + "set gyro_lpf1_static_hz = 250\n"
        + "set gyro_lpf2_static_hz = 500\n"
        + "set dterm_lpf1_static_hz = 110\n"
        + "set dterm_lpf2_static_hz = 170\n"
        + "set dyn_notch_count = 2\n"
        + "set vbat_min_cell_voltage = 330\n"
        + "set vbat_warning_cell_voltage = 350\n"
        + "set pid_process_denom = 2\n"
        + "# Betaflight / STM32F7X2 (MATEKF722) 4.4.2\n"
    )


@pytest.fixture()
def dangerous_dump():
    """Dump ที่มีค่า PID/filter อันตราย — ควร trigger rules."""
    return (
        "set p_roll = 120\n"   # สูงเกิน — oscillation
        "set d_roll = 80\n"    # สูงเกิน — motor heat
        "set p_yaw = 150\n"    # สูงเกิน
        "set gyro_lpf1_static_hz = 10\n"  # ต่ำเกิน — sluggish
        "set motor_pwm_protocol = PWM\n"  # เก่ามาก — ไม่แนะนำ
        "set min_throttle = 1000\n"
        "save\n"
    )


# ══════════════════════════════════════════════════════════════
# Analysis Dict Fixtures
# ══════════════════════════════════════════════════════════════
@pytest.fixture()
def freestyle_analysis():
    """Analysis dict จำลองสำหรับ 5\" Freestyle 4S."""
    return {
        "style":        "freestyle",
        "size":         5.0,
        "prop_size":    5.1,
        "pitch":        4.3,
        "motor_kv":     2306,
        "thrust_ratio": 4.2,
        "battery_est":  5,
        "filter": {
            "gyro_lpf1":   250,
            "gyro_lpf2":   None,
            "dterm_lpf1":  110,
            "anti_gravity": 5,
            "rpm_filter":  True,
        },
        "pid": {
            "roll":  {"p": 48, "i": 90, "d": 38},
            "pitch": {"p": 52, "i": 90, "d": 40},
            "yaw":   {"p": 40, "i": 90, "d": 0},
        },
        "prop_result": {
            "effect": {
                "motor_load":    3,
                "noise":         2,
                "tip_speed_mps": 200.0,
                "grip":          "medium",
                "efficiency":    "good",
            }
        },
        "advanced": {
            "thrust_ratio": 4.2,
            "power": {"est_flight_time_min": 5.2},
        },
    }


@pytest.fixture()
def dangerous_analysis(freestyle_analysis):
    """Analysis dict ที่ควร trigger danger rules."""
    d = dict(freestyle_analysis)
    d["thrust_ratio"] = 0.5       # TWR ต่ำมาก
    d["battery_est"] = 1          # เวลาบินสั้นมาก
    d["advanced"] = {
        "thrust_ratio": 0.5,
        "tip_speed_mps": 310.0,   # เกิน 290 = อันตราย
        "power": {"est_flight_time_min": 1.0},
    }
    d["prop_result"]["effect"]["motor_load"] = 6   # โหลดสูงสุด
    d["prop_result"]["effect"]["noise"] = 5
    return d


# ══════════════════════════════════════════════════════════════
# Blackbox CSV Fixtures
# ══════════════════════════════════════════════════════════════
def _make_blackbox_csv(rows: int = 100, oscillating: bool = False) -> str:
    """สร้าง Blackbox CSV จำลอง."""
    header = (
        "loopIteration,time,gyroADC[0],gyroADC[1],gyroADC[2],"
        "axisP[0],axisP[1],axisD[0],axisD[1],"
        "motor[0],motor[1],motor[2],motor[3],vbatLatest\n"
    )
    lines = [header]
    for i in range(rows):
        # oscillating gyro signal (sine-like alternating)
        gyro = (100 * ((-1) ** i)) if oscillating else (10 + i % 8)
        lines.append(
            f"{i},{i * 500},{gyro},{gyro // 2},{3},"
            f"{45 + i % 4},{48 + i % 3},{36 + i % 5},{38 + i % 4},"
            f"{1500 + i % 20},{1520 + i % 15},{1480 + i % 18},{1510 + i % 12},{1580}\n"
        )
    return "".join(lines)


@pytest.fixture()
def clean_blackbox_csv():
    """Blackbox CSV ที่ gyro signal เรียบ."""
    return _make_blackbox_csv(rows=120, oscillating=False)


@pytest.fixture()
def oscillating_blackbox_csv():
    """Blackbox CSV ที่มี oscillation ชัดเจน."""
    return _make_blackbox_csv(rows=120, oscillating=True)
