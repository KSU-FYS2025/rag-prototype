from app.AI.full_agent.actions_agent.schema import Command
from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.search_agent.schema import Validation

actions_agent = AgentBuilder(
    name="actions_agent",
    description="Agent that generates the final response",
    input_schema=Validation,
    output_schema=Command,
    # tools=[load_memory],
)
