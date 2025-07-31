from fastapi import WebSocket
from typing import Dict, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, key: str):
        try:
            await websocket.accept()
            if key not in self.active_connections:
                self.active_connections[key] = set()
            self.active_connections[key].add(websocket)
            logger.info(f"WebSocket connected for key: {key}")
        except Exception as e:
            logger.error(f"Error in WebSocket connect for key {key}: {str(e)}")
            raise

    def disconnect(self, websocket: WebSocket, key: str):
        try:
            if key in self.active_connections:
                self.active_connections[key].discard(websocket)
                logger.info(f"WebSocket disconnected for key: {key}")
                if not self.active_connections[key]:
                    del self.active_connections[key]
                    logger.info(f"No active connections left for key: {key}")
        except Exception as e:
            logger.error(f"Error in disconnect for key {key}: {str(e)}")

    async def broadcast_to_group(self, message: str, group_key: str):
        if group_key not in self.active_connections:
            logger.warning(f"No active connections for group key: {group_key}")
            return
        for connection in list(self.active_connections[group_key]):
            try:
                await connection.send_text(message)
                logger.debug(f"Sent group message for group key: {group_key}")
            except Exception as e:
                logger.error(f"Error broadcasting to group for key {group_key}: {str(e)}")
                self.disconnect(connection, group_key)