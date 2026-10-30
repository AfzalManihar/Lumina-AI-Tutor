# Creates backend\.venv if needed, installs dependencies, and starts the API on http://127.0.0.1:8000
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")
if (-not (Test-Path .venv)) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
pip install --quiet -r requirements.txt
if (-not (Test-Path .env)) { Write-Host "NOTE: backend\.env not found - copy ..\.env.example to backend\.env and fill in values." }
uvicorn app.main:app_factory --factory --reload --host 127.0.0.1 --port 8000
