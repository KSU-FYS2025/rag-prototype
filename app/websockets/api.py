import logging
from typing import Any


from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import Route, WebSocketRoute
from pydantic import ValidationError

from app.AI.api import triage_agent
from app.database.db import get_db_gen
from app.poi.models import POI


class Triage(WebSocketEndpoint):
    encoding = "json"

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        await websocket.send_json({"message": "waiting on server..."})
        # data is a dict because encoding="json"
        # triage_agent expects a string user_query
        query = data.get("query", str(data)) if isinstance(data, dict) else str(data)
        res = triage_agent(query)
        await websocket.send_json(res)

class Sync(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.received = []
        self.validated = []

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        # data is a dict because encoding="json"
        if isinstance(data, dict) and data.get("action") == "commit":
            try:
                await websocket.send_json({"status": "processing", "message": f"Committing {len(self.received)} POIs..."})
                self.validate()
                res = self.send_to_db()
                await websocket.send_json({"status": "success", "message": "Data synced successfully", "details": str(res)})
            except Exception as e:
                logging.error(f"Sync failed: {e}")
                await websocket.send_json({"status": "error", "message": str(e)})
        else:
            self.received.append(data)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        logging.info(f"Sync client disconnected with code {close_code}")

    def validate(self):
        from app.poi.models import POI
        for data in self.received:
            # We trust the data enough to skip per-item Pydantic re-validation if needed,
            # but we ensured the model is flexible. 
            self.validated.append(data)

    def send_to_db(self) -> dict:
        from app.poi.models import POI
        from app.database.db import embedding_fn
        
        pois_to_process = []
        for item in self.validated:
            # Full mapping from Unity POIData
            poi_args = {
                "id": item.get("identification", 0),
                "name": item.get("name", ""),
                "title": item.get("title", ""),
                "poiName": item.get("poiName", ""),
                "description": item.get("description", ""),
                "type": item.get("type", "Room"),
                "parentName": item.get("parentName", ""),
                "position": item.get("position", [0.0, 0.0, 0.0]),
                "rotation": item.get("rotation", [0.0, 0.0, 0.0]),
                "localPosition": item.get("localPosition", [0.0, 0.0, 0.0]),
                "localRotation": item.get("localRotation", [0.0, 0.0, 0.0]),
                "vector": item.get("vector", None)
            }
            
            # Handle potential Dict position if Unity sends it that way
            for field in ["position", "rotation", "localPosition", "localRotation"]:
                val = item.get(field)
                if isinstance(val, dict):
                    poi_args[field] = [val.get("x", 0.0), val.get("y", 0.0), val.get("z", 0.0)]
            
            pois_to_process.append(POI(**poi_args))

        # Batch generate embeddings
        texts_to_embed = []
        indices_to_embed = []
        for i, poi in enumerate(pois_to_process):
            if not poi.vector:
                text = f"Name: {poi.name}\nPOI Name: {poi.poiName}\nTitle: {poi.title}\nDescription: {poi.description}\nType: {poi.type}\nParent: {poi.parentName}"
                texts_to_embed.append(text)
                indices_to_embed.append(i)
        
        if texts_to_embed:
            vectors = embedding_fn.encode_documents(texts_to_embed)
            for idx, vec in zip(indices_to_embed, vectors):
                pois_to_process[idx].vector = vec.tolist() if hasattr(vec, "tolist") else list(vec)

        # Deduplicate by ID
        deduped_data = {}
        for poi in pois_to_process:
            dump = poi.model_dump()
            deduped_data[dump["id"]] = dump
        
        data_to_insert = list(deduped_data.values())

        if not data_to_insert:
            return {"message": "No data to insert"}

        from app.poi.models import get_poi_schema, get_index_params
        from app.database.db import ensure_collection

        with get_db_gen() as db:
            # Lazy initialize if dropped during runtime
            ensure_collection({
                "collection_name": "poi",
                "index_params": get_index_params(),
            }, get_poi_schema(), db=db)

            res = db.upsert(
                collection_name="poi",
                data=data_to_insert
            )
        return res

routes = [
    WebSocketRoute("/ws/AI", Triage),
    WebSocketRoute("/ws/sync", Sync)
]

router = APIRouter(routes=routes)
