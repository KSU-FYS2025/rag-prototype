from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.root_agent.schema import RootOutput

root_agent = AgentBuilder(
    name="root_agent",
    description="Agent that serves as an entry point to the user",
    output_schema=RootOutput,
)
