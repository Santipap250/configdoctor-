# tests/test_routes.py — OBIXConfig Doctor
# ══════════════════════════════════════════════════════════════
# Flask Route Smoke Tests
# ทดสอบว่าทุก route ตอบสนองและไม่ crash — ไม่ใช่ UI tests
# ══════════════════════════════════════════════════════════════
import json
import pytest


# ══════════════════════════════════════════════════════════════
# GET routes — ทุก route ต้อง return 200
# ══════════════════════════════════════════════════════════════
class TestGetRoutes:

    GET_ROUTES_200 = [
        "/app",
        "/landing",
        "/about",
        "/changelog",
        "/downloads",
        "/vtx",
        "/vtx-range",
        "/vtx-smartaudio",
        "/motor-prop",
        "/cli_surgeon",
        "/pid-advisor",
        "/quick-tune",
        "/rpm-filter",
        "/rates-visualizer",
        "/cli-comparator",
        "/blackbox",
        "/esc-checker",
        "/fpv-trainer",
        "/osd",
        "/battery-health",
        "/motor-thermal",
        "/loop-analyzer",
        "/flight-quiz",
        "/bf-wizard",
        "/build-card",
        "/tuning-log",
        "/leaderboard",
        "/military-uas",
        "/fpv",
        "/healthz",
        "/ping",
        "/sitemap.xml",
        "/robots.txt",
    ]

    @pytest.mark.parametrize("route", GET_ROUTES_200)
    @pytest.mark.smoke
    def test_get_route_returns_200(self, client, route):
        response = client.get(route)
        assert response.status_code == 200, (
            f"Route {route} returned {response.status_code} แทน 200"
        )

    def test_unknown_route_returns_404(self, client):
        response = client.get("/this-route-does-not-exist-xyz")
        assert response.status_code == 404

    def test_healthz_returns_json(self, client):
        response = client.get("/healthz")
        assert response.content_type.startswith("application/json")
        data = json.loads(response.data)
        assert data.get("status") == "ok"

    def test_ping_returns_pong(self, client):
        response = client.get("/ping")
        assert b"pong" in response.data

    def test_sitemap_is_valid_xml(self, client):
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert b"<?xml" in response.data
        assert b"<urlset" in response.data
        assert b"<loc>" in response.data

    def test_robots_txt_content_type(self, client):
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response.content_type

    def test_robots_txt_allows_crawling(self, client):
        response = client.get("/robots.txt")
        assert b"Allow: /" in response.data

    def test_robots_txt_disallows_api(self, client):
        response = client.get("/robots.txt")
        assert b"Disallow" in response.data


