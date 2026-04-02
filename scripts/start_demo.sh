#!/bin/bash

# Ensure we are in project root
cd "$(dirname "$0")/.." || exit

echo "========================================="
echo " Starting SwiftRide Demo Environment... "
echo "========================================="

# 1. Start Docker compose
docker compose -f infra/docker-compose.yml up -d

echo ""
echo "Waiting for services to become healthy..."

wait_for_container() {
    local container=$1
    while true; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null)
        state_running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null)
        
        if [ "$status" == "healthy" ]; then
            break
        elif [ "$status" == "" ] && [ "$state_running" == "true" ]; then
            # If no healthcheck defined but container is running, we consider it ready
            break
        fi
        sleep 2
    done
}

# Check data stores and infra
wait_for_container "swiftride-postgres"
echo "✅ PostgreSQL ready"

wait_for_container "swiftride-redis"
echo "✅ Redis ready"

wait_for_container "swiftride-kafka"
echo "✅ Kafka ready"

# Check services
wait_for_container "swiftride-user-service"
wait_for_container "swiftride-driver-service"
wait_for_container "swiftride-matching-service"
wait_for_container "swiftride-ride-service"
wait_for_container "swiftride-pricing-service"
echo "✅ All 5 services ready"
echo "========================================="

echo "Installing simulator dependencies..."
python -m pip install websockets httpx colorama > /dev/null 2>&1

echo "Starting Simulation Layer..."
python scripts/simulate_drivers.py &
DRIVERS_PID=$!

python scripts/simulate_rides.py &
RIDES_PID=$!

echo "Opening frontend interface..."
# Get absolute path using bash pwd for reliability
HTML_PATH="$(pwd)/frontend/stitch-export/index.html"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    start "" "file:///$HTML_PATH"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    open "$HTML_PATH"
else
    xdg-open "$HTML_PATH"
fi

echo "Demo running. Press Ctrl+C to stop simulators."
wait $DRIVERS_PID $RIDES_PID
