# Starts the Compass web console. Run from the project root.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    npm install
}

if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.local.example" ".env.local"
}

Write-Host "Console starting on http://localhost:3000" -ForegroundColor Green
npm run dev
