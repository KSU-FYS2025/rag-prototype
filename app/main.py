from fastapi import FastAPI

from app.poi import api as poiapi
from app.AI import api as aiapi
from app.websockets import api as wsapi

import logging
from contextlib import asynccontextmanager
from app.poi.models import get_poi_schema, get_index_params
from app.database.db import create_collection, get_db_gen

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database collections before app starts
    logging.info("Lifespan starting: initializing database...")
    try:
        with get_db_gen() as db:
            if not db.has_collection("poi"):
                logging.info("Collection 'poi' not found. Creating...")
                create_collection({
                    "collection_name": "poi",
                    "index_params": get_index_params(),
                }, get_poi_schema())
                logging.info("Collection 'poi' created successfully.")
            else:
                logging.info("Collection 'poi' already exists.")
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
