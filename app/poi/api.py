import logging

from pymilvus import MilvusClient
from fastapi import APIRouter, Body, FastAPI
from typing import Annotated, Optional
from pymilvus import model
from contextlib import asynccontextmanager
from logging import Logger

from app.poi.models import POI, POIOptional, get_poi_schema, get_index_params
from app.poi.types import OneOrMore
from app.dependencies import NeedsDb, get_db_gen
from app.database.db import create_collection

# Consider moving this somewhere else
embedding_fn = model.DefaultEmbeddingFunction()

@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_db_gen() as db:
        if not db.has_collection("poi"):

            create_collection({
                "collection_name": "poi",
                "index_params": get_index_params(),
            }, get_poi_schema())
    yield

router = APIRouter(lifespan=lifespan)

@router.get("/poi/", tags=["poi"])
def get_poi(
        poi_id: Annotated[OneOrMore[POI], Body()],
        fields: Annotated[list[str], Body()],
        db: NeedsDb
) -> OneOrMore[dict]:
    """

    :param poi_id:
    :param fields:
    :param db:
    :return:
    """
    res = db.get(
        collection_name="poi",
        ids=poi_id,
        output_fields=fields
        # TODO: Change this field when you have more information about schema
    )

    if type(poi_id) is str:
        return res[0]
    else:
        return res

@router.post("/poi/", tags=["poi"])
def insert_poi(
        poi: Annotated[OneOrMore[POI], Body()],
        db: NeedsDb
) -> dict:
    """
    Inserts POI object(s) into poi collection. If vectors are not pre-specified,
    it will convert it to vectors automatically.

    For example output see https://milvus.io/docs/insert-update-delete.md#Insert-Entities-into-a-Collection
    :param poi:
    :param db:
    :return:
    """
    if type(poi) is POI:
        if poi.vector_embedding is None:
            poi.generate_embedding(embedding_fn)
        data = [poi.model_dump()]
    else:
        data = []
        for _poi in poi:
            if _poi.vector_embedding is None:
                _poi.generate_embedding(embedding_fn)
            data.append(_poi)


    res = db.insert(
        collection_name="poi",
        data=data
    )

    return res

@router.put("/poi/", tags=["poi"])
def update_poi(
        poi_id: Annotated[int, Body()],
        # May be moved to the url. Not certain.
        poi: Annotated[POIOptional, Body()],
        db: NeedsDb
):
    if poi.vector_embedding is None:
        poi.generate_embedding(embedding_fn)

    data = {"id": poi_id} | poi.model_dump()
    res = db.upsert(
        collection_name="poi",
        data=data,
        # This should be in the version of milvus we're using, I don't know why it's not.
        # Update: it's in the **kwargs, but I'm pretty sure I'm passing it in right.
        partial_update=True
    )

    return res

@router.delete("/poi/", tags=["poi"])
def delete_poi(
        poi_id: Annotated[Optional[int], Body()],
        poi_filter: Annotated[Optional[str], Body()],
        db: NeedsDb
):
    if poi_id is not None and poi_filter is None:
        res = db.delete(
            collection_name="poi",
            ids=[poi_id]
        )

        return res
    elif poi_id is not None and poi_filter is not None:
        res = db.delete(
            collection_name="poi",
            filter=poi_filter
        )

        return res
    else:
        return {"error": "No value for id or filter found!"}
