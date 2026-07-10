from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.conversation_agent.schema import ConversationOutput
from app.AI.full_agent.root_agent.schema import RootOutput

conversation_agent = AgentBuilder(
    name="conversation_agent",
    description="An agent that handles conversational interactions with the user.",
    input_schema=RootOutput,
    output_schema=ConversationOutput,
)
