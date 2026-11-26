$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$Root\.env")) {
    Write-Host "No .env file found. Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item "$Root\.env.example" "$Root\.env"
    Write-Host "Please edit .env with your DeyeCloud App ID, App Secret, Email, and Password." -ForegroundColor Cyan
}

Start-Process cmd.exe -ArgumentList "/k", "`"$Root\start-backend.bat`""
Start-Process cmd.exe -ArgumentList "/k", "`"$Root\start-frontend.bat`""
Write-Host "Started Backend (http://127.0.0.1:8000) and Frontend (http://localhost:5173)" -ForegroundColor Green
