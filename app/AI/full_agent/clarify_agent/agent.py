from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.actions_agent.schema import Command
from app.AI.full_agent.defaults import planner_defaults
from app.AI.full_agent.clarify_agent.schema import ClarifyInput

clarify_agent = Agent(
    model="gemini-3.5-flash",
    name="clarify_agent",
    description="An agent whose purpose is to resolve clarification actions.",
    instruction="You are an AI agent whose purpose is to resolve clarification actions. Use the user_input and the "
    "clarification action provided to you to accomplish this task. You must output this as one of the "
    "actions in the Command schema. You can only output a clarification action if and only if the user_input "
    "still does not resolve the clarification action.",
    planner=planner_defaults,
    input_schema=ClarifyInput,
    output_schema=Command,
)
