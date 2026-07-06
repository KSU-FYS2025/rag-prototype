from google.adk.agents.llm_agent import Agent
from google.adk.tools import load_memory

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.defaults import planner_defaults
from app.AI.full_agent.search_agent.schema import SearchOutput

actions_agent = Agent(
    model="gemini-2.5-flash",
    name="actions_agent",
    description="Agent that generates the final response",
    instruction="""You are the last agent in a chain meant to provide navigational assistance. Your role is to take a
    list of POIs returned by the last agent and use it to synthesize a list of actions for the Unity client to take. For
    each object inside the validations tag, you must assign one action to it. Be sure to always take user preferences 
    into account if it is necessary. In cases where you need user preferences, you may use the load_memory tool to find
    any preferences need from previous conversations.""",
    planner=planner_defaults,
    input_schema=SearchOutput,
    output_schema=ActionsAgentOutput,
    # tools=[load_memory],
)
