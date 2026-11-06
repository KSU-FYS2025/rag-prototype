from google.adk.workflow import node

from app.AI.full_agent.agent import navigation_workflow
from app.AI.full_agent.agent import capture_query
from google.adk import Workflow

from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.schema import NavigationIntent


@node(name="mock_root_output", rerun_on_resume=True)
def mock_root_output():
    return RootOutput(intent=NavigationIntent.NAV_GUIDE, confidence=0.9)


full_nav_workflow = Workflow(
    name="full_nav_workflow",
    edges=[("START", capture_query, mock_root_output, navigation_workflow)],
)

root_agent = full_nav_workflow
agent = full_nav_workflow
