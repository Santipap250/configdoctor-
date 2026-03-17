# SECURITY REPORT — OBIXConfig Doctor v5.2
**Audited:** configdoctor--main  
**Date:** 2024 (automated static analysis + manual review)  
**Auditor:** Claude Security Audit Engine  
**Stack:** Python · Flask 2.3.3 · Jinja2 · Werkzeug · gunicorn · Firebase (client-side)

---

## Executive Summary (สำหรับผู้บริหาร / ไม่เชิงเทคนิค)

ระบบ OBIXConfig Doctor มีความปลอดภัยพื้นฐานที่ดี (มี CSRF, Rate Limiting, input validation, secure_filename)  
แต่พบ **ช่องโหว่ร้ายแรง 2 จุด** ระดับ High ใน dependency และ **ปัญหาระดับ Medium/Low** อีก 5 จุด  
ที่ต้องแก้ทันทีก่อน deploy production:

| # | ปัญหา | ระดับ | แก้แล้ว |
|---|-------|-------|---------|
| 1 | gunicorn 21.2.0 — HTTP Request Smuggling (CVE-2024-1135) | 🔴 HIGH | ✅ |
| 2 | Werkzeug 2.3.7 — Multipart DoS (CVE-2023-46136) | 🔴 HIGH | ✅ |
| 3 | Jinja2 < 3.1.4 — XSS ผ่าน xmlattr filter (CVE-2024-34064) | 🟡 MEDIUM | ✅ |
| 4 | SESSION_COOKIE_SECURE ปิดอยู่โดย default | 🟡 MEDIUM | ✅ |
| 5 | ไม่มี HSTS header | 🟡 MEDIUM | ✅ |
| 6 | POST routes 3 เส้นไม่มี Rate Limiting | 🟡 MEDIUM | ✅ |
| 7 | OSD export error เปิดเผย stack trace ให้ client | 🟡 MEDIUM | ✅ |
| 8 | Firebase rules แนะนำ `.read/.write = true` (insecure) | 🟡 MEDIUM | ✅ |
| 9 | CSP มี `'unsafe-inline'` ใน script-src | 🟡 MEDIUM | ⚠️ partial |

---

## รายละเอียดปัญหาแต่ละจุด

---

