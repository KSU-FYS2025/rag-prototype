from app.AI.root_agent.agent import root_agent
from app.AI.triage_agent.agent import triage_agent
from app.AI.search_agent.agent import search_workflow

from google.adk import Workflow

full_workflow = Workflow(
    name="full_workflow",
    edges=[
        ("START", root_agent, triage_agent, search_workflow),
    ]
)
