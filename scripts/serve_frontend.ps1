# SwiftRide — Frontend Utility Server (Windows PowerShell)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$scriptDir\..\frontend\stitch-export"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Starting SwiftRide Frontend Server...   " -ForegroundColor Cyan
Write-Host " http://localhost:3000/index.html        " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Start Python HTTP server on port 3000
Start-Process "http://localhost:3000/index.html"
python -m http.server 3000
