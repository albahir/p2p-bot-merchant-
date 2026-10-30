"""Canal de WebSockets en tiempo real para transmisión de spreads, tasas y alertas."""

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("api_websockets")

router = APIRouter(tags=["WebSockets"])


class ConnectionManager:
    """Administrador de conexiones WebSocket activas con capacidad de broadcast."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug("Nueva conexión WebSocket establecida. Total activas: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug("Conexión WebSocket cerrada. Total activas: %d", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Transmite un mensaje en formato JSON a todos los clientes conectados."""
        payload_str = json.dumps(message)
        dead_connections: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload_str)
            except (RuntimeError, OSError, ValueError) as err:
                logger.debug("Error enviando mensaje por WebSocket: %s", err)
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket) -> None:
    """Canal bidireccional en tiempo real para cotizaciones P2P, alertas y estado."""
    await manager.connect(websocket)
    try:
        # Enviar mensaje de bienvenida con el estado inicial
        await websocket.send_json({
            "type": "connected",
            "message": "Conectado al canal en tiempo real de P2P Merchant.",
        })

        while True:
            # Mantener conexión abierta y escuchar comandos de cliente si los envía
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                action = msg.get("action")
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except (RuntimeError, OSError, ValueError) as err:
        logger.debug("Excepción en conexión WebSocket: %s", err)
        manager.disconnect(websocket)
