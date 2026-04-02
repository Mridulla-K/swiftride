import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps ride_id to a list of active WebSockets for that ride
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, ride_id: str):
        await websocket.accept()
        if ride_id not in self.active_connections:
            self.active_connections[ride_id] = []
        self.active_connections[ride_id].append(websocket)
        logger.info(f"Tracking WebSocket connected for ride_id: {ride_id}")

    def disconnect(self, websocket: WebSocket, ride_id: str):
        if ride_id in self.active_connections:
            self.active_connections[ride_id].remove(websocket)
            if not self.active_connections[ride_id]:
                del self.active_connections[ride_id]
        logger.info(f"Tracking WebSocket disconnected for ride_id: {ride_id}")

    async def broadcast(self, ride_id: str, message: dict):
        if ride_id in self.active_connections:
            for connection in self.active_connections[ride_id]:
                await connection.send_json(message)
                logger.info(f"Broadcasted location to ride_id {ride_id}")

manager = ConnectionManager()
