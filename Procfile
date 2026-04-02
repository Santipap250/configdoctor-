# FIX C1: ลบ inline comment ออก — comment ในบรรทัดเดียวกับ command ทำให้ shell ตัด args หลัง # ออกทั้งหมด
# SQLite WAL supports 1 writer; ถ้าต้องการ multi-worker ให้ย้ายไปใช้ PostgreSQL
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 60 --preload --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -
