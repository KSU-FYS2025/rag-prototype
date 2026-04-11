import numpy
from fastapi import FastAPI
import json
import os

from app.poi import api as poiapi
from app.AI import api as aiapi
from app.websockets import api as wsapi

import logging
from contextlib import asynccontextmanager
from app.poi.models import get_poi_schema, get_index_params, POI
from app.database.db import create_collection, get_db_gen

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database collections before app starts
    logging.info("Lifespan starting: initializing database...")
    try:
        json_data = None
        with open(os.environ.get("POI_JSON_PATH"), "r") as db_file:
            json_data = json.load(db_file)
            id_counter = 0
            for poi in json_data["pois"]:
                # Transform into database format (turns position objects into arrays)
                poi["position"] = [
                    poi["position"]["x"],
                    poi["position"]["y"],
                    poi["position"]["z"]
                ]
                poi["rotation"] = [
                    poi["rotation"]["x"],
                    poi["rotation"]["y"],
                    poi["rotation"]["z"]
                ]
                poi["localPosition"] = [
                    poi["localPosition"]["x"],
                    poi["localPosition"]["y"],
                    poi["localPosition"]["z"]
                ]
                poi["localRotation"] = [
                    poi["localRotation"]["x"],
                    poi["localRotation"]["y"],
                    poi["localRotation"]["z"]
                ]
                poi["id"] = poi["identification"]
                id_counter += 1
                embedding = POI.generate_embedding_json(poi)
                poi["vector"] = embedding[0]
                # embedding = embedding.astype(numpy.float32)
                # poi["vector"] = embedding.tolist()
        with get_db_gen() as db:
            if not db.has_collection("poi"):
                logging.info("Collection 'poi' not found. Creating...")
                create_collection({
                    "collection_name": "poi",
                    "index_params": get_index_params(),
                }, db, get_poi_schema())
                logging.info("Collection 'poi' created successfully.")
                logging.info("Creating POIs form file...")
                db.insert(
                    collection_name="poi",
                    data=json_data["pois"],
                )
            else:
                logging.info("Collection 'poi' already exists.")
                logging.info("Updating POIs from file...")
                db.upsert(
                    collection_name="poi",
                    data=json_data["pois"],
                )
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(poiapi.router)
app.include_router(aiapi.router)
app.include_router(wsapi.router)

@app.get("/ping")
async def pong():
    return {"message": "pong!"}
