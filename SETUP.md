# 🚀 ConfigDoctor — Setup Guide

## Quick Start (5 minutes)

### 1. Clone & Navigate
```bash
git clone https://github.com/Santipap250/configdoctor-.git
cd configdoctor-
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment
```bash
cp .env.example .env

# Edit .env and set SECRET_KEY:
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
```

### 5. Create Data Directory
```bash
mkdir -p data static/downloads/osd static/downloads/diff_all
```

### 6. Run Application
```bash
python app.py
```

✅ Open http://localhost:10000 in your browser

---

## 🐳 Docker Setup

### Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data static/downloads/osd

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
```

### Build & Run
```bash
docker build -t configdoctor .
docker run -p 10000:10000 \
  -e SECRET_KEY="your-secret-key" \
  configdoctor
```

---

## 🔐 Security Configuration

### Generate Strong SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Set Environment Variables
```bash
# Production
export SECRET_KEY="your-generated-key"
export FLASK_ENV="production"
export TRUST_PROXY="1"
export FORCE_INSECURE="0"

# Development only
export FLASK_DEBUG="0"
export FLASK_ENV="development"
```

---

## 🧪 Testing

### Install Development Requirements
```bash
pip install -r requirements-dev.txt
```

### Run Tests
```bash
pytest                          # Run all tests
pytest -v                       # Verbose
pytest -k "test_analyze"        # Run specific test
pytest --cov=analyzer          # Coverage report
```

---

## 📤 Deployment

### Render.com Deployment

1. **Push to GitHub**
```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

2. **Create New Web Service on Render**
   - Connect GitHub repository
   - Set Environment Variables:
     ```
     SECRET_KEY=your-secret-key
     TRUST_PROXY=1
     FLASK_ENV=production
     ```
   - Build Command: (leave empty - uses Procfile)
   - Start Command: (leave empty - uses Procfile)

3. **Monitor Logs**
```bash
render logs --service configdoctor
```

### Heroku Deployment (Alternative)

```bash
heroku create configdoctor-app
heroku config:set SECRET_KEY="your-secret-key"
heroku config:set TRUST_PROXY="1"
git push heroku main
```

---

## 📊 Database Setup

### SQLite (Default)
- Automatically created at `data/community.db`
- WAL (Write-Ahead Logging) enabled for better concurrency
- Supports 1 writer, multiple readers

### PostgreSQL (Production)

For multi-worker deployment, migrate to PostgreSQL:

```bash
pip install psycopg2-binary
```

Update `app.py` database initialization.

---

## 🔄 Redis Setup (Optional)

For distributed rate limiting:

```bash
# Local Redis
redis-server

# or with Docker
docker run -p 6379:6379 redis:latest
```

Set in `.env`:
```
REDIS_URL=redis://localhost:6379/0
```

---

## 📝 Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'flask'`
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: `SECRET_KEY not set` error
**Solution:**
```bash
# Generate and set in .env
python -c "import secrets; print(secrets.token_hex(32))"
```

### Issue: Database permission denied
**Solution:**
```bash
mkdir -p data
chmod 755 data
```

### Issue: Port 10000 already in use
**Solution:**
```bash
PORT=5000 python app.py
# or
lsof -i :10000  # find process
kill -9 <PID>   # kill process
```

---

## 📦 Project Structure

```
configdoctor-/
├── app.py                 # Main Flask application
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── setup.py              # Python package setup
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── Procfile              # Deployment configuration
├── pytest.ini            # Test configuration
│
├── analyzer/             # Analysis modules
│   ├── prop_logic.py
│   ├── cli_surgeon.py
│   ├── blackbox_analyzer.py
│   └── ...
│
├── logic/                # Core business logic
│   └── presets.py
│
├── templates/            # HTML templates (40+ files)
│   ├── index.html
│   ├── landing.html
│   ├── pid_advisor.html
│   └── ...
│
├── static/               # Static assets
│   ├── css/
│   ├── js/
│   └── downloads/
│       ├── osd/
│       └── diff_all/
│
├── data/                 # Data directory (created on startup)
│   └── community.db      # SQLite database
│
├── tests/                # Test suite (for future)
│   └── test_*.py
│
└── README.md            # Project documentation
```

---

## 🔧 Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | CSRF & session signing key |
| `FLASK_DEBUG` | 0 | Enable debug mode (never in production) |
| `FLASK_ENV` | production | Environment (production/development) |
| `PORT` | 10000 | Server port |
| `TRUST_PROXY` | 1 | Trust X-Forwarded-For headers |
| `FORCE_INSECURE` | 0 | Allow insecure cookies (dev only) |
| `REDIS_URL` | empty | Redis connection (optional) |
| `DATABASE_PATH` | data/community.db | SQLite database path |

---

## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Gunicorn Documentation](https://gunicorn.org/)
- [Render Deployment Guide](https://docs.render.com/)
- [FPV Drone Configuration](https://configdoctor.onrender.com/)

---

## ✅ Checklist Before Production

- [ ] Generate strong `SECRET_KEY`
- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_DEBUG=0`
- [ ] Enable `TRUST_PROXY=1` (if behind proxy)
- [ ] Configure `REDIS_URL` for scaling
- [ ] Enable HTTPS/SSL
- [ ] Test rate limiting
- [ ] Verify database backups
- [ ] Set up error logging
- [ ] Monitor performance

---

**Need Help?** Visit [GitHub Issues](https://github.com/Santipap250/configdoctor-/issues)
