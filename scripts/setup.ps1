# DischargePilot AI — Windows Setup Script
# Run from the project root directory:
#   .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "DischargePilot AI Setup" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# ── Check Prerequisites ───────────────────────────────────────────────────────

Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  [OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python not found. Install Python 3.11+ from python.org" -ForegroundColor Red
    exit 1
}

# Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  [OK] Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Node.js not found. Install Node.js 18+ from nodejs.org" -ForegroundColor Red
    exit 1
}

# npm
try {
    $npmVersion = npm --version 2>&1
    Write-Host "  [OK] npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] npm not found." -ForegroundColor Red
    exit 1
}

Write-Host ""

# ── Backend Setup ─────────────────────────────────────────────────────────────

Write-Host "Setting up backend..." -ForegroundColor Yellow

$BackendDir = Join-Path $ProjectRoot "backend"
Set-Location $BackendDir

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "  Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv venv
}

# Activate venv
$ActivateScript = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
    Write-Host "  [OK] Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Could not activate venv automatically" -ForegroundColor Yellow
}

# Install dependencies
Write-Host "  Installing Python dependencies..." -ForegroundColor Gray
pip install -r requirements.txt --quiet
Write-Host "  [OK] Python dependencies installed" -ForegroundColor Green

# Create .env if missing
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "  [OK] Created .env from .env.example" -ForegroundColor Green
        Write-Host "  [!] Edit .env and add your ANTHROPIC_API_KEY" -ForegroundColor Yellow
    }
}

# Create uploads directory
$UploadsDir = Join-Path $BackendDir "uploads"
if (-not (Test-Path $UploadsDir)) {
    New-Item -ItemType Directory -Path $UploadsDir | Out-Null
    Write-Host "  [OK] Created uploads directory" -ForegroundColor Green
}

# Initialize database
Write-Host "  Initializing database..." -ForegroundColor Gray
python -c "
from app.db.database import engine
from app.db import models
models.Base.metadata.create_all(bind=engine)
print('Database initialized.')
" 2>&1
Write-Host "  [OK] Database initialized" -ForegroundColor Green

Write-Host ""

# ── Frontend Setup ────────────────────────────────────────────────────────────

Write-Host "Setting up frontend..." -ForegroundColor Yellow

$FrontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $FrontendDir

Write-Host "  Installing npm dependencies..." -ForegroundColor Gray
npm install --silent
Write-Host "  [OK] npm dependencies installed" -ForegroundColor Green

# Create .env.local if missing
$FrontendEnv = Join-Path $FrontendDir ".env.local"
if (-not (Test-Path $FrontendEnv)) {
    "NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -FilePath $FrontendEnv -Encoding utf8
    "NEXT_PUBLIC_APP_NAME=DischargePilot AI" | Out-File -FilePath $FrontendEnv -Append -Encoding utf8
    Write-Host "  [OK] Created frontend .env.local" -ForegroundColor Green
}

Write-Host ""

# ── Create Output Directories ─────────────────────────────────────────────────

Set-Location $ProjectRoot
$Dirs = @("outputs", "outputs\summaries", "outputs\traces", "outputs\reports", "outputs\evaluation", "data")
foreach ($dir in $Dirs) {
    $path = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}
Write-Host "[OK] Output directories created" -ForegroundColor Green

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit backend\.env and add your ANTHROPIC_API_KEY"
Write-Host "  2. Start backend:  cd backend; uvicorn app.main:app --reload"
Write-Host "  3. Start frontend: cd frontend; npm run dev"
Write-Host "  4. Open:          http://localhost:3000"
Write-Host ""
Write-Host "Run tests:"
Write-Host "  cd backend; pytest -v"
Write-Host ""
Write-Host "Run evaluation:"
Write-Host "  python evaluation\runner.py --mode offline --scenario all"
Write-Host ""
