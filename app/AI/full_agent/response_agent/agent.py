from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.response_agent.schema import FinalResponse
from app.AI.full_agent.search_agent.schema import SearchOutput

response_agent = Agent(
    model='gemini-2.5-flash',
    name='response_agent',
    description='Agent that generates the final response',
    instruction='Answer user questions to the best of your knowledge',
    input_schema=SearchOutput,
    output_schema=FinalResponse,
)
