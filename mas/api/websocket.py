"""WebSocket endpoint for real-time agent run event streaming (LLD Sec 5.2.6)."""

import asyncio
from typing import Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from mas.core.events import event_logger

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket):
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def broadcast_event(self, run_id: str, event_data: dict):
        if run_id in self.active_connections:
            websockets = list(self.active_connections[run_id])
            for ws in websockets:
                try:
                    await ws.send_json(event_data)
                except Exception:
                    self.disconnect(run_id, ws)


manager = ConnectionManager()


def on_event_emitted(event_dict: dict):
    """Callback attached to event_logger."""
    run_id = event_dict.get("run_id")
    if run_id and run_id in manager.active_connections:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(manager.broadcast_event(run_id, event_dict), loop)
        except Exception:
            pass


event_logger.subscribe(on_event_emitted)


@ws_router.websocket("/ws/runs/{run_id}")
async def websocket_run_endpoint(websocket: WebSocket, run_id: str):
    await manager.connect(run_id, websocket)
    try:
        # Initial greeting event
        await websocket.send_json({"type": "connected", "run_id": run_id})
        while True:
            # Keep-alive receive loop
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)
    except Exception:
        manager.disconnect(run_id, websocket)
