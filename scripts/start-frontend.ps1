# Installs frontend dependencies and starts Vite on http://localhost:5173 (proxies /api to the backend)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\frontend")
if (-not (Test-Path node_modules)) { npm install }
npm run dev
