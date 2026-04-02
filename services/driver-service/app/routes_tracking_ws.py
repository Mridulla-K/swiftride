from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .tracking_ws import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/track/{ride_id}")
async def websocket_endpoint(websocket: WebSocket, ride_id: str):
    await manager.connect(websocket, ride_id)
    try:
        while True:
            # This connection is for server-to-client pushes only.
            # We can receive data, but we don't do anything with it here.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, ride_id)
        logger.info(f"Client disconnected from tracking ride_id {ride_id}")
