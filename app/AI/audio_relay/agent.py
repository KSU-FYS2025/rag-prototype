from google.adk.agents.llm_agent import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from app.AI.audio_relay.tools import navigate, resolve_clarification


def get_from_file(context: ReadonlyContext) -> str:
    instruction = ""
    with open("app/AI/audio_relay/instruction.md", "r") as file:
        instruction = "\n".join(file.readlines())
    return instruction


root_agent = Agent(
    model="gemini-3.8-live",
    name="root_agent",
    tools=[navigate, resolve_clarification],
    description="A helpful assistant for navigating the user.",
    instruction=get_from_file,
)
