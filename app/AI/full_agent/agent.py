from google.adk.workflow import node, JoinNode
from google.adk import Context, Workflow, Event

import logging
import asyncio

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.search_agent.agent import (
    validate_pois,
    search_poi_node,
    synthesis_agent,
)
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput
from app.AI.full_agent.conversation_agent.agent import conversation_agent
from app.AI.full_agent.actions_agent.agent import actions_agent
from app.AI.full_agent.root_agent.agent import root_agent as intent_agent
from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.agent import triage_agent
from app.AI.schema import NavigationIntent


@node(name="navigation_router", rerun_on_resume=True)
def navigation_router(node_input: RootOutput):
    if node_input.intent == NavigationIntent.CONVERSATIONAL:
        return Event(route="conversational")
    else:
        return Event(route="navigation")


def make_base_workflow(i: int) -> Workflow:
    return Workflow(
        name=f"BaseWorkflow_{i}",
        edges=[
            ("START", search_poi_node, validate_pois, synthesis_agent, actions_agent),
        ],
    )


@node(name="router", rerun_on_resume=True)
async def parallel_router(ctx: Context, node_input: TriageAgentOutput):
    node_input = TriageAgentOutput.model_validate(node_input.model_dump(mode="json"))
    logging.info(f"parallel_router called with {node_input}")
    workflows = [make_base_workflow(item.order) for item in node_input.targets]

    tasks = [ctx.run_node(wf, item) for wf, item in zip(workflows, node_input.targets)]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        raise RuntimeError(f"One or more sub-workflows failed: {failures}")

    results_obj = ActionsAgentOutput(
        user_query=node_input.user_query,
        actions=results,
    )

    return Event(output=results_obj, partial=True)


navigation_workflow = Workflow(
    name="navigation_workflow",
    edges=[
        ("START", triage_agent, parallel_router),
    ],
)

full_workflow = Workflow(
    name="full_workflow",
    edges=[
        ("START", intent_agent, navigation_router),
        (
            navigation_router,
            {"conversational": conversation_agent, "navigation": navigation_workflow},
        ),
    ],
)

root_agent = full_workflow
agent = full_workflow
