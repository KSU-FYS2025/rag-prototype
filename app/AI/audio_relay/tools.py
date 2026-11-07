import logging
import uuid

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput, ClarifyAction
from app.AI.full_agent.full_nav_workflow.agent import full_nav_workflow
from app.AI.full_agent.clarify_agent.agent import clarify_agent
from app.AI.full_agent.clarify_agent.schema import ClarifyInput, ClarifyOutput
from app.AI.full_agent.conversation_agent.schema import ConversationOutput

USER_ID = "audio_relay"

# Live session id -> the clarify action that session is waiting on. Kept up to
# date by the websocket; resolve_clarification only reads it.
pending_clarifications: dict[str, ClarifyAction] = {}

# Separate from the live runner so the workflows' events never end up in the
# live session's history.
session_service = InMemorySessionService()
navigate_runner = Runner(
    app_name="RagPrototypeNavigateTool",
    node=full_nav_workflow,
    session_service=session_service,
)
clarify_runner = Runner(
    app_name="RagPrototypeClarifyTool",
    node=clarify_agent,
    session_service=session_service,
)


async def run_in_new_session(runner: Runner, text: str) -> list:
    """Runs the runner on `text` in a throwaway session and returns every event it produced."""
    session = await session_service.create_session(
        app_name=runner.app_name, user_id=USER_ID, session_id=uuid.uuid4().hex
    )

    events = []
    async for event in runner.run_async(
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
        session_id=session.id,
        user_id=USER_ID,
    ):
        events.append(event)

    await session_service.delete_session(
        app_name=runner.app_name, user_id=USER_ID, session_id=session.id
    )
    return events


async def resolve_clarification(answer: str, tool_context: ToolContext) -> dict:
    """Resolves the clarification question that was just asked using the user's answer.

    Only call this when the user is answering a question you asked from a `[navigation update]`.

    Args:
        answer: The user's answer, verbatim (e.g. "the men's one").

    Returns:
        {"action": {...}}, the action that replaces the question. The navigation system carries it out and sends what
        to say next as a `[navigation update]`. On failure, {"error": ...}.
    """
    action = pending_clarifications.get(tool_context.session.id)
    if action is None:
        return {"error": "No question is waiting for an answer. Call navigate instead."}

    resolved = None
    try:
        clarify_input = ClarifyInput(user_input=answer, clarification_action=action)
        events = await run_in_new_session(
            clarify_runner, clarify_input.model_dump_json()
        )

        output = None
        for event in events:
            if event.output is not None:
                output = event.output
        if isinstance(output, BaseModel):
            output = output.model_dump(mode="json")

        resolved = ClarifyOutput.model_validate({"action": output}).action
    except Exception:
        logging.exception("resolve_clarification tool failed")

    if resolved is None:
        result = {"error": "Something went wrong while handling that answer."}
    else:
        # clarify_agent can't be trusted to keep the order the same
        resolved.order = action.order
        result = {"action": resolved.model_dump(mode="json")}

    logging.info(f"resolve_clarification tool result: {result}")
    return result


async def navigate(query: str) -> dict:
    """Runs a new navigation request or question about the building through the navigation workflow.

    Use this for anything new the user asks, including when they change their mind instead of answering a
    clarification question.

    Args:
        query: What the user said, verbatim (e.g. "take me to room 3436").

    Returns:
        Either {"response": ...}, a conversational reply to read out loud, or {"actions": [...]}, the actions the
        navigation system will carry out. On failure, {"error": ...}.
    """
    result = None
    try:
        events = await run_in_new_session(navigate_runner, query)

        for event in events:
            output = event.output
            if isinstance(output, BaseModel):
                output = output.model_dump(mode="json")
            if not isinstance(output, dict):
                continue

            # Only parallel_router outputs the combined action list, and only
            # conversation_agent outputs a conversational response. Each
            # actions_agent also outputs a single Command, which is skipped.
            if "actions" in output:
                result = ActionsAgentOutput.model_validate(output).model_dump(
                    mode="json"
                )
            elif event.author == "conversation_agent":
                result = ConversationOutput.model_validate(output).model_dump(
                    mode="json"
                )
    except Exception:
        logging.exception("navigate tool failed")

    if result is None:
        logging.error(f"navigate tool: workflow produced no output for {query!r}")
        result = {"error": "Something went wrong while looking that up."}

    logging.info(f"navigate tool result: {result}")
    return result
