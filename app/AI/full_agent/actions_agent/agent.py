from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.search_agent.schema import SearchOutput

actions_agent = AgentBuilder(
    name="actions_agent",
    description="Agent that generates the final response",
    input_schema=SearchOutput,
    output_schema=ActionsAgentOutput,
    # tools=[load_memory],
)
