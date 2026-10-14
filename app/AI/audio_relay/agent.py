from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search, AgentTool

from app.AI.full_agent.agent import full_workflow

root_agent = Agent(
    model="gemini-2.5-flash-native-audio-latest",
    name="root_agent",
    tools=[full_workflow],
    description="A helpful assistant for navigating the user.",
    instruction="You are a helpful agent that guides users around a building. You have access to the full_workflow "
    "tool, which you can use to pass the users query into, and returns a list of actions for the frontend "
    "to take. For testing purposes, when you receive this, just read it out loud. Try to sound more robotic "
    "if at all possible. The workflow will likely take a while to run, so make sure to keep conversation "
    "with the user.",
)
