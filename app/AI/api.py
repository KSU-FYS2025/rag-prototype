import os
import ollama
from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.database.db import search_poi
from app.dependencies import NeedsDb, NeedsOllama
from app.AI.extras import instruction_prompt

router = APIRouter()

@router.get("/ai/search", tags=["poi", "vector search"], dependencies=[NeedsOllama])
async def user_query_step_1(
        poi_query: str
) -> StreamingResponse:
    retrieved_knowledge = search_poi(poi_query, 5, ["label", "tags", "pos", "description"])


    model = os.environ.get("AI_MODEL")

    stream = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": instruction_prompt(retrieved_knowledge)},
            {"role": "user", "content": poi_query}
        ],
        stream=True
    )

    async def response():
        for chunk in stream:
            yield chunk["message"]["content"]

    return StreamingResponse(response())