### [1] 🔴 HIGH — CVE-2024-1135: HTTP Request Smuggling (gunicorn)
**File:** `requirements.txt`  
**Package:** `gunicorn==21.2.0`  
**CVE:** [CVE-2024-1135](https://nvd.nist.gov/vuln/detail/CVE-2024-1135)  

**ปัญหา:** gunicorn ≤ 21.2.0 ไม่ validate `Transfer-Encoding` header อย่างถูกต้อง  
ทำให้ผู้โจมตีสามารถ smuggle HTTP request เพื่อ bypass security controls, cache poisoning,  
หรือ request hijacking ผ่าน reverse proxy (Nginx/Render)  

**ความเสี่ยง:**  
- Bypass authentication/authorization ที่ proxy layer
- Poison shared cache  
- อ่าน response ของ user อื่น (data leak)

**การแก้ไข:**
```bash
pip install "gunicorn==22.0.0"
```
**Replicate:**
```bash
pip show gunicorn | grep Version
# Version: 21.2.0  ← vulnerable
```

---

### [2] 🔴 HIGH — CVE-2023-46136: Multipart Parsing DoS (Werkzeug)
**File:** `requirements.txt`  
**Package:** `Werkzeug==2.3.7`  
**CVE:** [CVE-2023-46136](https://nvd.nist.gov/vuln/detail/CVE-2023-46136)  

**ปัญหา:** Werkzeug < 3.0.1 มี bug ใน multipart form parsing ที่ทำให้ CPU spike 100%  
เมื่อรับ request ที่สร้างขึ้นเป็นพิเศษ ทำให้ Denial of Service ได้

**ความเสี่ยง:**  
- ทำให้ server ไม่ตอบสนอง (DoS) ด้วย request เดียว
- ไม่ต้อง authenticate

**การแก้ไข:**
```bash
pip install "Werkzeug==3.0.3"
```

---

### [3] 🟡 MEDIUM — CVE-2024-34064: XSS ผ่าน xmlattr filter (Jinja2)
**File:** `requirements.txt`  
**Package:** `Jinja2>=3.1.2`  
**CVE:** [CVE-2024-34064](https://nvd.nist.gov/vuln/detail/CVE-2024-34064)  

**ปัญหา:** Jinja2 < 3.1.4 ไม่ escape `\t` (tab) และ `\n` ใน `xmlattr` filter  
ทำให้ inject attribute พิเศษได้ถ้า template ใช้ `xmlattr` กับ user input

**การแก้ไข:** Pin ให้ `Jinja2>=3.1.4,<4.0`

---

### [4] 🟡 MEDIUM — SESSION_COOKIE_SECURE ปิดโดย default
**File:** `app.py` บรรทัด 149–153  

**ปัญหา:**
```python
FORCE_SECURE = os.environ.get("FORCE_SECURE", "0") in ("1", "true", "True")
SESSION_COOKIE_SECURE=FORCE_SECURE  # default = False !
```
ถ้าไม่ตั้ง `FORCE_SECURE=1` ใน env, session cookie จะถูกส่งผ่าน HTTP ธรรมดา  
ทำให้ Cookie โดนขโมยผ่าน network sniffing (MITM attack)  

**การแก้ไข (PATCHED):**
```python
FORCE_INSECURE = os.environ.get("FORCE_INSECURE", "0") in ("1", "true", "True")
SESSION_COOKIE_SECURE=not FORCE_INSECURE  # default = True
```

---

### [5] 🟡 MEDIUM — ไม่มี HSTS Header
**File:** `app.py` ใน `set_security_headers()`  

**ปัญหา:** ไม่มี `Strict-Transport-Security` header  
Browser จะไม่บังคับ HTTPS อัตโนมัติ ทำให้ first request อาจไปบน HTTP  

**การแก้ไข (PATCHED):**
```python
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

---

### [6] 🟡 MEDIUM — POST Routes ไม่มี Rate Limiting
**File:** `app.py`  
**Routes:** `/app` (POST), `/motor-prop` (POST), `/rpm-filter` (POST)  

**ปัญหา:** 3 routes ที่รับ POST และทำ computation หนัก ไม่มี `@_rate()` decorator  
ทำให้ attacker ยิง request ซ้ำได้ไม่จำกัด → CPU exhaustion DoS  

**Proof of Concept:**
```bash
# อาจทำ server ช้าลงหรือ crash
for i in $(seq 1 500); do
  curl -s -X POST http://target/app -d "size=5&battery=4S&style=freestyle" &
done
```

**การแก้ไข (PATCHED):** เพิ่ม `@_rate("30 per minute;300 per day")` ทุก route

---

### [7] 🟡 MEDIUM — Error Detail Leak ใน OSD Export
**File:** `app.py` บรรทัดประมาณ 1022  

**ปัญหา:**
```python
except Exception as e:
    return (f"Failed to save: {e}", 500)  # ← leak stack/OS info
```
ส่ง exception message โดยตรงไปให้ client อาจเปิดเผย path, OS info หรือ disk layout  

**การแก้ไข (PATCHED):**
```python
except Exception:
    logger.exception("osd_export save failed")
    return ("Failed to save file. Please try again.", 500)
```

---

### [8] 🟡 MEDIUM — Firebase Rules แนะนำ `.read/.write = true`
**File:** `templates/landing.html` บรรทัด 2011  

**ปัญหา:** Comment ในโค้ดแนะนำให้ตั้ง Firebase Realtime Database rules เป็น  
`{ "rules": { ".read": true, ".write": true } }`  
ซึ่งทำให้ทุกคนในโลก อ่านและเขียนข้อมูลใน database ได้โดยไม่ต้อง authenticate  

**การแก้ไข (PATCHED):** แก้ comment ให้แนะนำ scoped rules ที่ปลอดภัยกว่า:
```json
{
  "rules": {
    "configdoctor": {
      "likes":   { ".read": true, ".write": true },
      "ratings": { ".read": true, ".write": true }
    },
    "$other": { ".read": false, ".write": false }
  }
}
```

---

### [9] 🟡 MEDIUM — CSP มี `'unsafe-inline'` ใน script-src
**File:** `app.py`  
**Status:** ⚠️ แก้ได้เพียง partial (เพิ่ม comment warning แล้ว)  

**ปัญหา:** `script-src 'self' 'unsafe-inline'` ทำให้ CSP ป้องกัน XSS ได้น้อยลง  
เพราะ inline `<script>` tags ทั้งหมดจะถูก execute โดยไม่ตรวจ  

**ทำไมแก้ทั้งหมดไม่ได้ทันที:** Templates มี inline `<script>` จำนวนมาก  
ต้อง migrate ทีละ template ไปใช้ nonce-based CSP ก่อน  

**Follow-up action ที่แนะนำ:**
1. ใช้ `flask-talisman` หรือ generate nonce ต่อ request
2. ย้าย inline JS ออกเป็นไฟล์ `.js` แยก
3. แทนที่ `'unsafe-inline'` ด้วย `'nonce-{random}'`

---

## สิ่งที่ตรวจและไม่พบปัญหา (Clean)

| ด้าน | ผล |
|------|-----|
| SQL Injection | ✅ ไม่มี database query โดยตรง |
| Command Injection | ✅ ไม่มี os.system/subprocess ที่รับ user input |
| Path Traversal | ✅ มี realpath + startswith guard ใน download route |
| CSRF | ✅ Flask-WTF CSRFProtect เปิดใช้งาน |
| Secret Key Hardcoded | ✅ crash ใน production ถ้าไม่ set SECRET_KEY |
| File Upload RCE | ✅ ไม่มี file upload จริง (รับเป็น JSON text เท่านั้น) |
| Template Injection (SSTI) | ✅ ไม่มี render_template_string ที่รับ user input |
| Eval/Exec ของ user input | ✅ eval/exec ที่เจอเป็นแค่ชื่อ function ไม่ใช่ user data |
| Plaintext Secrets ใน code | ✅ ไม่มี (Firebase apiKey เป็น placeholder YOUR_API_KEY) |
| X-Frame-Options | ✅ SAMEORIGIN set แล้ว |
| X-Content-Type-Options | ✅ nosniff set แล้ว |

---

## Replicate Commands (สำหรับทีม reproduce)

```bash
# ตรวจสอบ dependency versions
pip show gunicorn werkzeug jinja2

# ตรวจ SESSION_COOKIE_SECURE
grep -n "FORCE_SECURE\|SESSION_COOKIE_SECURE" app.py

# ตรวจ HSTS header
grep -n "Strict-Transport-Security\|HSTS" app.py

# ตรวจ rate limiting บน routes
grep -n "@_rate\|@app.route.*POST" app.py

# ตรวจ error leak
grep -n "Failed to save:" app.py

# ตรวจ Firebase rules comment
grep -n "read.*true.*write.*true" templates/landing.html
```

---

## แก้ไขที่ทำ (Files Changed)

| ไฟล์ | สิ่งที่เปลี่ยน |
|------|--------------|
| `requirements.txt` | gunicorn 21→22, Werkzeug 2.3.7→3.0.3, Jinja2 >=3.1.4 |
| `app.py` | SESSION_COOKIE_SECURE default True, HSTS header, Rate limit 3 routes, OSD error no-leak |
| `templates/landing.html` | Firebase rules comment → scoped rules |

---

## Recommended Follow-ups

1. **Rotate SECRET_KEY** ถ้าเคยมีค่า default ถูกใช้ใน production → generate ใหม่ด้วย `python -c "import secrets; print(secrets.token_hex(32))"`
2. **Firebase** — ถ้า database มีข้อมูลจริง: เข้า Firebase Console → Database → Rules → ตรวจสอบและ lock down
3. **Nonce-based CSP** — วางแผน migrate inline JS ออกเป็น external files เพื่อลบ `'unsafe-inline'`
4. **Add pip-audit to CI** — รัน `pip-audit -r requirements.txt` ใน GitHub Actions ทุก push
5. **Add gitleaks/trufflehog** — scan git history หา secrets ที่อาจเคย commit แล้ว
6. **Upgrade Flask** — พิจารณา migrate ไป Flask 3.x ซึ่งเป็น LTS อย่างเป็นทางการ
7. **Werkzeug debugger** — ตรวจให้แน่ใจว่า `FLASK_DEBUG=0` ใน production environment เสมอ (CVE-2024-34069)

---

*รายงานนี้จัดทำโดย automated static analysis + manual code review — ไม่มีการ execute หรือ deploy โค้ด*
