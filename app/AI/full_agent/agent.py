from app.AI.full_agent.root_agent.agent import root_agent
from app.AI.full_agent.triage_agent.agent import triage_agent
from app.AI.full_agent.search_agent.agent import search_workflow

from google.adk import Workflow

full_workflow = Workflow(
    name="full_workflow",
    edges=[
        ("START", root_agent, triage_agent, search_workflow),
    ]
)
