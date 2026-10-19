import json
import logging
import time

from fastapi import APIRouter
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel
from google.adk import Workflow, Runner, Agent

from app.AI.full_agent.root_agent.agent import root_agent
from app.dependencies import NeedsOllama
from app.AI.full_agent.agent import full_workflow
from app.AI.full_agent.triage_agent.agent import triage_agent as triage_agent_adk

router = APIRouter()


def check_author(event_author: str, target_author: list[str] | str):
    if isinstance(target_author, str):
        return event_author == target_author
    else:
        return event_author in target_author


async def run_adk_workflow(
    user_query: str | BaseModel,
    workflow: Workflow | Agent,
    target_author: list[str] | str | None = None,
) -> dict | str | None:
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=f"RagPrototypeADK{workflow.name}",
        node=workflow,
        session_service=session_service,
    )

    await session_service.create_session(
        app_name=f"RagPrototypeADK{workflow.name}",
        user_id="example_user",
        session_id="example_session",
    )

    user_content: types.Content

    if isinstance(user_query, str):
        user_content = types.Content(role="user", parts=[types.Part(text=user_query)])
    else:
        user_content = types.Content(
            role="user", parts=[types.Part(text=json.dumps(user_query.model_dump()))]
        )

    response = runner.run_async(
        user_id="example_user", session_id="example_session", new_message=user_content
    )

    author_filter = target_author or workflow.name

    output = {}
    try:
        async for event in response:
            logging.info(
                f"Event author: {event.author} | is_final: {event.is_final_response()} | output: {event.output} | content: {event.content}"
            )
            if event.is_final_response() and check_author(event.author, author_filter):
                logging.info(f"Matched root event: {event}")
                if event.output is not None:
                    output = event.output
                elif event.content is not None and event.content.parts is not None:
                    text = event.content.parts[0].text
                    if text is not None:
                        try:
                            output = json.loads(text)
                        except json.JSONDecodeError:
                            output = text
    finally:
        await response.aclose()

    logging.info(f"Final output: {output}")
    return output


@router.get("/ai/graph-workflow/full", dependencies=[NeedsOllama])
async def graph_workflow_full(user_query: str):
    return await run_adk_workflow(
        user_query, full_workflow, ["synthesis_agent", "actions_agent"]
    )


@router.post("/ai/graph-workflow/full_batch", dependencies=[NeedsOllama])
async def graph_workflow_full_batch(user_query: list[str]):
    backoff_factor = 2
    collect = []
    for query in user_query:
        for i in range(5):  # Max retry 5 times
            try:
                res = await run_adk_workflow(
                    query, full_workflow, ["synthesis_agent", "actions_agent"]
                )
                collect.append({"query": query, "result": res})
                break
            except ServerError:
                logging.info(
                    f"server error, likely caused by high demand. Retrying in {(backoff_factor**i) / 100} seconds..."
                )
                time.sleep((backoff_factor**i) / 100)

    return collect


@router.get("/ai/graph-workflow/root", dependencies=[NeedsOllama])
async def graph_workflow_root(user_query: str):
    return await run_adk_workflow(user_query, root_agent)


@router.get("/ai/graph-workflow/triage", dependencies=[NeedsOllama])
async def graph_workflow_triage(user_query: str):
    return await run_adk_workflow(user_query, triage_agent_adk)
