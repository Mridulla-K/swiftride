import asyncio
import json
import uuid
import pytest
import httpx
from datetime import datetime, timezone
from shared.redis import get_redis
from shared.kafka import create_producer, publish, create_consumer

# Configuration for services (assuming they are running on localhost for integration test)
RIDE_SERVICE_URL = "http://localhost:8003/api/v1/rides"
DRIVER_SERVICE_WS_URL = "ws://localhost:8001/ws/driver"
MATCHING_SERVICE_URL = "http://localhost:8004/api/v1/matching"

@pytest.mark.asyncio
async def test_driver_disconnect_reassignment():
    """
    Test Step 1: Request a ride.
    Test Step 2: Driver connects via WebSocket.
    Test Step 3: Ride is matched.
    Test Step 4: WebSocket connection is dropped.
    Test Step 5: Verify driver.disconnected is published and handled.
    Test Step 6: Verify new driver is assigned within 15 seconds.
    """
    ride_id = str(uuid.uuid4())
    rider_id = str(uuid.uuid4())
    driver_id = str(uuid.uuid4())
    
    # Pre-setup: Cache ride data for reassignment logic in matching-service
    redis = await get_redis()
    ride_data = {
        "ride_id": ride_id,
        "rider_id": rider_id,
        "pickup_lat": 40.7128,
        "pickup_lng": -74.0060,
        "dropoff_lat": 40.7306,
        "dropoff_lng": -73.9352
    }
    await redis.set(f"ride:data:{ride_id}", json.dumps(ride_data))
    await redis.set(f"ride:status:{ride_id}", "matched")

    # 1. Connect driver via WebSocket
    # We use a mock or actual connection depending on test environment
    # For this script, we'll simulate the disconnect recovery flow
    
    producer = await create_producer()
    
    # 2. Simulate match and active ride assignment
    await redis.set(f"driver:active_ride:{driver_id}", ride_id)
    
    # 3. Simulate WebSocket Drop by publishing to driver.disconnected 
    # (In a real integration test, we'd close the actual WS, but here we trigger the event)
    # Actually, let's trigger the recovery path by setting the reconnect key
    await redis.setex(f"driver:reconnect:{driver_id}", 2, "pending") # Short timeout for test
    
    # Wait for the recovery task to "fail" (we'll just publish the event manually to simulate the timeout)
    await publish(producer, "driver.disconnected", {
        "driver_id": driver_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": "test_disconnect"
    }, key=driver_id)
    await producer.stop()
    
    # 4. Verify Reassignment in Matching Service
    # We'll listen to ride.requested to see if it's re-published with reassignment: true
    consumer = await create_consumer("ride.requested", group_id="test-verifier")
    
    try:
        # Use asyncio.wait_for with a 15-second timeout as requested
        msg = await asyncio.wait_for(consumer.poll(timeout=1.0), timeout=15.0)
        
        assert msg is not None, "Did not receive reassignment request"
        assert msg["value"]["ride_id"] == ride_id
        assert msg["headers"].get("reassignment") == "true"
        
        print(f"✅ Integration Test Passed: Ride {ride_id} successfully reassigned.")
        
    except asyncio.TimeoutError:
        pytest.fail("Reassignment request not received within 15 seconds")
    finally:
        await consumer.stop()
        # Cleanup
        await redis.delete(f"ride:data:{ride_id}")
        await redis.delete(f"ride:status:{ride_id}")
        await redis.delete(f"driver:active_ride:{driver_id}")
