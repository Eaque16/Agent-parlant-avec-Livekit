from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..database import get_conversation

router = APIRouter()


class StateConnections:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[conversation_id].add(websocket)

    def disconnect(self, conversation_id: str, websocket: WebSocket) -> None:
        self._connections[conversation_id].discard(websocket)

    async def broadcast(self, conversation_id: str, payload: dict) -> None:
        stale = []
        for websocket in tuple(self._connections[conversation_id]):
            try:
                await websocket.send_json({"topic": "business_state", "payload": payload})
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(conversation_id, websocket)


state_connections = StateConnections()


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_state_socket(websocket: WebSocket, conversation_id: str):
    if not get_conversation(conversation_id):
        await websocket.close(code=4404)
        return
    await state_connections.connect(conversation_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state_connections.disconnect(conversation_id, websocket)
