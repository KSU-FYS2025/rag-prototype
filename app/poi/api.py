from pymilvus import MilvusClient
from fastapi import APIRouter, Depends, Body
from typing import Annotated
from pymilvus import model

from app.poi.models import POI
from app.poi.types import OneOrMore
from app.dependencies import DbDep

# Consider moving this somewhere else
embedding_fn = model.DefaultEmbeddingFunction()

router = APIRouter()

@router.get("/poi/", tags=["poi"])
def get_poi(
        poi_id: Annotated[OneOrMore[POI], Body()],
        fields: Annotated[list[str], Body()],
        db: DbDep
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
        db: DbDep
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
