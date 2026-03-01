import logging
from typing import Any


from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import Route, WebSocketRoute
from pydantic import ValidationError

from app.AI.api import triage_agent
from app.database.db import get_db_gen
from app.poi.models import POI

# TODO: Make sure to handle location data as well.
class Triage(WebSocketEndpoint):
    encoding = "json"

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        await websocket.send_json({"message": "waiting on server..."})
        res = triage_agent(data)
        await websocket.send_json(res)

class Sync(WebSocketEndpoint):
    encoding = "json"
    received: list[dict] = []
    validated: list[dict] = []

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        if isinstance(data, list):
            for element in data:
                self.received.append(element)
        elif isinstance(data, dict):
            self.received.append(data)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        match close_code:
            case 1000:
                try:
                    self.validate()
                    res = self.send_to_db()
                    await websocket.close(1000, f"data transferred successfully\nDetailed:\n{res}")
                except Exception as e:
                    await websocket.close(1011, f"error in transferring data!\nDetailed:\n{e}")
            case _:
                await websocket.close(1006, "unexpected client closure during data transfer")

    def validate(self):
        for data in self.received:
            try:
                POI(**data)
                self.validated.append(data)
            except ValidationError as e:
                if "name" in data:
                    logging.warning(f"POI with name {data["name"]} failed to validate!\nDetailed:\n{e}")
                else:
                    logging.warning(f"POI with unknown name failed to validate!\nDetailed:\n{e}")

    def send_to_db(self) -> dict:
        with get_db_gen() as db:
            res = db.upsert(
                collection_name="POI",
                data=self.validated
            )
        return res

routes = [
    WebSocketRoute("/ws/AI", Triage),
    WebSocketRoute("/ws/sync", Sync)
]

router = APIRouter(routes=routes)
