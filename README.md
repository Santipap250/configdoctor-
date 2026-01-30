# OBIXConfig Doctor 🛠️🚁

OBIXConfig Doctor คือเว็บแอปสำหรับวิเคราะห์และแนะนำการตั้งค่าโดรน FPV  
เช่น ใบพัด แบตเตอรี่ น้ำหนัก และสไตล์การบิน  
เหมาะสำหรับสาย Freestyle / Long-range / Save Battery

---

## 🔥 Features
- วิเคราะห์ใบพัดที่เหมาะสม
- คำนวณแรงขับต่อน้ำหนัก (Thrust / Weight)
- ประเมินเวลาในการบิน
- รองรับหลายสไตล์การบิน
- ใช้งานผ่านเว็บ (Flask)

---

## 📦 โครงสร้างโปรเจกต์
```
obixconfig-doctor/
├── app.py
├── analyzer/
├── logic/
├── templates/
├── static/
├── requirements.txt
├── Procfile
└── README.md
```

---

## 🧪 รันบนเครื่อง (Development)

```bash
git clone https://github.com/Santipap250/obixconfig-doctor.git
cd obixconfig-doctor
pip install -r requirements.txt
python app.py
```

จากนั้นเปิดเบราว์เซอร์:
```
http://127.0.0.1:5000
```

---

## 🚀 Deploy บน Render (Production)

### Environment Variables ที่ต้องตั้ง
| Key | Value |
|---|---|
| SECRET_KEY | ค่าสุ่มยาว ๆ |
| PORT | Render ตั้งให้อัตโนมัติ |

### คำสั่งรัน
Render จะใช้ `Procfile` อัตโนมัติ:
```
gunicorn app:app --bind 0.0.0.0:$PORT
```

---

## 🔐 Security
- ไม่ hardcode secret key ในโค้ด
- ใช้ Environment Variables แทน

---

## 📌 License
For educational and experimental use.
