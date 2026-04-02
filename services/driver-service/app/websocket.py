import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from shared.redis import get_redis
from shared.kafka import create_producer, publish

logger = logging.getLogger(__name__)
router = APIRouter()

# Global dictionary to store pending disconnect tasks
reconnect_tasks: Dict[str, asyncio.Task] = {}

RECONNECT_TIMEOUT = 30  # seconds

async def handle_disconnect(driver_id: str):
    """Wait for reconnect timeout, then publish disconnect event if not reconnected."""
    try:
        await asyncio.sleep(RECONNECT_TIMEOUT)
        
        # If the task is still in reconnect_tasks, it means driver didn't reconnect
        if driver_id in reconnect_tasks:
            logger.info(f"Driver {driver_id} failed to reconnect within {RECONNECT_TIMEOUT}s. Publishing disconnect.")
            
            # Publish driver.disconnected to Kafka
            producer = await create_producer()
            try:
                await publish(producer, "driver.disconnected", {
                    "driver_id": driver_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "websocket_timeout"
                }, key=driver_id)
            finally:
                await producer.stop()
            
            # Remove from Redis locations and active status
            redis = await get_redis()
            await redis.zrem("drivers:locations", driver_id)
            await redis.delete(f"driver:reconnect:{driver_id}")
            
            # Important: Remove the task from the dictionary after processing
            reconnect_tasks.pop(driver_id, None)
            
    except asyncio.CancelledError:
        logger.info(f"Reconnect task for driver {driver_id} cancelled (driver reconnected).")
        raise

@router.websocket("/ws/driver/{driver_id}/location")
async def driver_websocket_endpoint(websocket: WebSocket, driver_id: str):
    await websocket.accept()
    logger.info(f"Driver {driver_id} connected via WebSocket.")

    # 1. Handle Reconnection logic
    redis = await get_redis()
    active_ride_id = await redis.get(f"driver:active_ride:{driver_id}")
    if active_ride_id:
        if isinstance(active_ride_id, bytes):
            active_ride_id = active_ride_id.decode('utf-8')
        logger.info(f"Restoring context for driver {driver_id}: active_ride={active_ride_id}")
        await websocket.send_json({
            "type": "context_restore",
            "active_ride_id": active_ride_id
        })

    if driver_id in reconnect_tasks:
        logger.info(f"Driver {driver_id} reconnected. Cancelling pending disconnect task.")
        reconnect_tasks[driver_id].cancel()
        del reconnect_tasks[driver_id]
        
        # Clear recovery key in Redis
        await redis.delete(f"driver:reconnect:{driver_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            lat = message.get("lat")
            lng = message.get("lng")
            
            if lat is not None and lng is not None:
                # Update Redis location
                redis = await get_redis()
                await redis.geoadd("drivers:locations", (lng, lat, driver_id))
                
                # Publish to Kafka (optional, depending on if we want every ping in Kafka)
                producer = await create_producer()
                try:
                    await publish(producer, "driver.location", {
                        "driver_id": driver_id,
                        "lat": lat,
                        "lng": lng,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }, key=driver_id)
                finally:
                    await producer.stop()
                    
    except WebSocketDisconnect:
        logger.info(f"Driver {driver_id} disconnected.")
        
        # 2. Set Recovery key in Redis
        redis = await get_redis()
        await redis.setex(f"driver:reconnect:{driver_id}", RECONNECT_TIMEOUT, "pending")
        
        # 3. Start background task for disconnect recovery
        reconnect_tasks[driver_id] = asyncio.create_task(handle_disconnect(driver_id))
    except Exception as e:
        logger.error(f"WebSocket error for driver {driver_id}: {e}")
        # Treat other errors as disconnects
        if driver_id not in reconnect_tasks:
            reconnect_tasks[driver_id] = asyncio.create_task(handle_disconnect(driver_id))
