import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_dependencies():
    with patch("app.routes.get_redis", new_callable=AsyncMock) as mock_redis, \
         patch("app.routes.check_rate_limit", new_callable=AsyncMock) as mock_rl, \
         patch("app.routes.create_producer", new_callable=AsyncMock) as mock_producer, \
         patch("app.routes.publish", new_callable=AsyncMock) as mock_publish, \
         patch("app.routes.get_db", new_callable=AsyncMock) as mock_db:
        yield {
            "redis": mock_redis,
            "rate_limit": mock_rl,
            "producer": mock_producer,
            "publish": mock_publish,
            "db": mock_db
        }

def test_post_ride_request_success(mock_dependencies):
    mock_rl = mock_dependencies["rate_limit"]
    mock_rl.return_value = (True, 0)
    
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716,
        "pickup_lng": 80.2209,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 80.2707,
        "pickup_address": "Chennai Central",
        "dropoff_address": "Marina Beach"
    }
    
    # Mock DB behavior to return a ride with an ID
    with patch("app.routes.Ride") as mock_ride_cls:
        mock_ride = mock_ride_cls.return_value
        mock_ride.id = uuid.uuid4()
        mock_ride.rider_id = uuid.UUID(payload["rider_id"])
        mock_ride.pickup_lat = payload["pickup_lat"]
        mock_ride.pickup_lng = payload["pickup_lng"]
        mock_ride.dropoff_lat = payload["dropoff_lat"]
        mock_ride.dropoff_lng = payload["dropoff_lng"]
        mock_ride.pickup_address = payload["pickup_address"]
        mock_ride.dropoff_address = payload["dropoff_address"]
        mock_ride.status.value = "requested"
        mock_ride.requested_at = None

        response = client.post("/api/v1/rides/", json=payload)
        
        assert response.status_code == 201
        assert "id" in response.json()

def test_post_ride_request_rate_limited(mock_dependencies):
    mock_rl = mock_dependencies["rate_limit"]
    # Simulate rate limited: allowed=False, retry_after=45s
    mock_rl.return_value = (False, 45)
    
    payload = {
        "rider_id": str(uuid.uuid4()),
        "pickup_lat": 12.9716,
        "pickup_lng": 80.2209,
        "dropoff_lat": 13.0827,
        "dropoff_lng": 80.2707,
        "pickup_address": "Chennai Central",
        "dropoff_address": "Marina Beach"
    }
    
    response = client.post("/api/v1/rides/", json=payload)
    
    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "rate_limit_exceeded"
    assert "retry_after_seconds" in data
    assert data["retry_after_seconds"] == 45
