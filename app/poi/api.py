from pymilvus import MilvusClient
from fastapi import APIRouter, Depends, Body
from typing import Annotated

from app.poi.models import POI
from app.poi.types import OneOrMore
from app.dependencies import get_db


router = APIRouter()

@router.get("/poi/", tags=["poi"])
def get_poi(
        poi_id: Annotated[OneOrMore[POI], Body()],
        fields: Annotated[list[str], Body()],
        db: MilvusClient = Depends(get_db)
) -> OneOrMore[dict]:
    if type(poi_id) is str:
        ids = [poi_id]
    else:
        ids = poi_id

    res = db.get(
        collection_name="poi",
        ids=ids,
        output_fields=fields
        # TODO: Change this field when you have more information about schema
    )

    if type(poi_id) is str:
        return res[0]
    else:
        return res
