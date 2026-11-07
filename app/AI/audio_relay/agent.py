from google.adk.agents.llm_agent import Agent

from app.AI.audio_relay.tools import navigate, resolve_clarification
from app.AI.instruction_providers import get_from_file_path

root_agent = Agent(
    model="gemini-3.8-live",
    name="root_agent",
    tools=[navigate, resolve_clarification],
    description="A helpful assistant for navigating the user.",
    instruction=get_from_file_path("app/AI/audio_relay/instruction.md"),
)