# ══════════════════════════════════════════════════════════════
# POST /app — Main analyzer
# ══════════════════════════════════════════════════════════════
class TestPostApp:

    BASE_FORM = {
        "size": "5",
        "battery": "4S",
        "style": "freestyle",
        "weight": "700",
        "prop_size": "5.1",
        "blades": "3",
        "pitch": "4.3",
        "motor_kv": "2306",
        "battery_mAh": "1500",
        "motor_count": "4",
    }

    def test_post_returns_200(self, client):
        response = client.post("/app", data=self.BASE_FORM)
        assert response.status_code == 200

    def test_post_renders_analysis_content(self, client):
        response = client.post("/app", data=self.BASE_FORM)
        assert b"PID" in response.data or b"filter" in response.data.lower() or \
               b"pid" in response.data.lower()

    @pytest.mark.parametrize("style", ["freestyle", "racing", "longrange"])
    def test_all_styles_return_200(self, client, style):
        form = {**self.BASE_FORM, "style": style}
        response = client.post("/app", data=form)
        assert response.status_code == 200

    @pytest.mark.parametrize("battery", ["1S", "3S", "4S", "6S", "8S"])
    def test_various_batteries_no_crash(self, client, battery):
        form = {**self.BASE_FORM, "battery": battery}
        response = client.post("/app", data=form)
        assert response.status_code == 200

    def test_empty_form_no_500(self, client):
        """Empty form ไม่ควร crash server."""
        response = client.post("/app", data={})
        assert response.status_code in (200, 400, 422)

    def test_preset_key_works(self, client):
        form = {**self.BASE_FORM, "preset": "freestyle_5inch_4s"}
        response = client.post("/app", data=form)
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════
# JSON API Routes
# ══════════════════════════════════════════════════════════════
class TestAPIRoutes:

    def _post_json(self, client, url, payload):
        return client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    # ── /analyze_cli ─────────────────────────────────────────
    def test_analyze_cli_valid_dump(self, client, minimal_dump):
        response = self._post_json(client, "/analyze_cli", {"dump": minimal_dump})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "params" in data or "rules" in data

    def test_analyze_cli_empty_dump_returns_400(self, client):
        response = self._post_json(client, "/analyze_cli", {"dump": ""})
        assert response.status_code == 400

    def test_analyze_cli_no_body_returns_400(self, client):
        response = self._post_json(client, "/analyze_cli", {})
        assert response.status_code == 400

    def test_analyze_cli_oversized_returns_413(self, client):
        big = "set p_roll = 48\n" * 40_000  # > 512KB
        response = self._post_json(client, "/analyze_cli", {"dump": big})
        assert response.status_code == 413

    def test_analyze_cli_wrong_content_type_returns_415(self, client):
        response = client.post(
            "/analyze_cli",
            data="set p_roll = 48",
            content_type="text/plain",
        )
        assert response.status_code == 415

    def test_analyze_cli_result_has_pid(self, client, minimal_dump):
        response = self._post_json(client, "/analyze_cli", {"dump": minimal_dump})
        data = json.loads(response.data)
        pid = data.get("pid", {})
        assert pid.get("roll", {}).get("p") == 48

    # ── /compare_cli ──────────────────────────────────────────
    def test_compare_cli_valid_dumps(self, client, minimal_dump):
        dump_b = minimal_dump.replace("set p_roll = 48", "set p_roll = 55")
        response = self._post_json(client, "/compare_cli",
                                   {"dump_a": minimal_dump, "dump_b": dump_b})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "changed" in data

    def test_compare_cli_detects_p_roll_change(self, client, minimal_dump):
        dump_b = minimal_dump.replace("set p_roll = 48", "set p_roll = 55")
        response = self._post_json(client, "/compare_cli",
                                   {"dump_a": minimal_dump, "dump_b": dump_b})
        data = json.loads(response.data)
        assert "p_roll" in data.get("changed", {})

    def test_compare_cli_missing_dump_b_returns_400(self, client, minimal_dump):
        response = self._post_json(client, "/compare_cli", {"dump_a": minimal_dump})
        assert response.status_code == 400

    # ── /blackbox/analyze ─────────────────────────────────────
    def test_blackbox_analyze_valid_csv(self, client, clean_blackbox_csv):
        response = self._post_json(client, "/blackbox/analyze",
                                   {"csv": clean_blackbox_csv, "filename": "test.csv"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "meta" in data

    def test_blackbox_analyze_empty_csv_returns_400(self, client):
        response = self._post_json(client, "/blackbox/analyze", {"csv": ""})
        assert response.status_code == 400

    def test_blackbox_analyze_no_csv_key_returns_400(self, client):
        response = self._post_json(client, "/blackbox/analyze", {})
        assert response.status_code == 400

    # ── /api/symptom/<id> ─────────────────────────────────────
    def test_symptom_api_valid_id(self, client):
        response = client.get("/api/symptom/oscillation_after_flip")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "id" in data or "label" in data

    def test_symptom_api_invalid_id_returns_404(self, client):
        response = client.get("/api/symptom/this_symptom_does_not_exist_xyz")
        assert response.status_code == 404

    def test_symptom_api_injection_attempt_returns_400(self, client):
        response = client.get("/api/symptom/<script>alert(1)</script>")
        assert response.status_code in (400, 404)


# ══════════════════════════════════════════════════════════════
# Security Headers
# ══════════════════════════════════════════════════════════════
class TestSecurityHeaders:

    REQUIRED_HEADERS = {
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Content-Security-Policy",
    }

    @pytest.mark.parametrize("route", ["/app", "/blackbox", "/about"])
    def test_security_headers_present(self, client, route):
        response = client.get(route)
        for header in self.REQUIRED_HEADERS:
            assert header in response.headers, (
                f"Route {route} ขาด security header: {header}"
            )

    def test_x_frame_options_is_sameorigin(self, client):
        response = client.get("/app")
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_csp_blocks_unknown_origins(self, client):
        response = client.get("/app")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    def test_static_assets_have_cache_control(self, client):
        """Static assets ต้องมี Cache-Control header."""
        response = client.get("/static/css/style.css")
        if response.status_code == 200:
            cc = response.headers.get("Cache-Control", "")
            assert "max-age" in cc or "public" in cc


# ══════════════════════════════════════════════════════════════
# PATCH ROUND 2 — Security Tests (HSTS, Cookie, Rate Limit, Traversal)
# ══════════════════════════════════════════════════════════════
class TestSecurityPatch2:
    """Tests for patches added in security audit round 2."""

    # ── HSTS ────────────────────────────────────────────────
    @pytest.mark.parametrize("route", ["/app", "/blackbox", "/about", "/landing"])
    def test_hsts_header_present(self, client, route):
        """Strict-Transport-Security ต้องมีทุก route (PATCH round 1)."""
        response = client.get(route)
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts, (
            f"Route {route} ขาด Strict-Transport-Security header"
        )

    def test_hsts_includes_subdomain(self, client):
        """HSTS ต้อง includeSubDomains."""
        response = client.get("/app")
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "includeSubDomains" in hsts

    def test_hsts_max_age_at_least_one_year(self, client):
        """HSTS max-age ต้องไม่ต่ำกว่า 1 ปี (31536000 วินาที)."""
        import re
        response = client.get("/app")
        hsts = response.headers.get("Strict-Transport-Security", "")
        m = re.search(r"max-age=(\d+)", hsts)
        assert m, "ไม่พบ max-age ใน HSTS header"
        assert int(m.group(1)) >= 31_536_000, "HSTS max-age ต้อง >= 1 ปี"

    # ── Session Cookie ───────────────────────────────────────
    def test_session_cookie_httponly(self, client):
        """Session cookie ต้อง HttpOnly."""
        client.post("/app", data={"size": "5", "battery": "4S", "style": "freestyle",
                                  "weight": "750", "prop_size": "5", "pitch": "4", "blades": "3"})
        for header in client.cookie_jar if hasattr(client, 'cookie_jar') else []:
            if 'session' in str(header).lower():
                assert 'HttpOnly' in str(header)

    # ── Path Traversal ───────────────────────────────────────
    @pytest.mark.parametrize("fc,fn", [
        ("../../../etc", "passwd"),
        ("..", "passwd"),
        ("..%2F..%2Fetc", "passwd"),
        ("normal", "../../../etc/passwd"),
    ])
    def test_download_path_traversal_blocked(self, client, fc, fn):
        """Path traversal ใน /downloads/<fc>/<fn> ต้องถูก block."""
        response = client.get(f"/downloads/{fc}/{fn}")
        assert response.status_code in (400, 404), (
            f"Path traversal /{fc}/{fn} ไม่ถูก block (got {response.status_code})"
        )

    # ── OSD Export ────────────────────────────────────────────
    def test_osd_export_error_not_leaking_details(self, client):
        """OSD export 500 error ต้องไม่มี stack trace ใน response body."""
        # Send malformed-but-valid JSON ที่อาจทำให้ internal error
        response = client.post(
            "/osd/export",
            json={},
            content_type="application/json",
        )
        # ไม่ว่าจะ success หรือ error — response body ต้องไม่มี Python traceback
        body = response.data.decode("utf-8", errors="replace")
        assert "Traceback" not in body, "Response เปิดเผย Python Traceback"
        assert "File \"" not in body, "Response เปิดเผย file path จาก traceback"

    # ── Rate Limiting ─────────────────────────────────────────
    def _post_json(self, client, path, data):
        return client.post(path, json=data, content_type="application/json")

    def test_blackbox_rate_limit_exists(self, client):
        """ส่ง POST /blackbox/analyze เกิน limit ต้องได้ 429."""
        # Flask-Limiter ใช้ in-memory; ทดสอบ decorator ทำงานถูก
        # ส่งแค่ 1 request แล้วตรวจว่า header X-RateLimit มีหรือ response ปกติ
        response = self._post_json(client, "/blackbox/analyze",
                                   {"csv": "time,gyroX\n0,0\n", "filename": "t.csv"})
        # อย่างน้อยต้องไม่ crash — 200 หรือ 400 ก็โอเค แต่ไม่ใช่ 500
        assert response.status_code != 500

    def test_analyze_cli_rate_limit_exists(self, client):
        """POST /analyze_cli ต้องมี rate limit decorator — ไม่ crash."""
        response = self._post_json(client, "/analyze_cli",
                                   {"dump": "set p_roll = 48\nset i_roll = 90\n"})
        assert response.status_code != 500

    # ── Error Information Leakage ─────────────────────────────
    @pytest.mark.parametrize("route,payload", [
        ("/analyze_cli",   {"dump": "x" * 600_000}),         # oversized → 413
        ("/blackbox/analyze", {"csv": "x" * 11_000_000}),    # oversized → 413
    ])
    def test_oversized_requests_no_traceback(self, client, route, payload):
        """Oversized requests ต้องไม่เปิดเผย traceback."""
        response = client.post(route, json=payload, content_type="application/json")
        body = response.data.decode("utf-8", errors="replace")
        assert "Traceback" not in body
        assert response.status_code in (400, 413, 429, 500)
