from app.AI.full_agent.agent import navigation_workflow
from app.AI.full_agent.agent import capture_query
from google.adk import Workflow

full_nav_workflow = Workflow(
    name="full_nav_workflow", edges=[("START", capture_query, navigation_workflow)]
)

root_agent = full_nav_workflow
agent = full_nav_workflow
