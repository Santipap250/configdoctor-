# CONFIGDOCTOR

**สรุปสั้น ๆ (ไทย)**  
ConfigDoctor เป็นแอปเว็บแบบ Flask สำหรับช่วยวิเคราะห์/แนะนำค่าการตั้งค่า (diffs / CLI exports) ของบอร์ด FC (Flight Controller) และโปรเจกต์ที่เกี่ยวข้องกับโดรน FPV — เป้าหมายคือให้คนที่เล่นโดรนสามารถคัดลอกค่า CLI, ดาวน์โหลด diff, และเปรียบเทียบค่าจากบอร์ดต่าง ๆ ได้ง่ายและปลอดภัย

---

## 🔥 จุดเด่น (Highlights)
- อ่าน/แสดงไฟล์ diff / CLI ของหลายบอร์ด (รวมเป็น repo กลาง)
- ให้ตัวอย่าง CLI ที่คัดลอกได้ทันที
- หน้าสำหรับดาวน์โหลดไฟล์ diff แบบแยกตาม FC
- ใช้งานได้ทั้งบนเครื่องพัฒนา (Termux, Linux, macOS) และบนเซิร์ฟเวอร์ (Render/Heroku/VPS/Docker)
- ถูกออกแบบให้ deploy ง่าย และ reproducible ด้วย `requirements.txt` และ `gunicorn`

---

## 📁 โครงสร้างโปรเจกต์ (ตัวอย่าง)
```
configdoctor--main/
├─ app.py
├─ requirements.txt
├─ README.md
├─ templates/
│  ├─ index.html
│  └─ ...
├─ static/
│  └─ ...
├─ analyzer/
│  └─ *.py
├─ logic/
│  └─ presets.py
└─ data/
   └─ diffs/
```

---

## ⚙️ ติดตั้งและรัน (Termux / Linux / macOS)
แนะนำ Python >= 3.9+

1. อัปเดตแพ็กเกจ (Termux)
```bash
pkg update && pkg upgrade -y
pkg install python git nano -y
```

2. สร้างและเข้า virtual environment (แนะนำ)
```bash
python -m venv .venv
source .venv/bin/activate
```

3. ติดตั้ง dependency
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. ตั้งค่า environment variables (ตัวอย่าง `.env`)
สร้างไฟล์ `.env` ใน root:
```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=changeme-to-a-random-secret
DATABASE_URL=sqlite:///data/configdoctor.db  # หรือ URL ของฐานข้อมูลจริง
```
โหลดค่า (ถ้าใช้ `python-dotenv` จะโหลดอัตโนมัติเมื่อรัน Flask)

5. รันในโหมดพัฒนา
```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5000
```
หรือ
```bash
python app.py
```
(ขึ้นกับ `app.py` ว่ามี `if __name__ == '__main__': app.run()` หรือไม่)

6. รันด้วย gunicorn (production)
```bash
gunicorn --bind 0.0.0.0:8000 app:app
```

---

## 🐳 Docker (ตัวอย่าง Dockerfile)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_ENV=production
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app", "--workers", "4"]
```

---

## 🔐 การตั้งค่า SSH / Git (สั้น)
- ใช้ Git + GitHub เพื่อเก็บไฟล์ diff และเวอร์ชันคอนโทรล
- ในกรณีของ Termux ให้สร้าง SSH key แล้วเพิ่มเข้า GitHub (เพื่อนำไฟล์ขึ้น/ดึงไฟล์)
- ตัวอย่างคำสั่ง: `git clone git@github.com:USERNAME/REPO.git`

---

## ✅ คำแนะนำสำหรับการพัฒนา (Dev workflow)
- ใช้ `pre-commit` + `black` + `flake8` หรือ `pylint` เพื่อให้โค้ดสะอาด
- สร้าง `requirements-dev.txt` สำหรับเครื่องมือพัฒนา:
```
black
pylint
pytest
pre-commit
```
- เพิ่ม unit tests สำหรับ `analyzer/*` และ logic สำคัญ

---

## 🧪 การทดสอบ
- ตัวอย่างรัน pytest:
```bash
pip install -r requirements-dev.txt
pytest tests/
```

---

## 🛠️ ปัญหาที่พบบ่อย (Troubleshooting)
- `ModuleNotFoundError`:
  - ติดตั้ง dependencies หรือ activate virtualenv หรือแก้ `PYTHONPATH`
- `PermissionError` เวลาบันทึกไฟล์:
  - ตรวจสิทธิ์โฟลเดอร์ `chmod` หรือเปลี่ยน owner
- `gunicorn` ไม่เริ่ม:
  - ตรวจ log, ตรวจค่า `FLASK_APP` และ `app:app` ชื่อโมดูลถูกต้อง

---

## 🚀 Deploy (Render / VPS / Heroku / Docker)
- **Render**: สร้าง Web Service → เลือก repo → Build Command: `pip install -r requirements.txt` → Start Command: `gunicorn app:app`
- **Heroku**: ใช้ Procfile:
```
web: gunicorn app:app
```
- **VPS**: ใช้ `systemd` service file หรือ `docker-compose`

---

## 🧾 ตัวอย่าง `systemd` unit (Linux server)
```
[Unit]
Description=ConfigDoctor Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/configdoctor
Environment="PATH=/var/www/configdoctor/.venv/bin"
ExecStart=/var/www/configdoctor/.venv/bin/gunicorn --workers 3 --bind unix:configdoctor.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```

---

## 🙋‍♂️ วิธีร่วมพัฒนา (Contributing)
- Fork → สร้าง branch → PR
- เขียน commit message ชัดเจน
- เพิ่ม unit tests ถ้าแก้ logic
- เปิด issue เมื่อเจอ bug หรือมีไอเดียใหม่

---

## 📄 License
MIT License — ใส่ไฟล์ `LICENSE` ถ้าต้องการ

---

## 🙏 ขอบคุณ & เครดิต
- ขอบคุณคนที่ contribute โค้ด, docs, และไฟล์ diff ต่าง ๆ
- ถ้าต้องการให้ผมปรับ README เป็นเวอร์ชันภาษาอังกฤษหรือแบบย่อสำหรับโพสต์บอกได้เลย

---

## สรุปแบบกะทัดรัด
1. สร้าง virtualenv  
2. `pip install -r requirements.txt`  
3. ตั้ง `.env` แล้วรัน `flask run` หรือ `gunicorn app:app`  
4. Deploy: Docker / Render / Heroku ตามสะดวก

---
