from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import Route

from app.AI.api import triage_agent

class Triage(WebSocketEndpoint):
    encoding = "json"

    async def on_receive(self, websocket: WebSocket, data: str) -> None:
        await websocket.send_json({"message": "waiting on server..."})
        res = triage_agent(data)
        await websocket.send_json(res)

routes = [
    Route("/ws/AI", Triage)
]

router = APIRouter(routes=routes)
