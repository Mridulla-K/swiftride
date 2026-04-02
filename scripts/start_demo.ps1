# SwiftRide — Demo Environment Startup Script (Windows PowerShell)

Set-Location $PSScriptRoot/..

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Starting SwiftRide Demo Environment... " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Start Docker compose
Write-Host "Spinning up Docker infrastructure..."
docker compose -f infra/docker-compose.yml up -d

Write-Host "`nWaiting for services to become healthy..."

function Wait-ForContainer($containerName) {
    Write-Host "Waiting for $containerName... " -NoNewline
    while ($true) {
        $status = docker inspect --format='{{.State.Health.Status}}' $containerName 2>$null
        $running = docker inspect --format='{{.State.Running}}' $containerName 2>$null
        
        if ($status -eq "healthy") {
            Write-Host "✅ Healthy" -ForegroundColor Green
            break
        } elseif ($status -eq "" -and $running -eq "true") {
            # No healthcheck but running
            Write-Host "✅ Running" -ForegroundColor Green
            break
        }
        Start-Sleep -Seconds 2
    }
}

# Check data stores
Wait-ForContainer "swiftride-postgres"
Wait-ForContainer "swiftride-redis"
Wait-ForContainer "swiftride-kafka"

# Check microservices
Wait-ForContainer "swiftride-user-service"
Wait-ForContainer "swiftride-driver-service"
Wait-ForContainer "swiftride-matching-service"
Wait-ForContainer "swiftride-ride-service"
Wait-ForContainer "swiftride-pricing-service"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "✅ ALL SERVICES READY" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "Installing simulator dependencies..."
python -m pip install websockets httpx colorama --quiet

Write-Host "Starting Simulation Layer..."
$driverJob = Start-Job -ScriptBlock { python scripts/simulate_drivers.py }
$rideJob = Start-Job -ScriptBlock { python scripts/simulate_rides.py }

Write-Host "Opening frontend interface..."
$htmlPath = Resolve-Path "frontend/stitch-export/index.html"
Start-Process "file:///$htmlPath"

Write-Host "`nDemo running! Press Ctrl+C to stop simulators and exit." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nStopping simulators..." -ForegroundColor Red
    Stop-Job $driverJob
    Stop-Job $rideJob
    Remove-Job $driverJob
    Remove-Job $rideJob
    Write-Host "Simulators stopped. Docker containers are still running in the background."
}
