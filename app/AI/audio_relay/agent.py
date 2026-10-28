import logging

from google.adk import Runner
from google.adk.agents.llm_agent import Agent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types

from app.AI.mock_frontend.agent import mock_frontend_workflow

_TOOL_APP_NAME = "RagPrototypeNavigateTool"

# Nodes of mock_frontend_workflow whose content is meant to be spoken to the user.
# Other nodes (e.g. parallel_router) also emit content, but only for adk eval.
_SPOKEN_NODES = {"resolve_actions", "resolve_conversation"}

# The workflow runs on its own non-live runner and session service so its
# sub-agent events never land in the live session (and are never replayed).
# Each live session gets a matching workflow session, so a clarify question
# asked on one call is resumed by the user's answer on the next call.
_workflow_sessions = InMemorySessionService()
_workflow_runner = Runner(
    app_name=_TOOL_APP_NAME,
    node=mock_frontend_workflow,
    session_service=_workflow_sessions,
)


def _node_name(event: Event) -> str:
    # node_info.path looks like "mock_frontend/resolve_actions@1".
    return event.node_info.path.rsplit("/", 1)[-1].split("@", 1)[0]


async def navigate(query: str, tool_context: ToolContext) -> dict:
    """Runs the user's navigation request, building question, or clarification answer through the navigation workflow.

    Call this once per user utterance and wait for the result before calling it again.

    Args:
        query: What the user said, verbatim (e.g. "take me to room 3436", or "the men's one" when answering a
            clarification question).

    Returns:
        {"say": [...], "awaiting_reply": bool}. "say" is the text to read out loud, in order. If "awaiting_reply"
        is true, the last item in "say" is a question; pass the user's answer to this tool verbatim.
    """
    user_id = tool_context.user_id
    session_id = tool_context.session.id
    spoken: list[str] = []
    try:
        session = await _workflow_sessions.get_session(
            app_name=_TOOL_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            session = await _workflow_sessions.create_session(
                app_name=_TOOL_APP_NAME, user_id=user_id, session_id=session_id
            )

        async for event in _workflow_runner.run_async(
            new_message=types.Content(role="user", parts=[types.Part(text=query)]),
            session_id=session.id,
            user_id=user_id,
        ):
            if (
                _node_name(event) in _SPOKEN_NODES
                and event.content is not None
                and event.content.parts
            ):
                spoken.extend(p.text for p in event.content.parts if p.text)
    except Exception:
        logging.exception("navigate tool failed")

    session = await _workflow_sessions.get_session(
        app_name=_TOOL_APP_NAME, user_id=user_id, session_id=session_id
    )
    awaiting_reply = bool(
        session is not None and session.state.get("user:resume_resolution")
    )

    if not spoken:
        logging.error(f"navigate tool: workflow produced no speech for {query!r}")
        spoken = ["Something went wrong while looking that up."]

    result = {"say": spoken, "awaiting_reply": awaiting_reply}
    logging.info(f"navigate tool result: {result}")
    return result


root_agent = Agent(
    model="gemini-3.8-live",
    name="root_agent",
    tools=[navigate],
    description="A helpful assistant for navigating the user.",
    instruction="You are a helpful agent that guides users around a building. You have access to the navigate "
    "tool. Pass what the user said into it verbatim. Call it exactly once per thing the user says and wait for its "
    "result; never call it again until the user says something new. Read every item in the result's `say` list "
    "out loud, in order. If `awaiting_reply` is true, the last item is a question for the user: ask it, wait for "
    "their answer, then pass their answer to the navigate tool verbatim. Try to sound more robotic "
    "if at all possible. Note, this does not mean to speak like a robot, just make your voice sound more robotic. The "
    "tool will likely take a while to run, so make sure to keep conversation with the user. Additionally, you are "
    "only able to act on action that you gain from the tool call. You are NEVER to make up information in any "
    "circumstance. If the tool returns that it could not find a route to the location, do NOT make up anything.",
)
