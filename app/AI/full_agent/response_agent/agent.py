from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.response_agent.schema import ResponseAgentOutput
from app.AI.full_agent.search_agent.schema import SearchOutput

response_agent = Agent(
    model='gemini-2.5-flash',
    name='response_agent',
    description='Agent that generates the final response',
    instruction='''You are the last agent in a chain meant to provide navigational assistance. Your role is to take a
    list of POIs returned by the last agent and use it to synthesize a list of actions for the Unity client to take. For
    each object inside the validations tag, you must assign one action to it.''',
    input_schema=SearchOutput,
    output_schema=ResponseAgentOutput,
)
