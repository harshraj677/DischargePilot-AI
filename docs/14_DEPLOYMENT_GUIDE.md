# Deployment Guide — DischargePilot AI

Complete guide for deploying DischargePilot AI in local, Docker, and production environments.

---

## Environment Variables

### Backend (`.env`)

```env
# ── Required ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...          # Your Anthropic API key

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./dischargepilot.db   # SQLite (dev/demo)
# DATABASE_URL=postgresql://user:pass@localhost:5432/dischargepilot  # Production

# ── Application ───────────────────────────────────────────────────
APP_ENV=development                   # development | production
DEBUG=true                            # false in production
SECRET_KEY=your-secret-key-here       # For session signing

# ── Claude Model ──────────────────────────────────────────────────
CLAUDE_MODEL=claude-sonnet-4-6        # AI model to use
CLAUDE_MAX_TOKENS=8192                # Max tokens per call

# ── Agent Settings ────────────────────────────────────────────────
AGENT_MAX_ITERATIONS=20               # Max agent loop iterations
AGENT_TIMEOUT_SECONDS=300             # 5-minute timeout

# ── File Storage ──────────────────────────────────────────────────
UPLOAD_DIR=./uploads                  # PDF upload directory
MAX_UPLOAD_SIZE_MB=50                 # Maximum PDF size

# ── CORS ──────────────────────────────────────────────────────────
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Frontend (`.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000    # Backend URL
NEXT_PUBLIC_APP_NAME=DischargePilot AI
NEXT_PUBLIC_ENV=development
```

---

## Local Development Setup

### 1. Backend Setup

```powershell
# Windows PowerShell
cd "DischargePilot AI\backend"

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment file
Copy-Item .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# Initialize SQLite database
python -c "
from app.db.database import engine
from app.db import models
models.Base.metadata.create_all(bind=engine)
print('Database initialized.')
"

# Create upload directory
mkdir uploads -ErrorAction SilentlyContinue

# Run development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify at: `http://localhost:8000/docs`

### 2. Frontend Setup

```powershell
cd "DischargePilot AI\frontend"

# Install dependencies
npm install

# Copy environment file
Copy-Item .env.example .env.local
# Verify NEXT_PUBLIC_API_URL=http://localhost:8000

# Run development server
npm run dev
```

Open: `http://localhost:3000`

### 3. Run Tests

```powershell
cd "DischargePilot AI\backend"
.\venv\Scripts\Activate.ps1

# All tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Open coverage report
start htmlcov/index.html
```

---

## Docker Deployment

### Docker Compose (Recommended)

```yaml
# docker-compose.yml — in project root
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DATABASE_URL=sqlite:///./data/dischargepilot.db
      - APP_ENV=production
      - ALLOWED_ORIGINS=http://localhost:3000
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
```

```bash
# Build and start
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop
docker-compose down
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads data

# Initialize database on startup
RUN python -c "from app.db.database import engine; from app.db import models; models.Base.metadata.create_all(bind=engine)" || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

---

## Production Deployment

### Infrastructure Recommendations

| Component | Development | Production |
|-----------|-------------|------------|
| Database | SQLite | PostgreSQL 15+ |
| API Server | uvicorn (single) | uvicorn + gunicorn (multiple workers) |
| File Storage | Local filesystem | AWS S3 / Azure Blob |
| Secrets | .env file | AWS Secrets Manager / Vault |
| Monitoring | Loguru logs | Datadog / CloudWatch |
| Reverse Proxy | None | Nginx / Traefik |

### Production Backend Command

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keepalive 5 \
  --log-level info \
  --access-logfile /var/log/dischargepilot/access.log \
  --error-logfile /var/log/dischargepilot/error.log
```

### PostgreSQL Migration

```python
# backend/.env (production)
DATABASE_URL=postgresql://dischargepilot_user:securepassword@db-host:5432/dischargepilot
```

```bash
# Run Alembic migrations
cd backend
alembic upgrade head
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name dischargepilot.yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 50M;   # For PDF uploads
        proxy_read_timeout 300s;    # For long agent runs
    }

    # API Documentation
    location /docs {
        proxy_pass http://localhost:8000;
    }
}
```

---

## Claude API Setup

1. Create an account at [console.anthropic.com](https://console.anthropic.com)
2. Navigate to **API Keys** → Create new key
3. Copy the key (starts with `sk-ant-`)
4. Add to your `.env` file: `ANTHROPIC_API_KEY=sk-ant-...`

### API Usage Estimation

| Operation | API Calls | Est. Tokens/Patient |
|-----------|-----------|---------------------|
| Initial Planning | 1 call | ~2,000 |
| Per extraction tool | 1 call each | ~1,500 each |
| Summary Generation | 1 call | ~3,000 |
| Doctor Review (RLHF) | 1 call | ~2,000 |
| **Total per patient** | **~12-15 calls** | **~25,000 tokens** |

At Claude claude-sonnet-4-6 pricing, approximate cost: $0.05–$0.15 per patient (varies by document length).

---

## SQLite Configuration

### Database Location

```python
# backend/app/config.py
DATABASE_URL = "sqlite:///./dischargepilot.db"
```

### Backup Script

```powershell
# Windows PowerShell backup script
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$source = ".\dischargepilot.db"
$dest = ".\backups\dischargepilot_$timestamp.db"

New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
Copy-Item $source $dest
Write-Host "Database backed up to: $dest"
```

### Database Initialization

```python
# Reset database (development only)
from app.db.database import engine, Base
from app.db import models

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database reset complete.")
```

---

## CI/CD Recommendations

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with: { python-version: "3.11" }
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
        working-directory: backend
      - name: Run tests
        run: pytest --cov=app --cov-report=xml -v
        working-directory: backend
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          DATABASE_URL: sqlite:///./test.db
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "18" }
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
```

---

## Health Checks

### Backend Health Endpoint

```
GET /health
Response: {"status": "healthy", "version": "1.0.0", "database": "connected"}
```

### Verify Installation

```bash
# Check backend is running
curl http://localhost:8000/health

# Check API documentation is accessible
curl http://localhost:8000/docs

# Check database is initialized
curl http://localhost:8000/api/v1/patients/

# Run evaluation to verify clinical logic
cd backend
python ../evaluation/runner.py --mode offline --scenario all
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|---------|
| `ANTHROPIC_API_KEY not set` | Missing env var | Add key to `.env` file |
| `ModuleNotFoundError: fitz` | PyMuPDF not installed | `pip install pymupdf` |
| `Database not found` | Not initialized | Run `Base.metadata.create_all()` |
| `CORS error in browser` | Wrong origins | Check `ALLOWED_ORIGINS` in `.env` |
| `Agent timeout` | Long-running processing | Increase `AGENT_TIMEOUT_SECONDS` |
| `Upload fails (large PDF)` | Size limit | Increase `MAX_UPLOAD_SIZE_MB` |
| `Port 8000 already in use` | Conflict | `uvicorn app.main:app --port 8001` |
