from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

root_agent = Agent(
    model=LlmAgent.DEFAULT_LIVE_MODEL,
    name="root_agent",
    tools=[google_search],
    description="A helpful assistant for user questions.",
    instruction="You are a helpful assistant that can search the web.",
)
