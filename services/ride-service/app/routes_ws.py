from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .websocket import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/{ride_id}")
async def websocket_endpoint(websocket: WebSocket, ride_id: str):
    await manager.connect(websocket, ride_id)
    try:
        while True:
            # We just keep the connection open to push updates from the server
            data = await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(websocket, ride_id)
        logger.info(f"Client disconnected from ride_id {ride_id}")
