# Starts the Compass API. Run from the project root.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
    & ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env - add GOOGLE_API_KEY for generative answers." -ForegroundColor Yellow
}

Write-Host "API starting on http://localhost:8010 (docs at /docs)" -ForegroundColor Green
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8010
