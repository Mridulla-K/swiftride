import uuid
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_websocket_location_update_and_disconnect():
    driver_id = uuid.uuid4()
    
    mock_redis = AsyncMock()
    mock_producer = AsyncMock()
    
    # We patch the functions where they are imported/used
    with patch("app.routes.get_redis", return_value=mock_redis), \
         patch("app.routes.create_producer", return_value=mock_producer), \
         patch("app.routes.publish", new_callable=AsyncMock) as mock_publish, \
         patch("app.routes.asyncio.create_task") as mock_create_task:
        
        with client.websocket_connect(f"/api/v1/drivers/ws/driver/{driver_id}/location") as websocket:
            payload = {
                "lat": 12.34,
                "lng": 56.78,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            # Send message
            websocket.send_text(json.dumps(payload))
            
        # The 'with' block exiting triggers a disconnect, which should raise WebSocketDisconnect in the route
        # Assert redis location cached
        mock_redis.setex.assert_called_once()
        args, kwargs = mock_redis.setex.call_args
        assert args[0] == f"driver:loc:{driver_id}"
        assert args[1] == 30
        
        # Assert published to kafka
        mock_publish.assert_called_once()
        args, kwargs = mock_publish.call_args
        assert args[1] == "driver.location"
        assert args[2]["driver_id"] == str(driver_id)
        assert args[2]["lat"] == 12.34
        
        # Assert disconnect handling
        mock_redis.set.assert_called_once_with(f"driver:status:{driver_id}", "offline")
        mock_create_task.assert_called_once()

def test_websocket_invalid_message():
    driver_id = uuid.uuid4()
    
    mock_redis = AsyncMock()
    mock_producer = AsyncMock()
    
    with patch("app.routes.get_redis", return_value=mock_redis), \
         patch("app.routes.create_producer", return_value=mock_producer), \
         patch("app.routes.publish", new_callable=AsyncMock) as mock_publish, \
         patch("app.routes.asyncio.create_task"):
         
        with client.websocket_connect(f"/api/v1/drivers/ws/driver/{driver_id}/location") as websocket:
            # Send invalid payload (missing timestamp)
            payload = {
                "lat": 12.34,
                "lng": 56.78,
            }
            websocket.send_text(json.dumps(payload))
            
        # Location logic shouldn't be called for invalid message
        mock_redis.setex.assert_not_called()
        mock_publish.assert_not_called()

        # Connect & disconnect logic should still happen
        mock_redis.set.assert_called_once_with(f"driver:status:{driver_id}", "offline")
