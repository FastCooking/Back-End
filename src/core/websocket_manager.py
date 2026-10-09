from fastapi import WebSocket


class KDSWebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_to_kitchen(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:  # noqa: BLE001
                # Tratar desconexões abruptas
                print(f"Erro ao enviar WS para KDS: {e}")

kds_ws_manager = KDSWebSocketManager()
