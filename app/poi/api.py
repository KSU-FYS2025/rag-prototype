from pymilvus import MilvusClient
from fastapi import APIRouter, Depends, Body, FastAPI
from typing import Annotated, Optional
from pymilvus import model
from contextlib import asynccontextmanager

from app.poi.models import POI, POIOptional, poiSchema, index_params
from app.poi.types import OneOrMore
from app.dependencies import NeedsDb, get_db_gen
from app.database.db import create_schema, create_collection

# Consider moving this somewhere else
embedding_fn = model.DefaultEmbeddingFunction()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db_gen()
    if not db.has_collection("poi"):
        create_collection({
            "collection_name": "poi",
            "schema": poiSchema,
            "index_params": index_params,
        })
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
        _id: Annotated[int, Body()],
        # May be moved to the url. Not certain.
        poi: Annotated[POIOptional, Body()],
        db: NeedsDb
):
    if poi.vector_embedding is None:
        poi.generate_embedding(embedding_fn)

    data = {"id": _id} | poi.model_dump()
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
        _id: Annotated[Optional[int], Body()],
        _filter: Annotated[Optional[str], Body()],
        db: NeedsDb
):
    if _id is not None and _filter is None:
        res = db.delete(
            collection_name="poi",
            ids=[_id]
        )

        return res
    elif _id is not None and _filter is not None:
        res = db.delete(
            collection_name="poi",
            filter=_filter
        )

        return res
    else:
        return {"error": "No value for id or filter found!"}
