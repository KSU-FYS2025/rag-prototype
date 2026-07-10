from app.AI.full_agent.actions_agent.schema import Command
from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.clarify_agent.schema import ClarifyInput

assert isinstance(Command, type)
clarify_agent = AgentBuilder(
    name="clarify_agent",
    description="An agent whose purpose is to resolve clarification actions.",
    input_schema=ClarifyInput,
    output_schema=Command,
)
