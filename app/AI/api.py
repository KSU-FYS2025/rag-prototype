import os
from typing import Annotated

import ollama
from fastapi import APIRouter
from fastapi.params import Body
from starlette.responses import StreamingResponse

from app.database.db import search_poi
from app.dependencies import NeedsDb, NeedsOllama
from app.AI.extras import instruction_prompt, triage_agent_prompt

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

@router.get("/ai/triage_agent", tags=["poi", "ai", "triage_agent"], dependencies=[NeedsOllama])
def triage_agent(
        user_query: str,
        user_position: Annotated[(float, int, int), Body()]
):
    model = os.environ.get("AI_MODEL")

    res = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": triage_agent_prompt()},
            {"role": "user", "content": user_query}
        ]
    )

    return res
