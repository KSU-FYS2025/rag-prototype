import os

import ollama
from fastapi import APIRouter, Body, FastAPI, HTTPException
from typing import Annotated, Optional
from contextlib import asynccontextmanager

from starlette.responses import StreamingResponse

from app.poi.models import POI, POIOptional, get_poi_schema, get_index_params, dump_and_trim_none
from app.poi.types import OneOrMore
from app.dependencies import NeedsDb, get_db_gen, NeedsOllama
from app.database.db import create_collection, embedding_fn, search_poi


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
        poi_id: int,
        # fields: Optional[str],
        db: NeedsDb
) -> OneOrMore[dict]:
    """

    :param poi_id:
    :param fields:
    :param db:
    :return:
    """
    with db as db:
        res = db.get(
            collection_name="poi",
            ids=poi_id,
            # output_fields=fields
            # TODO: Change this field when you have more information about schema
        )

    if type(poi_id) is str:
        return res[0]
    else:
        return res

@router.get("/poi/all", tags=["poi"])
def get_all_poi(
        db: NeedsDb
) -> str:
    """

    :param db:
    :return:
    """
    with db as db:
        res = db.query(
            collection_name="poi",
            filter="id >= 0",
            # output_fields=fields
            # TODO: Change this field when you have more information about schema
        )
    return str(res)

@router.post("/poi/", tags=["poi"])
def insert_poi(
        poi: Annotated[OneOrMore[POI], Body()],
        db: NeedsDb
) -> str:
    """
    Inserts POI object(s) into poi collection. If vectors are not pre-specified,
    it will convert it to vectors automatically.

    For example output see https://milvus.io/docs/insert-update-delete.md#Insert-Entities-into-a-Collection
    :param poi:
    :param db:
    :return:
    """
    if len(poi.pos) != 3:
        raise HTTPException(status_code=400, detail="Pos info in body needs to be a 3 dimensional array of floating point values!!!")

    if type(poi) is POI:
        if not hasattr(poi, "vector") or poi.vector is None or poi.vector == []:
            poi.generate_embedding(embedding_fn)
        # idk how I feel about this, but it's needed
        delattr(poi, "id")
        data = [poi.model_dump()]
    else:
        data = []
        for _poi in poi:
            if _poi.vector is None:
                _poi.generate_embedding(embedding_fn)
            delattr(poi, "id")
            data.append(_poi.model_dump(mode="json"))

    with db as db:
        res = db.insert(
            collection_name="poi",
            data=data
        )

    return str(res)

@router.put("/poi/", tags=["poi"])
def update_poi(
        poi_id: Annotated[int, Body()],
        # May be moved to the url. Not certain.
        poi: Annotated[POIOptional, Body()],
        db: NeedsDb
):
    with db as db:
        prev_poi = db.get(
            collection_name="poi",
            ids=poi_id
        )
        print(f"{prev_poi=}\n")

        poi_dump = dump_and_trim_none(poi)
        print(f"{poi_dump=}\n")
        prev_poi = prev_poi[0].copy()
        print(f"{prev_poi=}\n")

        prev_poi.update(poi_dump)
        print(f"{prev_poi=}\n")
        new_poi = POI(**prev_poi)


        if not hasattr(new_poi, "vector") or new_poi.vector is None or new_poi.vector == []:
            new_poi.generate_embedding(embedding_fn)
        print("embedding generated!!!\n\n\n")

        res = db.upsert(
            collection_name="poi",
            data=new_poi.model_dump()
        )

    return res

@router.delete("/poi/", tags=["poi"])
def delete_poi(
        poi_id: Annotated[Optional[int], Body()],
        poi_filter: Annotated[Optional[str], Body()],
        db: NeedsDb
):
    with db as db:
        if poi_id and not poi_filter:
            res = db.delete(
                collection_name="poi",
                ids=[poi_id]
            )

            return res

        elif (not poi_id) and poi_filter:
            res = db.delete(
                collection_name="poi",
                filter=poi_filter
            )

            return res

        else:
            return {"error": "No value for id or filter found!"}

@router.get("/poi/search", tags=["poi", "vector search"], dependencies=[NeedsOllama])
async def user_query_step_1(
        poi_query: str,
        db: NeedsDb
) -> StreamingResponse:
    retrieved_knowledge = search_poi(poi_query, 5, ["label", "tags", "pos", "description"])

    instruction_prompt=f"""You are a helpful chatbot whose role is to assist people in guiding them to the correct spot
You are to not make up any information about the building or assume anything.
Using only the prompt and the information given below, answer the user's query as best you can.
Good luck snake, try to make it out alive. I don't want the paperwork.
{"\n".join([f" - {chunk}" for chunk, similarity in retrieved_knowledge])}
"""
    model = os.environ.get("LANGUAGE_MODEL")

    stream = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": instruction_prompt},
            {"role": "user", "content": poi_query}
        ],
        stream=True
    )

    async def response():
        for chunk in stream:
            yield chunk["message"]["content"]

    return StreamingResponse(response())


