# Opens the backend in a new PowerShell window and runs the frontend in this one. MongoDB must already be running.
$ErrorActionPreference = "Stop"
Start-Process powershell -ArgumentList "-NoExit","-File","$PSScriptRoot\start-backend.ps1"
& "$PSScriptRoot\start-frontend.ps1"
