from starlette.routing import BaseRoute
import logging
import warnings
from typing import Any


from fastapi import APIRouter, WebSocket
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import WebSocketRoute

from app.database.db import get_db_gen
from app.poi.models import POI, get_poi_schema, get_index_params
from app.database.db import embedding_fn, ensure_collection


warnings.warn(
    "This module currently uses the old scheme, and will be updated in a future version",
    DeprecationWarning,
    stacklevel=2,
)

# class Triage(WebSocketEndpoint):
#     encoding = "json"
#
#     async def on_connect(self, websocket: WebSocket) -> None:
#         await websocket.accept()
#         self.history = []  # Store last few turns
#         logging.info("Connected to Unity Project!")
#
#     async def on_receive(self, websocket: WebSocket, data: Any) -> None:
#         await websocket.send_json({"message": "waiting on server..."})
#         logging.info("Processing request from Unity...")
#         # data is a dict because encoding="json"
#         query = data.get("query", "")
#         context = data.get("context", None)
#
#         if not query and isinstance(data, str):
#             query = data
#
#         if data.get("type") == "verification":
#             from app.AI.api import verify_route_agent
#
#             res = verify_route_agent(query, data, context=context, history=self.history)
#         else:
#             res = triage_agent(query, context=context, history=self.history)
#
#         # Update history (keep last 5 exchanges)
#         self.history.append({"user": query, "ai": res.get("response", "")})
#         if len(self.history) > 5:
#             self.history.pop(0)
#
#         await websocket.send_json(res)


# routes: list[BaseRoute] = [
#     WebSocketRoute("/ws/AI", Triage),
# ]

router = APIRouter(routes=None)
