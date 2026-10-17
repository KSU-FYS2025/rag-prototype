import logging
import uuid

from google.adk import Runner
from google.adk.agents.llm_agent import Agent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.agent import full_workflow
from app.AI.full_agent.conversation_agent.schema import ConversationOutput

_TOOL_APP_NAME = "RagPrototypeNavigateTool"
_TOOL_USER_ID = "live_tool"

# The workflow runs on its own non-live runner and session service so its
# sub-agent events never land in the live session (and are never replayed).
_workflow_sessions = InMemorySessionService()
_workflow_runner = Runner(
    app_name=_TOOL_APP_NAME,
    node=full_workflow,
    session_service=_workflow_sessions,
)


def _as_workflow_output(
    output: object,
) -> ActionsAgentOutput | ConversationOutput | None:
    if isinstance(output, (ActionsAgentOutput, ConversationOutput)):
        return output
    if isinstance(output, BaseModel):
        output = output.model_dump(mode="json")
    if isinstance(output, dict):
        for schema in (ActionsAgentOutput, ConversationOutput):
            try:
                return schema.model_validate(output)
            except ValidationError:
                continue
    return None


async def navigate(query: str) -> dict:
    """Runs the user's navigation request or building question through the navigation workflow.

    Call this once per user request and wait for the result before calling it again.

    Args:
        query: The user's request, verbatim (e.g. "take me to room 3436").

    Returns:
        The workflow's output, unchanged. Either an ActionsAgentOutput
        ({"user_query", "actions": [...]}) where each action has a "cmd" of
        "navigation", "resolve_nearest", "answer", or "clarify", or a
        ConversationOutput ({"user_query", "response"}).
    """
    result: ActionsAgentOutput | ConversationOutput | None = None
    try:
        session = await _workflow_sessions.create_session(
            app_name=_TOOL_APP_NAME,
            user_id=_TOOL_USER_ID,
            session_id=uuid.uuid4().hex,
        )

        async for event in _workflow_runner.run_async(
            new_message=types.Content(role="user", parts=[types.Part(text=query)]),
            session_id=session.id,
            user_id=_TOOL_USER_ID,
        ):
            if event.output is not None:
                parsed = _as_workflow_output(event.output)
                if parsed is not None:
                    result = parsed
    except Exception:
        logging.exception("navigate tool failed")

    if result is None:
        logging.error(f"navigate tool: workflow produced no output for {query!r}")
        result = ConversationOutput(
            user_query=query,
            response="Something went wrong while looking that up.",
        )

    logging.info(f"navigate tool result: {result}")
    return result.model_dump(mode="json")


root_agent = Agent(
    model="gemini-3.8-live",
    name="root_agent",
    tools=[navigate],
    description="A helpful assistant for navigating the user.",
    instruction="You are a helpful agent that guides users around a building. You have access to the navigate "
    "tool. Pass the user's request into it verbatim. Call it exactly once per user request and wait for its result; "
    "never call it again for the same request. The result is either a list of `actions` or a conversational "
    "`response`. Read out loud: the `response` field of a conversational result or a navigation action, the `text` "
    "field of an answer action, and the `prompt` field of a clarify action (ask the user that question). For a "
    "resolve_nearest action, say you are finding the nearest `target_label`. If `actions` is empty, tell the user "
    "you could not find it. Try to sound more robotic "
    "if at all possible. Note, this does not mean to speak like a robot, just make your voice sound more robotic. The "
    "tool will likely take a while to run, so make sure to keep conversation with the user. Additionally, you are "
    "only able to act on action that you gain from the tool call. You are NEVER to make up information in any "
    "circumstance. If the tool returns that it could not find a route to the location, do NOT make up anything.",
)
