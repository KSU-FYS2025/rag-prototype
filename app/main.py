from fastapi import FastAPI
import json
import os
from dotenv import load_dotenv

from app.poi import api as poiapi
from app.AI import api as aiapi
from app.websockets import api as wsapi
from app.mcp import api as mcp

import logging
from contextlib import asynccontextmanager
from app.poi.models import get_poi_schema, get_index_params, POI
from app.database.db import create_collection, get_db_gen, embedding_fn

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database collections before app starts
    print("Lifespan starting: initializing models and database...")
    # Track startup success - app can start even if embedding fails
    embedding_init_failed = False

    # CRITICAL: Initialize embedding model FIRST and cache it for entire app lifetime
    # This prevents repeated downloads/initialization on every request
    logging.info("Pre-loading embedding model (this may take a moment on first run)...")
    embedding_fn.initialize(max_retries=3)
    if embedding_fn._embedding_fn is None:
        logging.warning(
            "Failed to initialize embedding model. Vector search will not be available. "
            "This may be due to network issues or HuggingFace rate limiting."
        )
        embedding_init_failed = True

    try:
        poi_json_path = os.environ.get("POI_JSON_PATH")
        if not poi_json_path:
            raise RuntimeError(
                "POI_JSON_PATH environment variable not set. "
                "Please set it to point to your POI JSON file."
            )

        if not os.path.exists(poi_json_path):
            raise FileNotFoundError(
                f"POI JSON file not found at: {poi_json_path}"
            )

        logging.info(f"Loading POI data from: {poi_json_path}")
        json_data = None
        with open(poi_json_path, "r") as db_file:
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
                try:
                    embedding = POI.generate_embedding_json(poi)
                    poi["vector"] = embedding[0]
                except Exception as e:
                    # If embedding fails due to network issues, log and continue
                    # The app can still start, but vector search may not be available
                    logging.warning(
                        f"Failed to generate embedding for POI {poi.get('id', 'unknown')}: {e}. "
                        f"This may be due to network issues. Vector search may be unavailable."
                    )
                    embedding_init_failed = True
                    # Create a dummy embedding if network fails
                    poi["vector"] = [0.0] * 768

        logging.info(f"Loaded {len(json_data['pois'])} POIs from file")

        with get_db_gen() as db:
            if not db.has_collection("poi"):
                logging.info("Collection 'poi' not found. Creating...")
                create_collection({
                    "collection_name": "poi",
                    "index_params": get_index_params(),
                }, db, get_poi_schema())
                logging.info("Collection 'poi' created successfully.")
                logging.info("Inserting POIs from file...")
                db.insert(
                    collection_name="poi",
                    data=json_data["pois"],
                )
                logging.info(f"Successfully inserted {len(json_data['pois'])} POIs")
            else:
                logging.info("Collection 'poi' already exists.")
                logging.info("Updating POIs from file...")
                db.upsert(
                    collection_name="poi",
                    data=json_data["pois"],
                )
                logging.info(f"Successfully upserted {len(json_data['pois'])} POIs")

        if embedding_init_failed:
            logging.warning(
                "Embedding initialization failed during startup. "
                "The app is running but vector search may not work as expected. "
                "Please check your network connection and restart the app."
            )
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}", exc_info=True)
        print(f"ERROR: Database initialization failed: {e}")
        raise
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(poiapi.router)
app.include_router(aiapi.router)
app.include_router(wsapi.router)
app.include_router(mcp.router)

@app.get("/ping")
async def pong():
    return {"message": "pong!"}
