from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.defaults import planner_defaults
from app.AI.full_agent.conversation_agent.schema import ConversationOutput
from app.AI.full_agent.root_agent.schema import RootOutput

conversation_agent = Agent(
    model="gemini-2.5-flash",
    name="conversation_agent",
    description="A helpful assistant for user questions.",
    instruction="Based on the user's query, converse with them. You have free rein, just stay within the user's "
    "conversation, and do not bring up any topics that may be offensive.",
    planner=planner_defaults,
    input_schema=RootOutput,
    output_schema=ConversationOutput,
)
