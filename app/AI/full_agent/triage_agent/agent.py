from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput

triage_agent = AgentBuilder(
    name="triage_agent",
    description="An agent that separates and classifies queries within a full user query",
    input_schema=RootOutput,
    output_schema=TriageAgentOutput,
)
