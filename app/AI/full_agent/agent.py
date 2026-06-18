from google.adk.workflow import node

from app.AI.full_agent.conversation_agent.agent import conversation_agent
from app.AI.full_agent.actions_agent.agent import actions_agent
from app.AI.full_agent.root_agent.agent import root_agent as intent_agent
from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.agent import triage_agent
from app.AI.full_agent.search_agent.agent import search_workflow

from google.adk import Workflow, Event

from app.AI.schema import NavigationIntent

navigation_workflow = Workflow(
    name='navigation_workflow',
    edges=[
        ("START", triage_agent, search_workflow, actions_agent),
    ]
)

@node(name="navigation_router", rerun_on_resume=True)
def navigation_router(node_input: RootOutput):
    if node_input.intent == NavigationIntent.CONVERSATIONAL:
        return Event(route="conversational")
    else:
        return Event(route="navigation")

full_workflow = Workflow(
    name="full_workflow",
    edges=[
        ("START", intent_agent, navigation_router),
        (navigation_router,
             {
                 "conversational": conversation_agent,
                 "navigation": navigation_workflow
             }
         )
    ]
)

root_agent = full_workflow
agent = full_workflow
